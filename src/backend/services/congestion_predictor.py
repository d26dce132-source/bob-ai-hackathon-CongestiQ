"""
Congestion Prediction Engine
=============================
Scores port-wide congestion risk over a 72-hour horizon by sliding a 6-hour
window across the schedule and aggregating four measurable factors.

All logic is deterministic, transparent, and derived solely from the Phase 1
database tables (vessels, berths, cranes, vessel_schedules).

Factor weights (must sum to 100)
---------------------------------
  arrival_density      30 pts  — how many vessels arrive per window
  berth_utilisation    35 pts  — % of compatible berths occupied/reserved
  crane_shortage       20 pts  — cranes needed vs cranes available
  delay_pressure       15 pts  — aggregate delay hours from late vessels

Classification thresholds
--------------------------
  0–30   LOW
  31–55  MEDIUM
  56–75  HIGH
  76–100 CRITICAL
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from db.models import Berth, Crane, Vessel, VesselSchedule
from schemas.prediction import (
    CongestionFactor,
    CongestionPredictionResponse,
    CongestionWindowScore,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WINDOW_HOURS = 6          # rolling window size in hours
HORIZON_HOURS = 72        # how far ahead to predict
WINDOW_COUNT = HORIZON_HOURS // WINDOW_HOURS  # = 12 windows

# Cranes needed per vessel type per call (rough operational estimate)
CRANES_NEEDED: dict[str, int] = {
    "container":    3,
    "bulk_carrier": 2,
    "tanker":       1,
    "roro":         1,
    "general_cargo": 2,
}

# Vessel size factor — larger ships create more congestion pressure
SIZE_FACTOR: dict[str, float] = {
    "container":    1.4,
    "bulk_carrier": 1.2,
    "tanker":       1.1,
    "roro":         0.9,
    "general_cargo": 0.8,
}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC timezone to naive datetimes (SQLite returns naive; PostgreSQL returns aware)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _classify(score: float) -> str:
    if score <= 30:
        return "LOW"
    if score <= 55:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


# ---------------------------------------------------------------------------
# Per-window scoring helpers
# ---------------------------------------------------------------------------

def _berth_utilisation(
    berths: list[Berth],
    active_schedules: list[VesselSchedule],
    window_start: datetime,
    window_end: datetime,
) -> Tuple[float, float]:
    """
    Returns (utilisation_pct 0–100, score_contribution 0–35).

    A berth is 'active' in a window if its schedule overlaps the window
    (eta < window_end  AND  etd > window_start).
    """
    total_berths = len(berths)
    if total_berths == 0:
        return 0.0, 0.0

    occupied_berth_ids: set[int] = set()
    for s in active_schedules:
        if s.berth_id is None:
            continue
        eta = _ensure_utc(s.eta)
        s_end = _ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24)
        if eta < window_end and s_end > window_start:
            occupied_berth_ids.add(s.berth_id)

    util_pct = min(len(occupied_berth_ids) / total_berths * 100, 100)
    # Non-linear: utilisation above 70% starts pressure spike
    if util_pct <= 70:
        contribution = (util_pct / 70) * 22   # 0–22 pts in the normal range
    else:
        contribution = 22 + ((util_pct - 70) / 30) * 13  # 22–35 pts in overload range
    return util_pct, round(contribution, 2)


def _arrival_density(
    schedules_in_window: list[VesselSchedule],
    berths: list[Berth],
) -> Tuple[int, float]:
    """
    Returns (arriving_count, score_contribution 0–30).
    Normalises against available berths — if arriving > available, pressure maxes.
    """
    n_arrivals = len(schedules_in_window)
    available_berths = max(len([b for b in berths if b.status not in ("maintenance",)]), 1)

    # Weight by vessel size
    weighted = sum(
        SIZE_FACTOR.get(s.vessel.vessel_type if s.vessel else "general_cargo", 1.0)
        for s in schedules_in_window
    )
    ratio = min(weighted / available_berths, 1.5)   # cap at 150%
    contribution = min((ratio / 1.5) * 30, 30)
    return n_arrivals, round(contribution, 2)


def _crane_shortage(
    schedules_in_window: list[VesselSchedule],
    cranes: list[Crane],
    berth_id_to_cranes: dict[int, list[Crane]],
) -> Tuple[float, float]:
    """
    Returns (shortage_factor 0–1, score_contribution 0–20).
    """
    total_cranes_needed = sum(
        CRANES_NEEDED.get(
            s.vessel.vessel_type if s.vessel else "general_cargo", 2
        )
        for s in schedules_in_window
    )
    # Available cranes = all cranes not in maintenance/offline
    available = sum(
        1 for c in cranes if c.status in ("available", "in_use")
    )
    if total_cranes_needed == 0:
        return 0.0, 0.0
    available = max(available, 1)
    shortage = max(0, (total_cranes_needed - available) / total_cranes_needed)
    contribution = shortage * 20
    return round(shortage, 4), round(contribution, 2)


def _delay_pressure(
    active_schedules: list[VesselSchedule],
) -> Tuple[int, float]:
    """
    Returns (delayed_count, score_contribution 0–15).
    Each delayed vessel contributes proportionally to its delay magnitude.
    """
    delayed = [s for s in active_schedules if s.delay_hours > 0]
    if not delayed:
        return 0, 0.0
    # Normalise: a vessel delayed 12+ hours contributes max pressure
    pressure = sum(min(s.delay_hours / 12.0, 1.0) for s in delayed)
    contribution = min((pressure / max(len(active_schedules), 1)) * 15, 15)
    return len(delayed), round(contribution, 2)


# ---------------------------------------------------------------------------
# Main prediction function
# ---------------------------------------------------------------------------

def compute_congestion(db: Session) -> CongestionPredictionResponse:
    """
    Compute port-wide congestion prediction for the next 72 hours.
    Returns a fully populated CongestionPredictionResponse.
    """
    now = datetime.now(timezone.utc)
    horizon_end = now + timedelta(hours=HORIZON_HOURS)

    # Load all data needed for prediction
    berths: list[Berth] = db.query(Berth).all()
    cranes: list[Crane] = db.query(Crane).all()

    # Build berth_id -> crane list map
    berth_id_to_cranes: dict[int, list[Crane]] = {}
    for c in cranes:
        if c.berth_id:
            berth_id_to_cranes.setdefault(c.berth_id, []).append(c)

    # Load all schedules in horizon (past 24h to future 72h) with relationships
    schedules: list[VesselSchedule] = (
        db.query(VesselSchedule)
        .options(joinedload(VesselSchedule.vessel), joinedload(VesselSchedule.berth))
        .filter(
            VesselSchedule.eta >= now - timedelta(hours=24),
            VesselSchedule.eta <= horizon_end,
            VesselSchedule.status.notin_(["cancelled", "completed"]),
        )
        .all()
    )

    # ------------------------------------------------------------------
    # Slide window across the 72-hour horizon
    # ------------------------------------------------------------------
    window_scores: list[CongestionWindowScore] = []

    for i in range(WINDOW_COUNT):
        w_start = now + timedelta(hours=i * WINDOW_HOURS)
        w_end = w_start + timedelta(hours=WINDOW_HOURS)

        # Schedules arriving in this window
        arriving = [s for s in schedules if w_start <= _ensure_utc(s.eta) < w_end]
        # Schedules active (overlapping) in this window
        active = []
        for s in schedules:
            eta = _ensure_utc(s.eta)
            s_end = _ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24)
            if eta < w_end and s_end > w_start:
                active.append(s)

        util_pct, util_score = _berth_utilisation(berths, active, w_start, w_end)
        n_arriving, arrival_score = _arrival_density(arriving, berths)
        shortage_factor, crane_score = _crane_shortage(arriving, cranes, berth_id_to_cranes)
        n_delayed, delay_score = _delay_pressure(active)

        raw_score = util_score + arrival_score + crane_score + delay_score
        score = round(min(raw_score, 100), 1)

        window_scores.append(
            CongestionWindowScore(
                window_start=w_start,
                window_end=w_end,
                score=score,
                level=_classify(score),
                arriving_vessels=n_arriving,
                berth_utilisation_pct=round(util_pct, 1),
                crane_shortage_factor=shortage_factor,
                delayed_vessel_count=n_delayed,
            )
        )

    # ------------------------------------------------------------------
    # Aggregate to overall score (weighted average, peak penalised)
    # ------------------------------------------------------------------
    scores = [w.score for w in window_scores]
    mean_score = sum(scores) / len(scores)
    peak_score = max(scores)
    # Overall = 60% mean + 40% peak — ensures a brief spike still registers
    overall = round(min(0.6 * mean_score + 0.4 * peak_score, 100), 1)
    overall_level = _classify(overall)

    # Peak window
    peak_idx = scores.index(peak_score)
    peak_window = window_scores[peak_idx]

    # ------------------------------------------------------------------
    # Build factor breakdown (for the current / next window)
    # ------------------------------------------------------------------
    w0 = window_scores[0]  # immediate next window
    arriving_now = [s for s in schedules if now <= _ensure_utc(s.eta) < now + timedelta(hours=WINDOW_HOURS)]
    active_now = []
    for s in schedules:
        eta = _ensure_utc(s.eta)
        s_end = _ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24)
        if eta < now + timedelta(hours=WINDOW_HOURS) and s_end > now:
            active_now.append(s)

    util_pct0, util_score0 = _berth_utilisation(berths, active_now, now, now + timedelta(hours=WINDOW_HOURS))
    _, arrival_score0 = _arrival_density(arriving_now, berths)
    shortage0, crane_score0 = _crane_shortage(arriving_now, cranes, berth_id_to_cranes)
    n_delayed0, delay_score0 = _delay_pressure(active_now)

    total_berths = len(berths)
    available_berths = len([b for b in berths if b.status == "available"])
    total_cranes = len([c for c in cranes if c.status not in ("maintenance", "offline")])

    factors: list[CongestionFactor] = [
        CongestionFactor(
            name="Berth Utilisation",
            contribution=round(util_score0 * (overall / max(w0.score, 1)), 2),
            description=(
                f"{total_berths - available_berths} of {total_berths} berths occupied or reserved "
                f"({util_pct0:.0f}% utilisation in current window)"
            ),
        ),
        CongestionFactor(
            name="Arrival Density",
            contribution=round(arrival_score0 * (overall / max(w0.score, 1)), 2),
            description=(
                f"{len(arriving_now)} vessel(s) arriving in the next {WINDOW_HOURS} hours "
                f"against {available_berths} available berths"
            ),
        ),
        CongestionFactor(
            name="Crane Shortage",
            contribution=round(crane_score0 * (overall / max(w0.score, 1)), 2),
            description=(
                f"{total_cranes} operational cranes available; "
                f"shortage factor {shortage0:.0%} for current arrival wave"
            ),
        ),
        CongestionFactor(
            name="Delay Pressure",
            contribution=round(delay_score0 * (overall / max(w0.score, 1)), 2),
            description=(
                f"{n_delayed0} vessel(s) currently experiencing delays, "
                f"holding berths longer than scheduled"
            ),
        ),
    ]

    # ------------------------------------------------------------------
    # Plain-English summary
    # ------------------------------------------------------------------
    busy_windows = sum(1 for w in window_scores if w.level in ("HIGH", "CRITICAL"))
    summary = (
        f"Port congestion is {overall_level} (score {overall}/100). "
        f"Peak congestion expected between "
        f"{peak_window.window_start.strftime('%H:%M UTC on %d %b')} and "
        f"{peak_window.window_end.strftime('%H:%M UTC on %d %b')} "
        f"(score {peak_score}/100). "
        f"{busy_windows} of {WINDOW_COUNT} planning windows are HIGH or CRITICAL."
    )

    return CongestionPredictionResponse(
        computed_at=now,
        overall_score=overall,
        overall_level=overall_level,
        peak_window_start=peak_window.window_start,
        peak_window_end=peak_window.window_end,
        peak_score=peak_score,
        factors=factors,
        window_scores=window_scores,
        summary=summary,
    )

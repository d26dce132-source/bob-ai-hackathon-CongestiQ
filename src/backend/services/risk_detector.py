"""
Vessel Risk Detection Service
==============================
Computes a congestion/delay risk score (0–100) for every vessel that has an
active or upcoming schedule within the next 72 hours.

Risk Factors
------------
  eta_proximity      25 pts  — vessels arriving sooner face current congestion
  existing_delay     25 pts  — vessels already delayed have compounding risk
  berth_fit          20 pts  — vessel dimensions vs compatible berth availability
  terminal_pressure  20 pts  — how busy the target terminal is right now
  low_priority       10 pts  — lower-priority vessels wait longer when congested

Classification thresholds
--------------------------
  0–25   LOW
  26–50  MEDIUM
  51–75  HIGH
  76–100 CRITICAL
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC timezone to naive datetimes (SQLite returns naive; PostgreSQL returns aware)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

from sqlalchemy.orm import Session, joinedload

from db.models import Berth, Crane, Vessel, VesselSchedule
from schemas.prediction import VesselRiskFactor, VesselRiskListResponse, VesselRiskResponse

HORIZON_HOURS = 72

# Vessels arriving within this many hours are at maximum ETA-proximity risk
MAX_PROXIMITY_HOURS = 12


def _classify(score: float) -> str:
    if score <= 25:
        return "LOW"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def _eta_proximity_score(eta: datetime, now: datetime) -> tuple[float, str]:
    """
    Vessels arriving sooner face full current congestion.
    0-12 h away -> 25 pts (max)
    12-72 h away -> linearly declines to 0 pts
    """
    eta = _ensure_utc(eta)
    hours_away = max((eta - now).total_seconds() / 3600, 0)
    if hours_away <= MAX_PROXIMITY_HOURS:
        score = 25.0
        desc = f"Arriving in {hours_away:.1f}h — fully exposed to current port congestion"
    else:
        ratio = max(0, (HORIZON_HOURS - hours_away) / (HORIZON_HOURS - MAX_PROXIMITY_HOURS))
        score = round(ratio * 25, 2)
        desc = f"Arriving in {hours_away:.1f}h — some lead time reduces exposure"
    return score, desc


def _delay_score(delay_hours: float) -> tuple[float, str]:
    """
    Vessels already delayed compound congestion risk (they hold berths longer).
    0 h delay → 0 pts
    ≥ 12 h delay → 25 pts (max)
    """
    score = round(min(delay_hours / 12.0, 1.0) * 25, 2)
    if delay_hours == 0:
        desc = "No existing delay reported"
    elif delay_hours < 3:
        desc = f"Minor delay of {delay_hours:.1f}h — minor impact on berth schedule"
    elif delay_hours < 8:
        desc = f"Moderate delay of {delay_hours:.1f}h — risks missing berth window"
    else:
        desc = f"Significant delay of {delay_hours:.1f}h — likely to displace subsequent vessels"
    return score, desc


def _berth_fit_score(
    vessel: Vessel,
    assigned_berth: Optional[Berth],
    all_berths: list[Berth],
) -> tuple[float, str]:
    """
    Vessels with fewer compatible berths have less flexibility and higher risk.
    1 compatible berth  → 20 pts (max risk)
    ≥ 5 compatible berths → 0 pts
    Also penalised if assigned berth is occupied and vessel has no unassigned berth.
    """
    compatible = [
        b for b in all_berths
        if vessel.vessel_type in b.vessel_types_allowed
        and b.max_draft_m >= vessel.draft_m
        and b.length_m >= vessel.length_m
    ]
    n_compatible = len(compatible)
    available_compatible = [b for b in compatible if b.status == "available"]

    if n_compatible == 0:
        score = 20.0
        desc = "No fully compatible berth found — will require special arrangement"
    elif len(available_compatible) == 0:
        score = 20.0
        desc = f"All {n_compatible} compatible berth(s) are currently occupied or under maintenance"
    else:
        ratio = max(0, (5 - len(available_compatible)) / 5)
        score = round(ratio * 20, 2)
        desc = (
            f"{len(available_compatible)} of {n_compatible} compatible berths currently available"
        )

    if assigned_berth and assigned_berth.status == "maintenance":
        score = min(score + 10, 20)
        desc += "; assigned berth is under maintenance"

    return score, desc


def _terminal_pressure_score(
    berth_id: Optional[int],
    all_berths: list[Berth],
    schedules: list[VesselSchedule],
    now: datetime,
) -> tuple[float, str]:
    """
    How busy is the target terminal in the next 12 hours?
    Looks at how many schedules overlap the immediate 12-hour window
    for berths in the same terminal.
    """
    if berth_id is None:
        # No berth assigned — moderate default pressure
        return 10.0, "No berth assigned yet — arrival slot uncertain"

    assigned = next((b for b in all_berths if b.id == berth_id), None)
    if assigned is None:
        return 5.0, "Assigned berth data unavailable"

    terminal = assigned.terminal
    terminal_berth_ids = {b.id for b in all_berths if b.terminal == terminal}
    terminal_berth_count = len(terminal_berth_ids)

    window_end = now + timedelta(hours=12)
    active_in_terminal = 0
    for s in schedules:
        if s.berth_id not in terminal_berth_ids:
            continue
        eta = _ensure_utc(s.eta)
        s_end = _ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24)
        if eta < window_end and s_end > now:
            active_in_terminal += 1

    utilisation = min(active_in_terminal / max(terminal_berth_count, 1), 1.0)
    score = round(utilisation * 20, 2)
    desc = (
        f"{active_in_terminal} vessel(s) active at {terminal} "
        f"in next 12h ({utilisation:.0%} terminal utilisation)"
    )
    return score, desc


def _priority_score(priority: int) -> tuple[float, str]:
    """
    Lower-priority vessels (priority 4–5) wait when congested.
    priority 1 (highest) → 0 pts
    priority 5 (lowest)  → 10 pts
    """
    score = round((priority - 1) / 4 * 10, 2)
    labels = {1: "Highest", 2: "High", 3: "Normal", 4: "Low", 5: "Lowest"}
    label = labels.get(priority, "Normal")
    desc = f"Priority {priority} ({label}) — {'may be deprioritised when berths are scarce' if priority > 3 else 'will be scheduled preferentially'}"
    return score, desc


def _build_recommendation(level: str, vessel: Vessel, delay_hours: float, berth_code: Optional[str]) -> str:
    if level == "LOW":
        return "No action required — proceed on current schedule."
    if level == "MEDIUM":
        return (
            f"Monitor closely. Consider adjusting sailing speed to shift ETA "
            f"by 2–4 hours if berth {berth_code or 'TBC'} becomes congested."
        )
    if level == "HIGH":
        return (
            f"Recommend speed adjustment or pre-arrival anchor notification. "
            f"Coordinate with port authority for priority berth access. "
            f"Current delay: {delay_hours:.1f}h."
        )
    return (
        f"CRITICAL: Immediate coordination required. Consider diverting to "
        f"alternative terminal or requesting emergency berth assignment. "
        f"Vessel {vessel.name} ({vessel.imo_number}) at serious congestion risk."
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def compute_vessel_risks(db: Session) -> VesselRiskListResponse:
    """
    Compute risk scores for all vessels with schedules in the next 72 hours.
    Returns a VesselRiskListResponse.
    """
    now = datetime.now(timezone.utc)
    horizon_end = now + timedelta(hours=HORIZON_HOURS)

    all_berths: list[Berth] = db.query(Berth).all()

    schedules: list[VesselSchedule] = (
        db.query(VesselSchedule)
        .options(joinedload(VesselSchedule.vessel), joinedload(VesselSchedule.berth))
        .filter(
            VesselSchedule.eta <= horizon_end,
            VesselSchedule.status.notin_(["cancelled", "completed"]),
        )
        .order_by(VesselSchedule.eta)
        .all()
    )

    # Deduplicate: keep only the earliest upcoming schedule per vessel
    seen_vessel_ids: set[int] = set()
    unique_schedules: list[VesselSchedule] = []
    for s in schedules:
        if s.vessel_id not in seen_vessel_ids:
            seen_vessel_ids.add(s.vessel_id)
            unique_schedules.append(s)

    results: list[VesselRiskResponse] = []

    for sched in unique_schedules:
        vessel = sched.vessel
        if vessel is None:
            continue

        eta_score, eta_desc = _eta_proximity_score(sched.eta, now)
        delay_score, delay_desc = _delay_score(sched.delay_hours)
        berth_score, berth_desc = _berth_fit_score(vessel, sched.berth, all_berths)
        terminal_score, terminal_desc = _terminal_pressure_score(
            sched.berth_id, all_berths, schedules, now
        )
        priority_score, priority_desc = _priority_score(sched.priority)

        total_score = round(
            min(eta_score + delay_score + berth_score + terminal_score + priority_score, 100), 1
        )
        level = _classify(total_score)

        factors = [
            VesselRiskFactor(name="ETA Proximity",      contribution=round(eta_score, 1),      description=eta_desc),
            VesselRiskFactor(name="Existing Delay",     contribution=round(delay_score, 1),    description=delay_desc),
            VesselRiskFactor(name="Berth Compatibility", contribution=round(berth_score, 1),   description=berth_desc),
            VesselRiskFactor(name="Terminal Pressure",  contribution=round(terminal_score, 1), description=terminal_desc),
            VesselRiskFactor(name="Priority Level",     contribution=round(priority_score, 1), description=priority_desc),
        ]

        berth_code = sched.berth.code if sched.berth else None
        recommendation = _build_recommendation(level, vessel, sched.delay_hours, berth_code)

        results.append(
            VesselRiskResponse(
                vessel_id=vessel.id,
                vessel_name=vessel.name,
                vessel_type=vessel.vessel_type,
                imo_number=vessel.imo_number,
                current_status=vessel.status,
                schedule_id=sched.id,
                eta=sched.eta,
                berth_code=berth_code,
                risk_score=total_score,
                risk_level=level,
                delay_hours=sched.delay_hours,
                factors=factors,
                recommendation=recommendation,
            )
        )

    # Sort: highest risk first
    results.sort(key=lambda v: v.risk_score, reverse=True)

    return VesselRiskListResponse(
        computed_at=now,
        total=len(results),
        vessels=results,
    )

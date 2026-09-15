"""
Berth Assignment Optimizer
===========================
For each vessel schedule in the next 72 hours, evaluate all berths and
recommend the best fit.

Scoring (0-100)
---------------
  compatibility_check (hard gate) — vessel type, draft, length must pass
  availability_score   40 pts  — berth not double-booked in the ETA-ETD window
  congestion_relief    30 pts  — prefer berths in less-busy terminals
  priority_fit         20 pts  — high-priority vessels get better berths
  shore_power_bonus    10 pts  — bonus for vessels that benefit from shore power

If no berth passes the hard compatibility gate, the vessel is flagged
as unassignable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from db.models import Berth, Vessel, VesselSchedule
from schemas.optimization import (
    BerthAssignmentRecommendation,
    BerthAssignmentResponse,
    BerthFitScore,
)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


HORIZON_HOURS = 72

# Which vessel types benefit from shore power (e.g. for refrigerated cargo)
SHORE_POWER_TYPES = {"container", "roro"}


# ---------------------------------------------------------------------------
# Hard compatibility check
# ---------------------------------------------------------------------------
def _is_compatible(vessel: Vessel, berth: Berth) -> tuple[bool, str]:
    """
    Returns (passes: bool, notes: str).
    All three conditions must be true for a berth to be usable.
    """
    reasons = []
    ok = True

    if vessel.vessel_type not in berth.vessel_types_allowed:
        reasons.append(f"type '{vessel.vessel_type}' not allowed (berth accepts: {berth.vessel_types_allowed})")
        ok = False

    if vessel.draft_m > berth.max_draft_m:
        reasons.append(f"draft {vessel.draft_m}m exceeds max {berth.max_draft_m}m")
        ok = False

    if vessel.length_m > berth.length_m:
        reasons.append(f"length {vessel.length_m}m exceeds berth length {berth.length_m}m")
        ok = False

    if ok:
        return True, (
            f"Type OK ({vessel.vessel_type}), "
            f"draft OK ({vessel.draft_m}m <= {berth.max_draft_m}m), "
            f"length OK ({vessel.length_m}m <= {berth.length_m}m)"
        )
    return False, "; ".join(reasons)


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------
def _is_available(
    berth: Berth,
    eta: datetime,
    etd: datetime,
    all_schedules: list[VesselSchedule],
    exclude_schedule_id: Optional[int] = None,
) -> tuple[bool, str]:
    """
    Returns (available: bool, notes: str).
    Checks whether any existing schedule at this berth overlaps [eta, etd].
    """
    if berth.status == "maintenance":
        return False, "Berth under maintenance"

    overlapping = []
    for s in all_schedules:
        if s.berth_id != berth.id:
            continue
        if exclude_schedule_id and s.id == exclude_schedule_id:
            continue
        s_eta = _ensure_utc(s.eta)
        s_etd = _ensure_utc(s.etd) if s.etd else s_eta + timedelta(hours=24)
        # Overlap: [eta, etd) overlaps [s_eta, s_etd) iff eta < s_etd AND etd > s_eta
        if eta < s_etd and etd > s_eta:
            overlapping.append(s)

    if overlapping:
        names = ", ".join(
            s.vessel.name if s.vessel else f"#{s.vessel_id}" for s in overlapping[:2]
        )
        return False, f"Occupied by {names} during {eta.strftime('%H:%M')}-{etd.strftime('%H:%M')}"

    return True, f"Berth free {eta.strftime('%d %b %H:%M')}-{etd.strftime('%d %b %H:%M')}"


# ---------------------------------------------------------------------------
# Berth congestion load (for terminal-level preference)
# ---------------------------------------------------------------------------
def _terminal_load(
    terminal: str,
    berths: list[Berth],
    schedules: list[VesselSchedule],
    now: datetime,
    window_hours: int = 12,
) -> float:
    """Returns 0.0-1.0 — fraction of terminal berths occupied in next window_hours."""
    terminal_berths = [b for b in berths if b.terminal == terminal]
    if not terminal_berths:
        return 0.0
    window_end = now + timedelta(hours=window_hours)
    occupied = set()
    for s in schedules:
        if not any(b.id == s.berth_id for b in terminal_berths):
            continue
        s_eta = _ensure_utc(s.eta)
        s_etd = _ensure_utc(s.etd) if s.etd else s_eta + timedelta(hours=24)
        if s_eta < window_end and s_etd > now:
            occupied.add(s.berth_id)
    return len(occupied) / len(terminal_berths)


# ---------------------------------------------------------------------------
# Score a single berth for a vessel
# ---------------------------------------------------------------------------
def _score_berth(
    vessel: Vessel,
    berth: Berth,
    eta: datetime,
    etd: datetime,
    priority: int,
    all_schedules: list[VesselSchedule],
    all_berths: list[Berth],
    now: datetime,
    exclude_schedule_id: Optional[int] = None,
) -> BerthFitScore:
    compatible, compat_notes = _is_compatible(vessel, berth)
    if not compatible:
        return BerthFitScore(
            berth_id=berth.id,
            berth_code=berth.code,
            terminal=berth.terminal,
            fit_score=0.0,
            compatibility=False,
            availability=False,
            compatibility_notes=compat_notes,
            availability_notes="Not evaluated (failed compatibility)",
        )

    available, avail_notes = _is_available(berth, eta, etd, all_schedules, exclude_schedule_id)

    # Availability score (40 pts)
    avail_score = 40.0 if available else 0.0

    # Congestion relief (30 pts) — lower terminal load = better
    t_load = _terminal_load(berth.terminal, all_berths, all_schedules, now)
    relief_score = (1.0 - t_load) * 30.0

    # Priority fit (20 pts) — priority 1 gets full score, priority 5 gets 0
    priority_score = ((5 - priority) / 4) * 20.0

    # Shore power bonus (10 pts)
    shore_score = 10.0 if (berth.has_shore_power and vessel.vessel_type in SHORE_POWER_TYPES) else 0.0

    total = round(avail_score + relief_score + priority_score + shore_score, 1)

    return BerthFitScore(
        berth_id=berth.id,
        berth_code=berth.code,
        terminal=berth.terminal,
        fit_score=total,
        compatibility=True,
        availability=available,
        compatibility_notes=compat_notes,
        availability_notes=avail_notes,
    )


# ---------------------------------------------------------------------------
# Main optimizer
# ---------------------------------------------------------------------------
def compute_berth_assignments(db: Session) -> BerthAssignmentResponse:
    now = datetime.now(timezone.utc)
    horizon_end = now + timedelta(hours=HORIZON_HOURS)

    berths: list[Berth] = db.query(Berth).all()

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

    recommendations: list[BerthAssignmentRecommendation] = []
    unassignable_count = 0

    for sched in schedules:
        vessel = sched.vessel
        if vessel is None:
            continue

        eta = _ensure_utc(sched.eta)
        etd = _ensure_utc(sched.etd) if sched.etd else eta + timedelta(hours=24)

        # Score all berths
        scored: list[BerthFitScore] = [
            _score_berth(
                vessel, berth, eta, etd,
                sched.priority, schedules, berths, now,
                exclude_schedule_id=sched.id,
            )
            for berth in berths
        ]

        # Filter: only compatible berths can be recommended
        viable = [s for s in scored if s.compatibility and s.availability]
        all_compatible = [s for s in scored if s.compatibility]

        if not viable and not all_compatible:
            # Truly unassignable — no compatible berth at all
            unassignable_count += 1
            current_code = sched.berth.code if sched.berth else None
            recommendations.append(
                BerthAssignmentRecommendation(
                    schedule_id=sched.id,
                    vessel_id=vessel.id,
                    vessel_name=vessel.name,
                    vessel_type=vessel.vessel_type,
                    eta=eta,
                    etd=etd,
                    current_berth_code=current_code,
                    recommended_berth_code=current_code or "NONE",
                    recommended_berth_id=sched.berth_id or 0,
                    recommended_terminal="N/A",
                    fit_score=0.0,
                    change_required=False,
                    reason="No compatible berth found — vessel requires special arrangement",
                    alternative_berths=[],
                )
            )
            continue

        # Pick best viable berth; fall back to best compatible if none available
        candidates = viable if viable else all_compatible
        best = max(candidates, key=lambda s: s.fit_score)

        # Alternatives: next-best compatible berths (excluding the best)
        alternatives = sorted(
            [s for s in all_compatible if s.berth_code != best.berth_code],
            key=lambda s: s.fit_score,
            reverse=True,
        )[:3]

        current_code = sched.berth.code if sched.berth else None
        change_required = current_code != best.berth_code

        # Build reason
        if not viable and all_compatible:
            reason = (
                f"All compatible berths are occupied during {eta.strftime('%H:%M')}-"
                f"{etd.strftime('%H:%M')}. Best compatible berth {best.berth_code} "
                f"recommended — arrival window may need adjustment."
            )
        elif change_required:
            reason = (
                f"Berth {best.berth_code} ({best.terminal}) offers the best fit "
                f"(score {best.fit_score}/100). "
                f"{'Currently assigned to ' + current_code + ' which is less optimal.' if current_code else 'No berth currently assigned.'}"
            )
        else:
            reason = (
                f"Current berth {current_code} is the optimal assignment "
                f"(score {best.fit_score}/100). No change recommended."
            )

        recommendations.append(
            BerthAssignmentRecommendation(
                schedule_id=sched.id,
                vessel_id=vessel.id,
                vessel_name=vessel.name,
                vessel_type=vessel.vessel_type,
                eta=eta,
                etd=etd,
                current_berth_code=current_code,
                recommended_berth_code=best.berth_code,
                recommended_berth_id=best.berth_id,
                recommended_terminal=best.terminal,
                fit_score=best.fit_score,
                change_required=change_required,
                reason=reason,
                alternative_berths=alternatives,
            )
        )

    changes = sum(1 for r in recommendations if r.change_required)
    summary = (
        f"{len(recommendations)} vessel schedule(s) evaluated. "
        f"{changes} berth change(s) recommended to reduce congestion. "
        f"{unassignable_count} vessel(s) require special berth arrangement."
    )

    return BerthAssignmentResponse(
        computed_at=now,
        total_recommendations=len(recommendations),
        unassignable_count=unassignable_count,
        recommendations=recommendations,
        summary=summary,
    )

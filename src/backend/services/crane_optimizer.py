"""
Crane Assignment Optimizer
============================
For each vessel schedule in the next 72 hours, recommend which cranes
should be assigned to handle its cargo operations.

Crane selection scoring (0-100)
--------------------------------
  type_match        40 pts  — crane type suits vessel type
  availability      30 pts  — crane not already committed to overlapping work
  proximity         20 pts  — crane already at the assigned berth (or unassigned)
  capacity_fit      10 pts  — crane lift capacity >= cargo weight requirement

If fewer cranes are available than required, a shortfall warning is raised.

Crane type preference by vessel type
--------------------------------------
  container     -> quay_crane  (ship-to-shore)
  bulk_carrier  -> mobile_crane
  tanker        -> mobile_crane (loading arms are hose-based, cranes for mooring)
  roro          -> mobile_crane (ramp operations, light cranes)
  general_cargo -> mobile_crane or reach_stacker
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from db.models import Crane, VesselSchedule
from schemas.optimization import (
    CraneAssignmentDetail,
    CraneAssignmentRecommendation,
    CraneAssignmentResponse,
)

HORIZON_HOURS = 72

# Preferred crane types per vessel type (ordered, first match wins)
PREFERRED_CRANE_TYPES: dict[str, list[str]] = {
    "container":     ["quay_crane", "gantry_crane"],
    "bulk_carrier":  ["mobile_crane", "gantry_crane"],
    "tanker":        ["mobile_crane"],
    "roro":          ["mobile_crane", "reach_stacker"],
    "general_cargo": ["mobile_crane", "reach_stacker", "gantry_crane"],
}

# Required cranes per vessel type per operation
CRANES_REQUIRED: dict[str, int] = {
    "container":     3,
    "bulk_carrier":  2,
    "tanker":        1,
    "roro":          1,
    "general_cargo": 2,
}

# Minimum lift capacity (tonnes) suitable per vessel type
MIN_LIFT_CAPACITY: dict[str, float] = {
    "container":     55.0,
    "bulk_carrier":  80.0,
    "tanker":        70.0,
    "roro":          40.0,
    "general_cargo": 45.0,
}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_crane_available(
    crane: Crane,
    eta: datetime,
    etd: datetime,
    all_schedules: list[VesselSchedule],
    exclude_schedule_id: Optional[int] = None,
) -> bool:
    """
    A crane is available if it is not committed to any overlapping schedule
    at the same berth, within the [eta, etd] window.
    We track crane assignments by berth: if the crane is assigned to a berth
    that has another vessel in the window, it is considered busy.
    """
    if crane.status in ("maintenance", "offline"):
        return False

    if crane.berth_id is None:
        return True  # Pool crane — always considered available

    # Check if the crane's berth has another schedule overlapping our window
    for s in all_schedules:
        if s.berth_id != crane.berth_id:
            continue
        if exclude_schedule_id and s.id == exclude_schedule_id:
            continue
        s_eta = _ensure_utc(s.eta)
        s_etd = _ensure_utc(s.etd) if s.etd else s_eta + timedelta(hours=24)
        if eta < s_etd and etd > s_eta:
            return False  # Crane is busy at its berth during this window

    return True


def _score_crane(
    crane: Crane,
    vessel_type: str,
    berth_id: Optional[int],
    eta: datetime,
    etd: datetime,
    all_schedules: list[VesselSchedule],
    exclude_schedule_id: Optional[int],
) -> float:
    """Score a single crane candidate (0-100)."""
    preferred = PREFERRED_CRANE_TYPES.get(vessel_type, ["mobile_crane"])

    # Type match (40 pts)
    if crane.crane_type == preferred[0]:
        type_score = 40.0
    elif crane.crane_type in preferred:
        type_score = 25.0
    else:
        type_score = 0.0

    # Availability (30 pts)
    if _is_crane_available(crane, eta, etd, all_schedules, exclude_schedule_id):
        avail_score = 30.0
    else:
        return 0.0  # Unavailable crane cannot be recommended

    # Proximity (20 pts) — crane at the assigned berth or unassigned
    if crane.berth_id is None:
        proximity_score = 15.0  # pool crane, needs to be moved
    elif crane.berth_id == berth_id:
        proximity_score = 20.0  # already at the right berth
    else:
        proximity_score = 5.0   # at a different berth — relocation needed

    # Capacity fit (10 pts)
    min_cap = MIN_LIFT_CAPACITY.get(vessel_type, 50.0)
    if crane.max_lift_tonnes >= min_cap * 1.2:
        cap_score = 10.0  # well above minimum
    elif crane.max_lift_tonnes >= min_cap:
        cap_score = 6.0   # meets minimum
    else:
        cap_score = 0.0   # undersized

    return round(type_score + avail_score + proximity_score + cap_score, 1)


def compute_crane_assignments(db: Session) -> CraneAssignmentResponse:
    now = datetime.now(timezone.utc)
    horizon_end = now + timedelta(hours=HORIZON_HOURS)

    cranes: list[Crane] = db.query(Crane).all()

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

    recommendations: list[CraneAssignmentRecommendation] = []
    shortfall_count = 0

    for sched in schedules:
        vessel = sched.vessel
        if vessel is None:
            continue

        eta = _ensure_utc(sched.eta)
        etd = _ensure_utc(sched.etd) if sched.etd else eta + timedelta(hours=24)
        vessel_type = vessel.vessel_type
        n_required = CRANES_REQUIRED.get(vessel_type, 2)
        berth_id = sched.berth_id
        berth_code = sched.berth.code if sched.berth else None

        # Score all cranes
        scored: list[tuple[Crane, float]] = []
        for crane in cranes:
            score = _score_crane(
                crane, vessel_type, berth_id, eta, etd, schedules, sched.id
            )
            if score > 0:
                scored.append((crane, score))

        # Sort best first, pick the top n_required
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = scored[:n_required]
        shortfall = max(0, n_required - len(selected))

        if shortfall > 0:
            shortfall_count += 1

        # Build crane detail objects
        crane_details: list[CraneAssignmentDetail] = []
        for crane, score in selected:
            crane_berth_code = None
            if crane.berth_id:
                crane_berth = next((b for b in [sched.berth] if b and b.id == crane.berth_id), None)
                # Find berth code from schedule's berth or use ID
                crane_berth_code = f"Berth#{crane.berth_id}" if crane.berth_id else None

            if crane.berth_id == berth_id:
                crane_reason = f"Already stationed at {berth_code} — no relocation needed"
            elif crane.berth_id is None:
                crane_reason = f"Pool crane — deploy to {berth_code}"
            else:
                crane_reason = f"Redeploy from Berth#{crane.berth_id} to {berth_code}"

            crane_details.append(
                CraneAssignmentDetail(
                    crane_id=crane.id,
                    crane_code=crane.code,
                    crane_type=crane.crane_type,
                    berth_code=berth_code,
                    reason=crane_reason,
                )
            )

        # Build reason summary
        preferred_types = PREFERRED_CRANE_TYPES.get(vessel_type, ["mobile_crane"])
        if shortfall > 0:
            reason = (
                f"{n_required} crane(s) required for {vessel_type} operations at {berth_code}. "
                f"Only {len(selected)} available — shortfall of {shortfall}. "
                f"Preferred type: {preferred_types[0]}."
            )
            shortfall_warning = (
                f"WARNING: {shortfall} crane(s) short for {vessel.name}. "
                f"Operations at {berth_code} may be delayed."
            )
        else:
            reason = (
                f"{n_required} {preferred_types[0]}(s) recommended for {vessel.name} "
                f"at {berth_code}. All required cranes available."
            )
            shortfall_warning = None

        recommendations.append(
            CraneAssignmentRecommendation(
                schedule_id=sched.id,
                vessel_id=vessel.id,
                vessel_name=vessel.name,
                vessel_type=vessel_type,
                eta=eta,
                berth_code=berth_code,
                cranes_required=n_required,
                cranes_recommended=crane_details,
                cranes_shortfall=shortfall,
                shortfall_warning=shortfall_warning,
                reason=reason,
            )
        )

    summary = (
        f"{len(recommendations)} vessel schedule(s) evaluated for crane assignments. "
        f"{shortfall_count} vessel(s) face a crane shortfall — immediate reallocation advised."
    )

    return CraneAssignmentResponse(
        computed_at=now,
        total_recommendations=len(recommendations),
        shortfall_count=shortfall_count,
        recommendations=recommendations,
        summary=summary,
    )

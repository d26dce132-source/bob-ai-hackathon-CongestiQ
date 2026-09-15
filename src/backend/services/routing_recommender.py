"""
Alternative Routing Recommendations
=====================================
Identifies vessels that face HIGH or CRITICAL congestion risk and generates
actionable alternative routing options based on the simulated port data.

NOTE: These recommendations are generated from simulated/sample port data
and are intended as a prototype decision-support tool. In production,
recommendations would also consider real-time AIS data, weather, port
authority approvals, and commercial agreements.

Three alternative action types are always evaluated per vessel:
  1. speed_reduction      — arrive later by slowing down (shifts ETA)
  2. anchor_and_wait      — proceed to anchorage, wait for congestion to ease
  3. terminal_transfer    — redirect to alternative terminal within the port
  4. divert_to_anchorage  — hold at a nearby anchorage point (for CRITICAL)

Each alternative is scored on:
  feasibility_score  0-100  (based on priority, delay tolerance, vessel type)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from db.models import Berth, VesselSchedule
from schemas.optimization import (
    RoutingAlternative,
    RoutingRecommendation,
    RoutingRecommendationResponse,
)
from services.risk_detector import compute_vessel_risks

HORIZON_HOURS = 72
RISK_THRESHOLD = 50.0  # only generate routing for vessels above this risk score

DATA_NOTICE = (
    "PROTOTYPE NOTICE: These routing recommendations are generated from simulated "
    "port operational data for demonstration purposes. Real routing decisions require "
    "coordination with port authorities, vessel operators, and real-time AIS data."
)

# Anchorage areas near the simulated port
ANCHORAGE_AREAS = [
    "North Anchorage (NA-1)",
    "Eastern Roads (ER-2)",
    "Outer Harbour Waiting Area (OHW-3)",
]


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _build_speed_reduction(
    vessel_type: str,
    priority: int,
    delay_hours: float,
    risk_score: float,
) -> RoutingAlternative:
    """
    Reducing speed by 10-20% typically shifts ETA by 4-8 hours,
    which can move the vessel out of the peak congestion window.
    """
    delay_shift = 6.0 if risk_score >= 75 else 4.0
    # Feasibility decreases with higher existing delay and higher priority
    penalty = min(delay_hours * 3, 30) + (priority - 1) * 5
    feasibility = max(round(80 - penalty, 1), 10.0)
    congestion_reduction = round(min(delay_shift / 8 * 40, 40), 1)

    return RoutingAlternative(
        option_rank=1,
        action_type="speed_reduction",
        description=(
            f"Reduce speed by 15% to shift ETA by approximately {delay_shift:.0f} hours. "
            f"This moves arrival outside the peak congestion window."
        ),
        estimated_delay_hours=delay_shift,
        congestion_reduction_pct=congestion_reduction,
        feasibility_score=feasibility,
        trade_offs=(
            f"Adds {delay_shift:.0f}h to voyage time. Increased fuel consumption at "
            f"low speed may partially offset savings. Not suitable for time-critical cargo."
        ),
    )


def _build_anchor_and_wait(
    vessel_type: str,
    priority: int,
    risk_score: float,
) -> RoutingAlternative:
    """
    Vessel proceeds to anchorage and waits for a clear berth window.
    Best for lower-priority vessels when congestion is temporary.
    """
    wait_hours = 8.0 if risk_score >= 75 else 4.0
    # High-priority vessels should not wait — low feasibility
    feasibility = max(round(70 - (priority - 1) * 15, 1), 5.0)
    congestion_reduction = round(min(wait_hours / 12 * 35, 35), 1)
    anchorage = ANCHORAGE_AREAS[priority % len(ANCHORAGE_AREAS)]

    return RoutingAlternative(
        option_rank=2,
        action_type="anchor_and_wait",
        description=(
            f"Proceed to {anchorage} and hold for approximately {wait_hours:.0f} hours "
            f"until a berth window becomes available."
        ),
        estimated_delay_hours=wait_hours,
        congestion_reduction_pct=congestion_reduction,
        feasibility_score=feasibility,
        trade_offs=(
            f"Approximately {wait_hours:.0f}h delay. Anchorage fees apply. "
            f"Suitable for lower-priority and non-time-sensitive cargo. "
            f"Reduces berth pressure immediately."
        ),
    )


def _build_terminal_transfer(
    vessel_type: str,
    current_terminal: Optional[str],
    alt_terminal: Optional[str],
    priority: int,
    risk_score: float,
) -> RoutingAlternative:
    """
    Redirect vessel to the alternative terminal within the port.
    Only feasible if the vessel type is compatible with the other terminal.
    """
    if alt_terminal:
        desc = (
            f"Redirect vessel from {current_terminal} to {alt_terminal}. "
            f"This distributes traffic across terminals and reduces hotspot pressure."
        )
        feasibility = round(max(60 - (priority - 1) * 8, 15.0), 1)
    else:
        desc = (
            "No compatible alternative terminal available within this port for this vessel type. "
            "Consider adjacent port diversion."
        )
        feasibility = 15.0

    return RoutingAlternative(
        option_rank=3,
        action_type="terminal_transfer",
        description=desc,
        estimated_delay_hours=2.0,
        congestion_reduction_pct=round(min(risk_score * 0.3, 30), 1),
        feasibility_score=feasibility,
        trade_offs=(
            "Requires coordination with terminal operators and port authority. "
            "2-4h delay for reberthing logistics. May affect cargo handling equipment availability."
        ),
    )


def _build_divert_anchorage(
    vessel_type: str,
    priority: int,
    risk_score: float,
) -> RoutingAlternative:
    """Only generated for CRITICAL risk vessels as a last resort."""
    anchorage = ANCHORAGE_AREAS[0]
    feasibility = max(round(85 - (priority - 1) * 10, 1), 20.0)

    return RoutingAlternative(
        option_rank=4,
        action_type="divert_to_anchorage",
        description=(
            f"CRITICAL: Divert immediately to {anchorage} and await port authority "
            f"clearance. Do not enter port approaches until berth confirmed."
        ),
        estimated_delay_hours=12.0,
        congestion_reduction_pct=40.0,
        feasibility_score=feasibility,
        trade_offs=(
            "Significant delay (12+ hours). Requires port authority coordination. "
            "Recommended only when congestion is CRITICAL and no other option available."
        ),
    )


def compute_routing_recommendations(db: Session) -> RoutingRecommendationResponse:
    now = datetime.now(timezone.utc)

    # Get vessel risk assessments
    risk_result = compute_vessel_risks(db)

    # Load berths for terminal info
    berths: list[Berth] = db.query(Berth).all()
    berth_by_id: dict[int, Berth] = {b.id: b for b in berths}

    # Build terminal → alt_terminal map
    terminals = list({b.terminal for b in berths})
    alt_terminal_map: dict[str, Optional[str]] = {}
    for t in terminals:
        others = [x for x in terminals if x != t]
        alt_terminal_map[t] = others[0] if others else None

    # Load schedules to get berth assignments
    horizon_end = now + timedelta(hours=HORIZON_HOURS)
    schedules: list[VesselSchedule] = (
        db.query(VesselSchedule)
        .options(joinedload(VesselSchedule.berth))
        .filter(
            VesselSchedule.eta <= horizon_end,
            VesselSchedule.status.notin_(["cancelled", "completed"]),
        )
        .all()
    )
    schedule_by_vessel: dict[int, VesselSchedule] = {}
    for s in schedules:
        if s.vessel_id not in schedule_by_vessel:
            schedule_by_vessel[s.vessel_id] = s

    recommendations: list[RoutingRecommendation] = []

    for vessel_risk in risk_result.vessels:
        if vessel_risk.risk_score < RISK_THRESHOLD:
            continue  # Only generate routing for significant risk vessels

        sched = schedule_by_vessel.get(vessel_risk.vessel_id)
        priority = sched.priority if sched else 3
        berth_code = vessel_risk.berth_code
        current_terminal: Optional[str] = None
        alt_terminal: Optional[str] = None

        if sched and sched.berth_id:
            berth = berth_by_id.get(sched.berth_id)
            if berth:
                current_terminal = berth.terminal
                alt_terminal = alt_terminal_map.get(current_terminal)

        # Congestion driver description
        top_factor = max(vessel_risk.factors, key=lambda f: f.contribution)
        congestion_driver = f"{top_factor.name}: {top_factor.description}"

        # Build alternatives
        alternatives: list[RoutingAlternative] = [
            _build_speed_reduction(
                vessel_risk.vessel_type, priority,
                vessel_risk.delay_hours, vessel_risk.risk_score
            ),
            _build_anchor_and_wait(
                vessel_risk.vessel_type, priority, vessel_risk.risk_score
            ),
            _build_terminal_transfer(
                vessel_risk.vessel_type, current_terminal, alt_terminal,
                priority, vessel_risk.risk_score
            ),
        ]
        if vessel_risk.risk_level == "CRITICAL":
            alternatives.append(
                _build_divert_anchorage(
                    vessel_risk.vessel_type, priority, vessel_risk.risk_score
                )
            )

        # Recommended action = highest feasibility alternative
        best_alt = max(alternatives, key=lambda a: a.feasibility_score)
        recommended = (
            f"Recommended: {best_alt.action_type.replace('_', ' ').title()}. "
            f"{best_alt.description}"
        )

        recommendations.append(
            RoutingRecommendation(
                vessel_id=vessel_risk.vessel_id,
                vessel_name=vessel_risk.vessel_name,
                vessel_type=vessel_risk.vessel_type,
                current_risk_level=vessel_risk.risk_level,
                current_risk_score=vessel_risk.risk_score,
                eta=vessel_risk.eta,
                assigned_berth_code=berth_code,
                congestion_driver=congestion_driver,
                alternatives=alternatives,
                recommended_action=recommended,
                data_notice=DATA_NOTICE,
            )
        )

    summary = (
        f"{len(recommendations)} vessel(s) identified for alternative routing "
        f"(risk score >= {RISK_THRESHOLD:.0f}). "
        f"All recommendations are based on simulated port data."
    )

    return RoutingRecommendationResponse(
        computed_at=now,
        total_vessels_affected=len(recommendations),
        recommendations=recommendations,
        summary=summary,
    )

"""
72-Hour Operations Plan Generator
====================================
Aggregates all Phase 2 + Phase 3 findings into a single prioritized action
list that a port supervisor can use directly.

Plan items are sourced from:
  1. CRITICAL/HIGH vessel risks (from risk_detector)
  2. CRITICAL/HIGH congestion hotspots (from hotspot_finder)
  3. Berth conflicts — vessels with no available berth (from assignment_optimizer)
  4. Crane shortfalls — vessels with insufficient cranes (from crane_optimizer)
  5. Routing recommendations — HIGH/CRITICAL vessels needing re-routing

Each item has:
  - priority_level: CRITICAL | HIGH | MEDIUM | LOW
  - action_type: one of the five source categories
  - time_window: when the issue occurs
  - area: berth / terminal / vessel name
  - issue: one-sentence problem
  - recommended_action: one-sentence action

Items are sorted: CRITICAL first, then HIGH, then by earliest time_window.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from schemas.optimization import OperationsPlanResponse, PlanItem
from services.assignment_optimizer import compute_berth_assignments
from services.congestion_predictor import compute_congestion
from services.crane_optimizer import compute_crane_assignments
from services.hotspot_finder import compute_hotspots
from services.risk_detector import compute_vessel_risks
from services.routing_recommender import compute_routing_recommendations

HORIZON_HOURS = 72
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _level_to_plan_priority(level: str) -> str:
    return level if level in PRIORITY_ORDER else "LOW"


def compute_operations_plan(db: Session) -> OperationsPlanResponse:
    now = datetime.now(timezone.utc)
    plan_end = now + timedelta(hours=HORIZON_HOURS)

    items: list[PlanItem] = []
    item_id = 1

    # ------------------------------------------------------------------
    # Source 1: HIGH + CRITICAL vessel risks
    # ------------------------------------------------------------------
    risk_result = compute_vessel_risks(db)
    for v in risk_result.vessels:
        if v.risk_level not in ("HIGH", "CRITICAL"):
            continue
        window_start = _ensure_utc(v.eta) if v.eta else now
        window_end = window_start + timedelta(hours=6)
        top_factor = max(v.factors, key=lambda f: f.contribution)

        items.append(PlanItem(
            item_id=item_id,
            priority_rank=0,  # filled in after sort
            priority_level=v.risk_level,
            action_type="vessel_risk",
            time_window_start=window_start,
            time_window_end=window_end,
            area=v.berth_code or "Unassigned",
            issue=(
                f"{v.vessel_name} ({v.vessel_type}) has {v.risk_level} congestion risk "
                f"(score {v.risk_score:.0f}/100). "
                f"Key driver: {top_factor.name}."
            ),
            recommended_action=v.recommendation,
            reason=top_factor.description,
            affected_vessel=v.vessel_name,
            affected_berth=v.berth_code,
        ))
        item_id += 1

    # ------------------------------------------------------------------
    # Source 2: HIGH + CRITICAL hotspots
    # ------------------------------------------------------------------
    hotspot_result = compute_hotspots(db)
    for h in hotspot_result.hotspots:
        if h.severity not in ("HIGH", "CRITICAL"):
            continue
        # Time window: now to now+24h (hotspots are near-term)
        window_start = now
        window_end = now + timedelta(hours=24)
        first_vessel = h.affected_vessels[0].vessel_name if h.affected_vessels else "Multiple vessels"

        items.append(PlanItem(
            item_id=item_id,
            priority_rank=0,
            priority_level=h.severity,
            action_type="hotspot",
            time_window_start=window_start,
            time_window_end=window_end,
            area=f"{h.berth_code} ({h.terminal})",
            issue=(
                f"Berth {h.berth_code} is a {h.severity} congestion hotspot "
                f"(score {h.hotspot_score:.0f}/100). "
                f"{h.scheduled_vessel_count} vessel(s) scheduled, "
                f"{h.overlap_hours:.0f}h of overlap detected."
            ),
            recommended_action=(
                f"Redistribute vessel arrivals at {h.berth_code}. "
                f"Reallocate {max(0, h.required_crane_count - h.available_crane_count)} "
                f"additional crane(s). Review schedule for {first_vessel}."
            ),
            reason=h.reasons[0] if h.reasons else "Berth overloaded",
            affected_vessel=first_vessel,
            affected_berth=h.berth_code,
        ))
        item_id += 1

    # ------------------------------------------------------------------
    # Source 3: Berth assignment conflicts (unassignable or change required)
    # ------------------------------------------------------------------
    berth_result = compute_berth_assignments(db)
    for rec in berth_result.recommendations:
        if rec.unassignable_count if hasattr(rec, "unassignable_count") else False:
            continue
        # Only flag if a change is strongly needed (fit_score < 40)
        if not rec.change_required and rec.fit_score >= 40:
            continue
        if rec.fit_score == 0:
            level = "CRITICAL"
            issue = f"No suitable berth found for {rec.vessel_name} ({rec.vessel_type})."
            action = "Coordinate special berthing arrangement with terminal operations."
        elif rec.change_required:
            level = "HIGH" if rec.fit_score < 50 else "MEDIUM"
            issue = (
                f"{rec.vessel_name} currently assigned to {rec.current_berth_code}. "
                f"Recommended reassignment to {rec.recommended_berth_code} "
                f"(fit score improvement)."
            )
            action = (
                f"Reassign {rec.vessel_name} from {rec.current_berth_code} "
                f"to {rec.recommended_berth_code} ({rec.recommended_terminal})."
            )
        else:
            continue

        window_start = _ensure_utc(rec.eta)
        window_end = _ensure_utc(rec.etd) if rec.etd else window_start + timedelta(hours=24)

        items.append(PlanItem(
            item_id=item_id,
            priority_rank=0,
            priority_level=level,
            action_type="berth_conflict",
            time_window_start=window_start,
            time_window_end=window_end,
            area=rec.current_berth_code or "Unassigned",
            issue=issue,
            recommended_action=action,
            reason=rec.reason,
            affected_vessel=rec.vessel_name,
            affected_berth=rec.current_berth_code,
        ))
        item_id += 1

    # ------------------------------------------------------------------
    # Source 4: Crane shortfalls
    # ------------------------------------------------------------------
    crane_result = compute_crane_assignments(db)
    for rec in crane_result.recommendations:
        if rec.cranes_shortfall == 0:
            continue
        level = "CRITICAL" if rec.cranes_shortfall >= 2 else "HIGH"
        window_start = _ensure_utc(rec.eta)
        window_end = window_start + timedelta(hours=12)

        items.append(PlanItem(
            item_id=item_id,
            priority_rank=0,
            priority_level=level,
            action_type="crane_shortage",
            time_window_start=window_start,
            time_window_end=window_end,
            area=rec.berth_code or "Unassigned",
            issue=(
                f"Crane shortfall for {rec.vessel_name} at {rec.berth_code}: "
                f"{rec.cranes_required} required, "
                f"{rec.cranes_required - rec.cranes_shortfall} available."
            ),
            recommended_action=(
                rec.shortfall_warning or
                f"Redeploy {rec.cranes_shortfall} crane(s) to {rec.berth_code} "
                f"before {window_start.strftime('%d %b %H:%M')}."
            ),
            reason=rec.reason,
            affected_vessel=rec.vessel_name,
            affected_berth=rec.berth_code,
        ))
        item_id += 1

    # ------------------------------------------------------------------
    # Source 5: Routing recommendations (CRITICAL only in plan)
    # ------------------------------------------------------------------
    routing_result = compute_routing_recommendations(db)
    for rec in routing_result.recommendations:
        if rec.current_risk_level != "CRITICAL":
            continue
        window_start = _ensure_utc(rec.eta) if rec.eta else now
        window_end = window_start + timedelta(hours=6)
        best_alt = max(rec.alternatives, key=lambda a: a.feasibility_score)

        items.append(PlanItem(
            item_id=item_id,
            priority_rank=0,
            priority_level="CRITICAL",
            action_type="routing",
            time_window_start=window_start,
            time_window_end=window_end,
            area=rec.assigned_berth_code or "Approaching port",
            issue=(
                f"CRITICAL routing conflict: {rec.vessel_name} at high congestion risk "
                f"(score {rec.current_risk_score:.0f}/100). {rec.congestion_driver[:80]}."
            ),
            recommended_action=rec.recommended_action[:200],
            reason=f"Risk level {rec.current_risk_level}. Best option: {best_alt.action_type}",
            affected_vessel=rec.vessel_name,
            affected_berth=rec.assigned_berth_code,
        ))
        item_id += 1

    # ------------------------------------------------------------------
    # Sort: CRITICAL first, then HIGH, then by earliest time window
    # ------------------------------------------------------------------
    items.sort(key=lambda x: (
        PRIORITY_ORDER.get(x.priority_level, 3),
        x.time_window_start,
    ))

    # Assign sequential priority_rank after sort
    for rank, item in enumerate(items, start=1):
        item.priority_rank = rank

    # Re-number item_ids to be sequential after sort
    for idx, item in enumerate(items, start=1):
        item.item_id = idx

    critical_count = sum(1 for i in items if i.priority_level == "CRITICAL")
    high_count = sum(1 for i in items if i.priority_level == "HIGH")

    # Executive summary
    congestion = compute_congestion(db)
    if critical_count > 0:
        exec_summary = (
            f"IMMEDIATE ACTION REQUIRED. {critical_count} CRITICAL and {high_count} HIGH "
            f"priority issue(s) identified across the 72-hour planning horizon. "
            f"Port-wide congestion is {congestion.overall_level} "
            f"(score {congestion.overall_score}/100). "
            f"Peak congestion expected {congestion.peak_window_start.strftime('%d %b %H:%M') if congestion.peak_window_start else 'N/A'}. "
            f"Priority actions: address hotspot berths, resolve crane shortfalls, "
            f"and reroute CRITICAL vessels."
        )
    elif high_count > 0:
        exec_summary = (
            f"{high_count} HIGH priority issue(s) require attention. "
            f"Port-wide congestion is {congestion.overall_level} "
            f"(score {congestion.overall_score}/100). "
            f"Monitor berth assignments and crane allocations closely."
        )
    else:
        exec_summary = (
            f"Port operations are within normal parameters. "
            f"Congestion level: {congestion.overall_level} "
            f"(score {congestion.overall_score}/100). "
            f"{len(items)} routine action(s) flagged for the 72-hour window."
        )

    return OperationsPlanResponse(
        generated_at=now,
        plan_horizon_hours=HORIZON_HOURS,
        plan_end=plan_end,
        total_items=len(items),
        critical_items=critical_count,
        high_items=high_count,
        items=items,
        executive_summary=exec_summary,
    )

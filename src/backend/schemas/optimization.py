"""
Phase 3 optimization schemas — responses for berth/crane assignments,
alternative routing recommendations, and the 72-hour operations plan.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Berth Assignment
# ---------------------------------------------------------------------------
class BerthFitScore(BaseModel):
    """How well a candidate berth fits the vessel."""
    berth_id: int
    berth_code: str
    terminal: str
    fit_score: float                # 0–100
    compatibility: bool             # passes all hard constraints
    availability: bool              # not double-booked in the time window
    compatibility_notes: str        # e.g. "Draft OK, length OK, type OK"
    availability_notes: str         # e.g. "Berth free 14:00-22:00"


class BerthAssignmentRecommendation(BaseModel):
    schedule_id: int
    vessel_id: int
    vessel_name: str
    vessel_type: str
    eta: datetime
    etd: Optional[datetime] = None
    current_berth_code: Optional[str] = None  # existing assignment if any
    recommended_berth_code: str
    recommended_berth_id: int
    recommended_terminal: str
    fit_score: float                # 0–100 for recommended berth
    change_required: bool           # False when current == recommended
    reason: str                     # plain-English explanation
    alternative_berths: List[BerthFitScore]  # next-best options


class BerthAssignmentResponse(BaseModel):
    computed_at: datetime
    total_recommendations: int
    unassignable_count: int         # vessels with no suitable berth found
    recommendations: List[BerthAssignmentRecommendation]
    summary: str


# ---------------------------------------------------------------------------
# Crane Assignment
# ---------------------------------------------------------------------------
class CraneAssignmentDetail(BaseModel):
    crane_id: int
    crane_code: str
    crane_type: str
    berth_code: Optional[str] = None
    reason: str


class CraneAssignmentRecommendation(BaseModel):
    schedule_id: int
    vessel_id: int
    vessel_name: str
    vessel_type: str
    eta: datetime
    berth_code: Optional[str] = None
    cranes_required: int
    cranes_recommended: List[CraneAssignmentDetail]
    cranes_shortfall: int           # > 0 means not enough cranes available
    shortfall_warning: Optional[str] = None
    reason: str


class CraneAssignmentResponse(BaseModel):
    computed_at: datetime
    total_recommendations: int
    shortfall_count: int            # vessels with a crane shortage
    recommendations: List[CraneAssignmentRecommendation]
    summary: str


# ---------------------------------------------------------------------------
# Alternative Routing
# ---------------------------------------------------------------------------
class RoutingAlternative(BaseModel):
    option_rank: int                # 1 = best option
    action_type: str                # speed_reduction | anchor_and_wait | terminal_transfer | divert_to_anchorage
    description: str
    estimated_delay_hours: float
    congestion_reduction_pct: float # expected reduction in berth pressure
    feasibility_score: float        # 0–100
    trade_offs: str


class RoutingRecommendation(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_type: str
    current_risk_level: str
    current_risk_score: float
    eta: Optional[datetime] = None
    assigned_berth_code: Optional[str] = None
    congestion_driver: str          # reason routing is needed
    alternatives: List[RoutingAlternative]
    recommended_action: str         # summary of best option
    data_notice: str                # prototype disclaimer


class RoutingRecommendationResponse(BaseModel):
    computed_at: datetime
    total_vessels_affected: int
    recommendations: List[RoutingRecommendation]
    summary: str


# ---------------------------------------------------------------------------
# 72-Hour Operations Plan
# ---------------------------------------------------------------------------
class PlanItem(BaseModel):
    item_id: int
    priority_rank: int              # 1 = most urgent
    priority_level: str             # CRITICAL | HIGH | MEDIUM | LOW
    action_type: str                # berth_conflict | crane_shortage | vessel_risk | routing | hotspot
    time_window_start: datetime
    time_window_end: datetime
    area: str                       # berth code / terminal / vessel name
    issue: str                      # one-sentence problem description
    recommended_action: str         # one-sentence action
    reason: str                     # why this is flagged
    affected_vessel: Optional[str] = None
    affected_berth: Optional[str] = None


class OperationsPlanResponse(BaseModel):
    generated_at: datetime
    plan_horizon_hours: int
    plan_end: datetime
    total_items: int
    critical_items: int
    high_items: int
    items: List[PlanItem]
    executive_summary: str

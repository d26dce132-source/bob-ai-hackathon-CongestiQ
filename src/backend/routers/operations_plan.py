"""
GET /api/operations-plan  — prioritized 72-hour port operations plan
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.optimization import OperationsPlanResponse
from services.operations_plan import compute_operations_plan

router = APIRouter(prefix="/operations-plan", tags=["operations-plan"])


@router.get("", response_model=OperationsPlanResponse)
def get_operations_plan(db: Session = Depends(get_db)):
    """
    Generate a prioritized **72-hour port operations plan** aggregating all
    Phase 2 and Phase 3 findings.

    Plan items are sourced from:
    - **vessel_risk** — HIGH/CRITICAL vessels needing immediate attention
    - **hotspot** — HIGH/CRITICAL congestion hotspots at berths
    - **berth_conflict** — vessels with no suitable berth or suboptimal assignments
    - **crane_shortage** — vessels facing a crane shortfall
    - **routing** — CRITICAL vessels requiring alternative routing

    Items are sorted CRITICAL first, then HIGH, then by earliest time window.

    The `executive_summary` provides a one-paragraph brief for port supervisors.
    """
    return compute_operations_plan(db)

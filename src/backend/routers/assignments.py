"""
GET /api/assignments         — berth assignment recommendations
GET /api/assignments/cranes  — crane assignment recommendations
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.optimization import BerthAssignmentResponse, CraneAssignmentResponse
from services.assignment_optimizer import compute_berth_assignments
from services.crane_optimizer import compute_crane_assignments

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=BerthAssignmentResponse)
def get_berth_assignments(db: Session = Depends(get_db)):
    """
    Evaluate all vessel schedules in the next **72 hours** and recommend the
    optimal berth for each vessel.

    Each recommendation includes:
    - `recommended_berth_code` and `recommended_terminal`
    - `fit_score` (0–100) — how well the berth suits this vessel
    - `change_required` — whether the current assignment should be changed
    - `reason` — plain-English explanation
    - `alternative_berths` — up to 3 next-best options

    Vessels with no compatible berth are flagged as unassignable.
    """
    return compute_berth_assignments(db)


@router.get("/cranes", response_model=CraneAssignmentResponse)
def get_crane_assignments(db: Session = Depends(get_db)):
    """
    Evaluate all vessel schedules in the next **72 hours** and recommend
    which cranes should be assigned to each vessel's cargo operations.

    Each recommendation includes:
    - `cranes_recommended` — list of recommended crane codes and types
    - `cranes_required` vs `cranes_shortfall` — identifies shortage situations
    - `shortfall_warning` — raised when not enough cranes are available
    - `reason` — plain-English explanation

    Results are ordered by vessel ETA (earliest first).
    """
    return compute_crane_assignments(db)

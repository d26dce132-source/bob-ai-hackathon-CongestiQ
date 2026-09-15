"""
GET /api/vessels/risk   — risk scores for all vessels with upcoming schedules
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from db.database import get_db
from schemas.prediction import VesselRiskListResponse
from services.risk_detector import compute_vessel_risks

router = APIRouter(prefix="/vessels", tags=["vessel-risk"])


@router.get("/risk", response_model=VesselRiskListResponse)
def get_vessel_risks(
    risk_level: Optional[str] = Query(
        None,
        description="Filter by risk level: LOW | MEDIUM | HIGH | CRITICAL",
    ),
    db: Session = Depends(get_db),
):
    """
    Compute congestion/delay risk for every vessel with an active schedule
    in the next **72 hours**.

    Each vessel receives:
    - `risk_score` (0–100) and `risk_level` (LOW / MEDIUM / HIGH / CRITICAL)
    - `factors` — five explainable sub-scores
    - `recommendation` — a short action sentence for port operators

    Results are sorted highest-risk first.
    Optionally filter by `risk_level` to focus on vessels needing attention.
    """
    result = compute_vessel_risks(db)
    if risk_level:
        level_upper = risk_level.upper()
        result.vessels = [v for v in result.vessels if v.risk_level == level_upper]
        result.total = len(result.vessels)
    return result

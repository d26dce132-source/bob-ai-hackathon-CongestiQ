"""
GET /api/routing/recommendations  — alternative routing for high-risk vessels
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.optimization import RoutingRecommendationResponse
from services.routing_recommender import compute_routing_recommendations

router = APIRouter(prefix="/routing", tags=["routing"])


@router.get("/recommendations", response_model=RoutingRecommendationResponse)
def get_routing_recommendations(db: Session = Depends(get_db)):
    """
    Generate alternative routing recommendations for vessels with **HIGH** or
    **CRITICAL** congestion risk (risk score >= 50).

    Each recommendation includes:
    - `current_risk_level` and `current_risk_score`
    - `congestion_driver` — the primary reason routing is needed
    - `alternatives` — up to 4 ranked options:
        - Speed reduction (shift ETA)
        - Anchor and wait
        - Terminal transfer
        - Divert to anchorage (CRITICAL only)
    - `recommended_action` — the single best option for port operators
    - `data_notice` — prototype disclaimer (simulated data)

    Results are based on simulated port operational data.
    """
    return compute_routing_recommendations(db)

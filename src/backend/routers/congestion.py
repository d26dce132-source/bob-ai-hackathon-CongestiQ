"""
GET /api/congestion          — port-wide congestion prediction
GET /api/congestion/hotspots — berth-level congestion hotspots
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.prediction import CongestionPredictionResponse, HotspotListResponse
from services.congestion_predictor import compute_congestion
from services.hotspot_finder import compute_hotspots

router = APIRouter(prefix="/congestion", tags=["congestion"])


@router.get("", response_model=CongestionPredictionResponse)
def get_congestion_prediction(db: Session = Depends(get_db)):
    """
    Compute port-wide congestion prediction for the next **72 hours**.

    Returns:
    - `overall_score` (0–100) and classification level
    - `peak_window` — when the worst congestion is expected
    - `factors` — explainable breakdown of each contributing factor
    - `window_scores` — score for each 6-hour window in the horizon
    - `summary` — plain-English one-sentence explanation
    """
    return compute_congestion(db)


@router.get("/hotspots", response_model=HotspotListResponse)
def get_hotspots(db: Session = Depends(get_db)):
    """
    Identify berths where congestion is likely to develop in the next **72 hours**.

    Returns a ranked list of hotspot berths with:
    - `hotspot_score` (0–100) and severity level
    - Schedule overlap hours
    - Crane demand vs supply
    - Affected vessels with their ETAs and priorities
    - Plain-English reasons for each hotspot
    """
    return compute_hotspots(db)

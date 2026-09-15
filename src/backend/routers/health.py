"""
GET /api/health — detailed health check including database row counts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Berth, Crane, Vessel, VesselSchedule
from schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def api_health(db: Session = Depends(get_db)):
    """
    Returns API and database status plus row counts for each table.
    Useful for quickly confirming the database is seeded and reachable.
    """
    try:
        vessel_count = db.query(Vessel).count()
        berth_count = db.query(Berth).count()
        crane_count = db.query(Crane).count()
        schedule_count = db.query(VesselSchedule).count()
        db_status = "ok"
    except Exception as exc:  # pragma: no cover
        return HealthResponse(
            status="degraded",
            service="congestiq-api",
            database=f"error: {exc}",
            vessel_count=0,
            berth_count=0,
            crane_count=0,
            schedule_count=0,
        )

    return HealthResponse(
        status="ok",
        service="congestiq-api",
        database=db_status,
        vessel_count=vessel_count,
        berth_count=berth_count,
        crane_count=crane_count,
        schedule_count=schedule_count,
    )

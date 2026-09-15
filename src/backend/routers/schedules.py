"""
GET /api/schedules   — list vessel schedules with filtering
GET /api/schedules/{id}  — single schedule detail
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from db.models import Vessel, VesselSchedule, Berth
from schemas import ScheduleListResponse, VesselScheduleResponse

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _enrich(schedule: VesselSchedule) -> VesselScheduleResponse:
    """Map ORM row to response schema, adding denormalised vessel/berth names."""
    data = VesselScheduleResponse.model_validate(schedule)
    data.vessel_name = schedule.vessel.name if schedule.vessel else None
    data.vessel_type = schedule.vessel.vessel_type if schedule.vessel else None
    data.berth_code = schedule.berth.code if schedule.berth else None
    return data


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    status: Optional[str] = Query(None, description="Filter by schedule status"),
    vessel_id: Optional[int] = Query(None, description="Filter by vessel ID"),
    berth_id: Optional[int] = Query(None, description="Filter by berth ID"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Filter by priority (1-5)"),
    window_hours: Optional[int] = Query(
        72, ge=0, le=9999,
        description="Only return schedules with ETA within this many hours from now (0 = no limit)"
    ),
    db: Session = Depends(get_db),
):
    """
    Return vessel schedules, ordered by ETA ascending.

    By default returns schedules with ETA within the next **72 hours**.
    Pass `window_hours=0` to disable the time filter and return all schedules.

    Valid statuses: `scheduled`, `in_port`, `completed`, `cancelled`, `delayed`
    """
    query = db.query(VesselSchedule).options(
        joinedload(VesselSchedule.vessel),
        joinedload(VesselSchedule.berth),
    )

    if status:
        query = query.filter(VesselSchedule.status == status)
    if vessel_id is not None:
        query = query.filter(VesselSchedule.vessel_id == vessel_id)
    if berth_id is not None:
        query = query.filter(VesselSchedule.berth_id == berth_id)
    if priority is not None:
        query = query.filter(VesselSchedule.priority == priority)
    if window_hours and window_hours > 0:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = now + timedelta(hours=window_hours)
        query = query.filter(VesselSchedule.eta <= cutoff)

    schedules = query.order_by(VesselSchedule.eta).all()
    enriched = [_enrich(s) for s in schedules]
    return ScheduleListResponse(total=len(enriched), schedules=enriched)


@router.get("/{schedule_id}", response_model=VesselScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Return a single vessel schedule by its database ID."""
    schedule = (
        db.query(VesselSchedule)
        .options(
            joinedload(VesselSchedule.vessel),
            joinedload(VesselSchedule.berth),
        )
        .filter(VesselSchedule.id == schedule_id)
        .first()
    )
    if schedule is None:
        raise HTTPException(
            status_code=404, detail=f"Schedule {schedule_id} not found"
        )
    return _enrich(schedule)

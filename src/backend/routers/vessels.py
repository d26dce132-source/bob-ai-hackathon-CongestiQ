"""
GET /api/vessels  — list all vessels with optional filtering
GET /api/vessels/{id}  — single vessel detail
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Vessel
from schemas import VesselListResponse, VesselResponse

router = APIRouter(prefix="/vessels", tags=["vessels"])


@router.get("", response_model=VesselListResponse)
def list_vessels(
    status: Optional[str] = Query(None, description="Filter by vessel status"),
    vessel_type: Optional[str] = Query(None, description="Filter by vessel type"),
    db: Session = Depends(get_db),
):
    """
    Return all vessels, optionally filtered by **status** or **vessel_type**.

    Valid statuses: `en_route`, `anchored`, `berthing`, `berthed`, `departing`, `departed`
    Valid types: `container`, `bulk_carrier`, `tanker`, `roro`, `general_cargo`
    """
    query = db.query(Vessel)
    if status:
        query = query.filter(Vessel.status == status)
    if vessel_type:
        query = query.filter(Vessel.vessel_type == vessel_type)

    vessels = query.order_by(Vessel.name).all()
    return VesselListResponse(total=len(vessels), vessels=vessels)


@router.get("/{vessel_id}", response_model=VesselResponse)
def get_vessel(vessel_id: int, db: Session = Depends(get_db)):
    """Return a single vessel by its database ID."""
    vessel = db.query(Vessel).filter(Vessel.id == vessel_id).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")
    return vessel

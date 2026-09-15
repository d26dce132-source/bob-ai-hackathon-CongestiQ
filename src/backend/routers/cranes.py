"""
GET /api/cranes   — list all cranes with optional filtering
GET /api/cranes/{id}  — single crane detail
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Crane
from schemas import CraneListResponse, CraneResponse

router = APIRouter(prefix="/cranes", tags=["cranes"])


@router.get("", response_model=CraneListResponse)
def list_cranes(
    status: Optional[str] = Query(None, description="Filter by crane status"),
    crane_type: Optional[str] = Query(None, description="Filter by crane type"),
    berth_id: Optional[int] = Query(None, description="Filter by assigned berth"),
    db: Session = Depends(get_db),
):
    """
    Return all cranes, optionally filtered by **status**, **crane_type**, or **berth_id**.

    Valid statuses: `available`, `in_use`, `maintenance`, `offline`
    Valid types: `quay_crane`, `mobile_crane`, `reach_stacker`, `gantry_crane`
    """
    query = db.query(Crane)
    if status:
        query = query.filter(Crane.status == status)
    if crane_type:
        query = query.filter(Crane.crane_type == crane_type)
    if berth_id is not None:
        query = query.filter(Crane.berth_id == berth_id)

    cranes = query.order_by(Crane.code).all()
    return CraneListResponse(total=len(cranes), cranes=cranes)


@router.get("/{crane_id}", response_model=CraneResponse)
def get_crane(crane_id: int, db: Session = Depends(get_db)):
    """Return a single crane by its database ID."""
    crane = db.query(Crane).filter(Crane.id == crane_id).first()
    if crane is None:
        raise HTTPException(status_code=404, detail=f"Crane {crane_id} not found")
    return crane

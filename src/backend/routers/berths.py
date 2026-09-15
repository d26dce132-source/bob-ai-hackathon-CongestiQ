"""
GET /api/berths   — list all berths with optional filtering
GET /api/berths/{id}  — single berth detail
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Berth
from schemas import BerthListResponse, BerthResponse

router = APIRouter(prefix="/berths", tags=["berths"])


@router.get("", response_model=BerthListResponse)
def list_berths(
    status: Optional[str] = Query(None, description="Filter by berth status"),
    terminal: Optional[str] = Query(None, description="Filter by terminal name"),
    db: Session = Depends(get_db),
):
    """
    Return all berths, optionally filtered by **status** or **terminal**.

    Valid statuses: `available`, `occupied`, `maintenance`, `reserved`
    """
    query = db.query(Berth)
    if status:
        query = query.filter(Berth.status == status)
    if terminal:
        query = query.filter(Berth.terminal.ilike(f"%{terminal}%"))

    berths = query.order_by(Berth.code).all()
    return BerthListResponse(total=len(berths), berths=berths)


@router.get("/{berth_id}", response_model=BerthResponse)
def get_berth(berth_id: int, db: Session = Depends(get_db)):
    """Return a single berth by its database ID."""
    berth = db.query(Berth).filter(Berth.id == berth_id).first()
    if berth is None:
        raise HTTPException(status_code=404, detail=f"Berth {berth_id} not found")
    return berth

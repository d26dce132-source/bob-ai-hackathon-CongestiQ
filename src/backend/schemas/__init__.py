"""
Pydantic schemas for API request/response validation.

These are separate from the ORM models so each layer can evolve independently.
All response schemas use `from_attributes = True` (replaces orm_mode in Pydantic v2).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Vessel schemas
# ---------------------------------------------------------------------------
class VesselBase(BaseModel):
    name: str
    imo_number: str
    call_sign: Optional[str] = None
    flag: Optional[str] = None
    vessel_type: str
    operator: Optional[str] = None
    length_m: float
    beam_m: float
    draft_m: float
    gross_tonnage: int
    teu_capacity: Optional[int] = None
    status: str


class VesselResponse(VesselBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class VesselListResponse(BaseModel):
    total: int
    vessels: List[VesselResponse]


# ---------------------------------------------------------------------------
# Berth schemas
# ---------------------------------------------------------------------------
class BerthBase(BaseModel):
    code: str
    terminal: str
    name: str
    length_m: float
    max_draft_m: float
    vessel_types_allowed: str
    has_shore_power: bool
    status: str


class BerthResponse(BerthBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class BerthListResponse(BaseModel):
    total: int
    berths: List[BerthResponse]


# ---------------------------------------------------------------------------
# Crane schemas
# ---------------------------------------------------------------------------
class CraneBase(BaseModel):
    code: str
    name: str
    crane_type: str
    max_lift_tonnes: float
    outreach_m: Optional[float] = None
    berth_id: Optional[int] = None
    status: str


class CraneResponse(CraneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CraneListResponse(BaseModel):
    total: int
    cranes: List[CraneResponse]


# ---------------------------------------------------------------------------
# VesselSchedule schemas
# ---------------------------------------------------------------------------
class VesselScheduleBase(BaseModel):
    vessel_id: int
    berth_id: Optional[int] = None
    eta: datetime
    etd: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    cargo_type: Optional[str] = None
    cargo_volume_teu: Optional[int] = None
    cargo_weight_tonnes: Optional[float] = None
    status: str
    priority: int
    delay_hours: float
    port_of_origin: Optional[str] = None
    next_port: Optional[str] = None


class VesselScheduleResponse(VesselScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    # Nested vessel name for convenience
    vessel_name: Optional[str] = None
    vessel_type: Optional[str] = None
    berth_code: Optional[str] = None


class ScheduleListResponse(BaseModel):
    total: int
    schedules: List[VesselScheduleResponse]


# ---------------------------------------------------------------------------
# Health schema
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
    vessel_count: int
    berth_count: int
    crane_count: int
    schedule_count: int

"""
SQLAlchemy ORM models for CongestiQ.

Tables
------
- vessels        : ships that call at the port
- berths         : docking positions at the port
- cranes         : cargo-handling equipment assigned to berths
- vessel_schedules : planned arrival/departure events for vessels
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


# ---------------------------------------------------------------------------
# Vessel
# ---------------------------------------------------------------------------
class Vessel(Base):
    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Identity
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    imo_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    call_sign: Mapped[str] = mapped_column(String(20), nullable=True)
    flag: Mapped[str] = mapped_column(String(60), nullable=True)

    # Classification
    vessel_type: Mapped[str] = mapped_column(
        String(60), nullable=False
    )  # container | bulk_carrier | tanker | roro | general_cargo
    operator: Mapped[str] = mapped_column(String(120), nullable=True)

    # Physical dimensions
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    beam_m: Mapped[float] = mapped_column(Float, nullable=False)
    draft_m: Mapped[float] = mapped_column(Float, nullable=False)
    gross_tonnage: Mapped[int] = mapped_column(Integer, nullable=False)
    teu_capacity: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # only for container ships

    # Current status
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="en_route"
    )  # en_route | anchored | berthing | berthed | departing | departed

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    schedules: Mapped[list["VesselSchedule"]] = relationship(
        "VesselSchedule", back_populates="vessel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vessel id={self.id} name={self.name!r} type={self.vessel_type}>"


# ---------------------------------------------------------------------------
# Berth
# ---------------------------------------------------------------------------
class Berth(Base):
    __tablename__ = "berths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    terminal: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Physical limits
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    max_draft_m: Mapped[float] = mapped_column(Float, nullable=False)

    # Capabilities
    vessel_types_allowed: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # comma-separated list, e.g. "container,roro"
    has_shore_power: Mapped[bool] = mapped_column(Boolean, default=False)

    # Current operational status
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="available"
    )  # available | occupied | maintenance | reserved

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    cranes: Mapped[list["Crane"]] = relationship(
        "Crane", back_populates="berth", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["VesselSchedule"]] = relationship(
        "VesselSchedule", back_populates="berth"
    )

    def __repr__(self) -> str:
        return f"<Berth id={self.id} code={self.code!r} terminal={self.terminal!r}>"


# ---------------------------------------------------------------------------
# Crane
# ---------------------------------------------------------------------------
class Crane(Base):
    __tablename__ = "cranes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    crane_type: Mapped[str] = mapped_column(
        String(60), nullable=False
    )  # quay_crane | mobile_crane | reach_stacker | gantry_crane

    # Capabilities
    max_lift_tonnes: Mapped[float] = mapped_column(Float, nullable=False)
    outreach_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Assignment
    berth_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("berths.id"), nullable=True
    )

    # Operational status
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="available"
    )  # available | in_use | maintenance | offline

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    berth: Mapped["Berth | None"] = relationship("Berth", back_populates="cranes")

    def __repr__(self) -> str:
        return f"<Crane id={self.id} code={self.code!r} type={self.crane_type}>"


# ---------------------------------------------------------------------------
# VesselSchedule
# ---------------------------------------------------------------------------
class VesselSchedule(Base):
    __tablename__ = "vessel_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    vessel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vessels.id"), nullable=False, index=True
    )
    berth_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("berths.id"), nullable=True
    )

    # Timing
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    etd: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Cargo
    cargo_type: Mapped[str] = mapped_column(String(80), nullable=True)
    cargo_volume_teu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cargo_weight_tonnes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status and priority
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="scheduled"
    )  # scheduled | in_port | completed | cancelled | delayed
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )  # 1=highest, 5=lowest
    delay_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Origin / destination
    port_of_origin: Mapped[str] = mapped_column(String(100), nullable=True)
    next_port: Mapped[str] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    vessel: Mapped["Vessel"] = relationship("Vessel", back_populates="schedules")
    berth: Mapped["Berth | None"] = relationship("Berth", back_populates="schedules")

    def __repr__(self) -> str:
        return f"<VesselSchedule id={self.id} vessel_id={self.vessel_id} eta={self.eta}>"

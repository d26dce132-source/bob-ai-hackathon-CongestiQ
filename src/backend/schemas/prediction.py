"""
Phase 2 prediction schemas — responses for congestion, vessel risk, and hotspots.
Added to the existing schemas package.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared enums (represented as string literals for simplicity)
# ---------------------------------------------------------------------------
# Severity levels used across all prediction endpoints
# Values: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"


# ---------------------------------------------------------------------------
# Congestion prediction
# ---------------------------------------------------------------------------
class CongestionWindowScore(BaseModel):
    """Score for one 6-hour rolling window."""
    window_start: datetime
    window_end: datetime
    score: float                  # 0–100
    level: str                    # LOW | MEDIUM | HIGH | CRITICAL
    arriving_vessels: int
    berth_utilisation_pct: float  # 0–100
    crane_shortage_factor: float  # 0–1 (1 = severe shortage)
    delayed_vessel_count: int


class CongestionFactor(BaseModel):
    """One contributing factor in the congestion score explanation."""
    name: str
    contribution: float           # points added to score (0–100 scale)
    description: str


class CongestionPredictionResponse(BaseModel):
    computed_at: datetime
    overall_score: float          # 0–100
    overall_level: str            # LOW | MEDIUM | HIGH | CRITICAL
    peak_window_start: Optional[datetime] = None
    peak_window_end: Optional[datetime] = None
    peak_score: float
    factors: List[CongestionFactor]
    window_scores: List[CongestionWindowScore]
    summary: str                  # one-sentence plain-English explanation


# ---------------------------------------------------------------------------
# Vessel risk detection
# ---------------------------------------------------------------------------
class VesselRiskFactor(BaseModel):
    """One contributing factor in a vessel's risk score."""
    name: str
    contribution: float           # points (0–100 scale)
    description: str


class VesselRiskResponse(BaseModel):
    vessel_id: int
    vessel_name: str
    vessel_type: str
    imo_number: str
    current_status: str
    schedule_id: Optional[int] = None
    eta: Optional[datetime] = None
    berth_code: Optional[str] = None
    risk_score: float             # 0–100
    risk_level: str               # LOW | MEDIUM | HIGH | CRITICAL
    delay_hours: float
    factors: List[VesselRiskFactor]
    recommendation: str           # short action sentence


class VesselRiskListResponse(BaseModel):
    computed_at: datetime
    total: int
    vessels: List[VesselRiskResponse]


# ---------------------------------------------------------------------------
# Congestion hotspots
# ---------------------------------------------------------------------------
class HotspotVessel(BaseModel):
    vessel_id: int
    vessel_name: str
    eta: datetime
    delay_hours: float
    priority: int


class HotspotResponse(BaseModel):
    berth_code: str
    berth_name: str
    terminal: str
    hotspot_score: float          # 0–100
    severity: str                 # LOW | MEDIUM | HIGH | CRITICAL
    scheduled_vessel_count: int
    available_crane_count: int
    required_crane_count: int
    overlap_hours: float          # how many hours in 72h window are double-booked
    reasons: List[str]            # plain-English reason list
    affected_vessels: List[HotspotVessel]


class HotspotListResponse(BaseModel):
    computed_at: datetime
    total_hotspots: int
    hotspots: List[HotspotResponse]
    port_summary: str

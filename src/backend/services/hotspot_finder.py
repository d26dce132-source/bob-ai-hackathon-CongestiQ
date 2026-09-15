"""
Congestion Hotspot Detection Service
======================================
Identifies berths where congestion is likely to develop over the next 72 hours.

A berth becomes a hotspot when:
  1. More vessels are scheduled than the berth can service in the time window
     (schedule overlap — two ETDs overlap with the same berth)
  2. Insufficient cranes are assigned to handle the expected cargo volume
  3. One or more assigned vessels have significant existing delays

Hotspot Score (0–100)
----------------------
  schedule_overlap   40 pts  — double-booked or tightly sequenced windows
  crane_deficit      35 pts  — cranes needed > cranes available at berth
  delay_exposure     25 pts  — delayed vessels holding the berth longer

Classification thresholds
--------------------------
  0–30   LOW
  31–55  MEDIUM
  56–75  HIGH
  76–100 CRITICAL
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC timezone to naive datetimes (SQLite returns naive; PostgreSQL returns aware)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

from db.models import Berth, Crane, VesselSchedule
from schemas.prediction import HotspotListResponse, HotspotResponse, HotspotVessel

HORIZON_HOURS = 72

# Minimum cranes required per vessel type for normal operations
CRANES_NEEDED: dict[str, int] = {
    "container":     3,
    "bulk_carrier":  2,
    "tanker":        1,
    "roro":          1,
    "general_cargo": 2,
}


def _classify(score: float) -> str:
    if score <= 30:
        return "LOW"
    if score <= 55:
        return "MEDIUM"
    if score <= 75:
        return "HIGH"
    return "CRITICAL"


def _overlap_hours(schedules: list[VesselSchedule], now: datetime) -> float:
    """
    Calculate total hours in the 72h window where more than one vessel
    occupies the berth simultaneously (impossible in reality — this is
    the core congestion indicator).
    Uses a simple event-timeline scan in 1-hour buckets.
    """
    horizon_end = now + timedelta(hours=HORIZON_HOURS)
    # Build 1-hour occupancy buckets
    buckets = [0] * HORIZON_HOURS
    for s in schedules:
        eta = _ensure_utc(s.eta)
        s_start = max(eta, now)
        s_end = min(_ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24), horizon_end)
        start_h = int((s_start - now).total_seconds() / 3600)
        end_h = int((s_end - now).total_seconds() / 3600)
        for h in range(max(start_h, 0), min(end_h, HORIZON_HOURS)):
            buckets[h] += 1

    # Count hours where occupancy > 1
    overlap = sum(1 for b in buckets if b > 1)
    return float(overlap)


def _schedule_overlap_score(overlap_h: float) -> float:
    """0–40 pts based on overlap hours. 8+ hours of overlap → max score."""
    return round(min(overlap_h / 8.0, 1.0) * 40, 2)


def _crane_deficit_score(
    schedules: list[VesselSchedule],
    assigned_cranes: list[Crane],
    now: datetime,
) -> tuple[int, int, float]:
    """
    Returns (required, available, score 0–35).
    Compute peak crane demand across the 72h window.
    """
    horizon_end = now + timedelta(hours=HORIZON_HOURS)
    # Peak simultaneous crane demand (worst single hour)
    buckets = [0] * HORIZON_HOURS
    for s in schedules:
        vtype = s.vessel.vessel_type if s.vessel else "general_cargo"
        needed = CRANES_NEEDED.get(vtype, 2)
        eta = _ensure_utc(s.eta)
        s_start = max(eta, now)
        s_end = min(_ensure_utc(s.etd) if s.etd else eta + timedelta(hours=24), horizon_end)
        start_h = int((s_start - now).total_seconds() / 3600)
        end_h = int((s_end - now).total_seconds() / 3600)
        for h in range(max(start_h, 0), min(end_h, HORIZON_HOURS)):
            buckets[h] += needed

    peak_demand = max(buckets) if buckets else 0
    available = len([c for c in assigned_cranes if c.status in ("available", "in_use")])

    deficit = max(0, peak_demand - available)
    if peak_demand == 0:
        score = 0.0
    else:
        score = round(min(deficit / peak_demand, 1.0) * 35, 2)
    return peak_demand, available, score


def _delay_exposure_score(schedules: list[VesselSchedule]) -> tuple[float]:
    """0–25 pts based on aggregate delay hours of vessels assigned to this berth."""
    total_delay = sum(s.delay_hours for s in schedules)
    # 24 h of aggregate delay → max score
    score = round(min(total_delay / 24.0, 1.0) * 25, 2)
    return (score,)


def compute_hotspots(db: Session) -> HotspotListResponse:
    """
    Identify berths where congestion is expected in the next 72 hours.
    Returns a HotspotListResponse.
    """
    now = datetime.now(timezone.utc)
    horizon_end = now + timedelta(hours=HORIZON_HOURS)

    berths: list[Berth] = db.query(Berth).all()
    cranes: list[Crane] = db.query(Crane).all()

    # All schedules in horizon
    schedules: list[VesselSchedule] = (
        db.query(VesselSchedule)
        .options(joinedload(VesselSchedule.vessel), joinedload(VesselSchedule.berth))
        .filter(
            VesselSchedule.eta <= horizon_end,
            VesselSchedule.status.notin_(["cancelled", "completed"]),
        )
        .all()
    )

    # Map berth_id → schedules
    berth_schedules: dict[int, list[VesselSchedule]] = {}
    for s in schedules:
        if s.berth_id:
            berth_schedules.setdefault(s.berth_id, []).append(s)

    # Map berth_id → cranes
    berth_cranes: dict[int, list[Crane]] = {}
    for c in cranes:
        if c.berth_id:
            berth_cranes.setdefault(c.berth_id, []).append(c)

    hotspots: list[HotspotResponse] = []

    for berth in berths:
        b_schedules = berth_schedules.get(berth.id, [])
        if not b_schedules:
            continue   # No traffic at this berth — skip

        b_cranes = berth_cranes.get(berth.id, [])

        # Compute sub-scores
        overlap_h = _overlap_hours(b_schedules, now)
        overlap_score = _schedule_overlap_score(overlap_h)

        required_cranes, available_cranes, crane_score = _crane_deficit_score(
            b_schedules, b_cranes, now
        )
        (delay_score,) = _delay_exposure_score(b_schedules)

        hotspot_score = round(min(overlap_score + crane_score + delay_score, 100), 1)
        severity = _classify(hotspot_score)

        # Build reasons list
        reasons: list[str] = []
        if overlap_h > 0:
            reasons.append(
                f"{overlap_h:.0f}h of schedule overlap — "
                f"multiple vessels competing for the same berth slot"
            )
        if required_cranes > available_cranes:
            reasons.append(
                f"Peak crane demand ({required_cranes}) exceeds available cranes "
                f"at this berth ({available_cranes})"
            )
        delayed = [s for s in b_schedules if s.delay_hours > 0]
        if delayed:
            total_delay = sum(s.delay_hours for s in delayed)
            reasons.append(
                f"{len(delayed)} vessel(s) delayed by a combined {total_delay:.1f}h, "
                f"extending berth occupation beyond planned window"
            )
        if berth.status == "maintenance":
            reasons.append("Berth is currently under maintenance — capacity temporarily reduced")
        if not reasons:
            reasons.append("Traffic volume approaching berth capacity limits")

        # Build affected vessel list (sorted by priority then ETA)
        affected = sorted(b_schedules, key=lambda s: (s.priority, s.eta))
        affected_vessels = [
            HotspotVessel(
                vessel_id=s.vessel_id,
                vessel_name=s.vessel.name if s.vessel else f"Vessel #{s.vessel_id}",
                eta=s.eta,
                delay_hours=s.delay_hours,
                priority=s.priority,
            )
            for s in affected
        ]

        hotspots.append(
            HotspotResponse(
                berth_code=berth.code,
                berth_name=berth.name,
                terminal=berth.terminal,
                hotspot_score=hotspot_score,
                severity=severity,
                scheduled_vessel_count=len(b_schedules),
                available_crane_count=available_cranes,
                required_crane_count=required_cranes,
                overlap_hours=overlap_h,
                reasons=reasons,
                affected_vessels=affected_vessels,
            )
        )

    # Sort: worst hotspots first
    hotspots.sort(key=lambda h: h.hotspot_score, reverse=True)
    # Exclude LOW-severity berths with only 1 vessel and no real overlap
    significant = [h for h in hotspots if h.severity != "LOW" or h.overlap_hours > 0]

    # Port-level summary
    critical = sum(1 for h in significant if h.severity == "CRITICAL")
    high = sum(1 for h in significant if h.severity == "HIGH")

    if critical > 0:
        summary = (
            f"{critical} CRITICAL and {high} HIGH hotspot(s) detected. "
            f"Immediate berth and crane reallocation recommended."
        )
    elif high > 0:
        summary = (
            f"{high} HIGH congestion hotspot(s) identified. "
            f"Review crane assignments and arrival sequencing."
        )
    elif significant:
        summary = (
            f"{len(significant)} berth(s) showing elevated congestion risk. "
            f"Monitor and adjust schedules proactively."
        )
    else:
        summary = "No significant congestion hotspots detected in the next 72 hours."

    return HotspotListResponse(
        computed_at=now,
        total_hotspots=len(significant),
        hotspots=significant,
        port_summary=summary,
    )

"""
Seed script — populates the database with realistic simulated port data.

Designed to be idempotent: checks for existing rows before inserting so
restarting the server never duplicates data.

Data represents a medium-sized container/bulk port (loosely modelled on a
South-East Asian transshipment hub) with two terminals:
  - North Container Terminal (NCT)
  - South Bulk & General Terminal (SBT)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from db.models import Berth, Crane, Vessel, VesselSchedule

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

_BERTHS: list[dict] = [
    # North Container Terminal — 7 berths
    {
        "code": "NCT-1",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 1",
        "length_m": 400.0,
        "max_draft_m": 16.0,
        "vessel_types_allowed": "container",
        "has_shore_power": True,
        "status": "available",
    },
    {
        "code": "NCT-2",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 2",
        "length_m": 380.0,
        "max_draft_m": 15.5,
        "vessel_types_allowed": "container",
        "has_shore_power": True,
        "status": "occupied",
    },
    {
        "code": "NCT-3",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 3",
        "length_m": 360.0,
        "max_draft_m": 15.0,
        "vessel_types_allowed": "container,roro",
        "has_shore_power": True,
        "status": "available",
    },
    {
        "code": "NCT-4",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 4",
        "length_m": 340.0,
        "max_draft_m": 14.5,
        "vessel_types_allowed": "container",
        "has_shore_power": False,
        "status": "available",
    },
    {
        "code": "NCT-5",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 5",
        "length_m": 320.0,
        "max_draft_m": 14.0,
        "vessel_types_allowed": "container,general_cargo",
        "has_shore_power": False,
        "status": "maintenance",
    },
    {
        "code": "NCT-6",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 6",
        "length_m": 310.0,
        "max_draft_m": 13.5,
        "vessel_types_allowed": "container",
        "has_shore_power": True,
        "status": "reserved",
    },
    {
        "code": "NCT-7",
        "terminal": "North Container Terminal",
        "name": "NCT Berth 7",
        "length_m": 300.0,
        "max_draft_m": 13.0,
        "vessel_types_allowed": "container,roro",
        "has_shore_power": False,
        "status": "available",
    },
    # South Bulk & General Terminal — 5 berths
    {
        "code": "SBT-1",
        "terminal": "South Bulk & General Terminal",
        "name": "SBT Berth 1",
        "length_m": 350.0,
        "max_draft_m": 17.0,
        "vessel_types_allowed": "bulk_carrier,tanker",
        "has_shore_power": False,
        "status": "occupied",
    },
    {
        "code": "SBT-2",
        "terminal": "South Bulk & General Terminal",
        "name": "SBT Berth 2",
        "length_m": 330.0,
        "max_draft_m": 16.5,
        "vessel_types_allowed": "bulk_carrier",
        "has_shore_power": False,
        "status": "available",
    },
    {
        "code": "SBT-3",
        "terminal": "South Bulk & General Terminal",
        "name": "SBT Berth 3",
        "length_m": 280.0,
        "max_draft_m": 14.0,
        "vessel_types_allowed": "tanker,general_cargo",
        "has_shore_power": True,
        "status": "available",
    },
    {
        "code": "SBT-4",
        "terminal": "South Bulk & General Terminal",
        "name": "SBT Berth 4",
        "length_m": 260.0,
        "max_draft_m": 13.0,
        "vessel_types_allowed": "general_cargo,roro",
        "has_shore_power": False,
        "status": "available",
    },
    {
        "code": "SBT-5",
        "terminal": "South Bulk & General Terminal",
        "name": "SBT Berth 5",
        "length_m": 240.0,
        "max_draft_m": 12.5,
        "vessel_types_allowed": "general_cargo",
        "has_shore_power": False,
        "status": "maintenance",
    },
]

# (code, name, type, max_lift_t, outreach_m, berth_code, status)
_CRANE_TEMPLATES: list[tuple] = [
    # NCT quay cranes — large ship-to-shore
    ("QC-NCT-01", "STS Crane NCT-01", "quay_crane", 65.0, 63.0, "NCT-1", "in_use"),
    ("QC-NCT-02", "STS Crane NCT-02", "quay_crane", 65.0, 63.0, "NCT-1", "in_use"),
    ("QC-NCT-03", "STS Crane NCT-03", "quay_crane", 65.0, 63.0, "NCT-2", "in_use"),
    ("QC-NCT-04", "STS Crane NCT-04", "quay_crane", 60.0, 58.0, "NCT-2", "available"),
    ("QC-NCT-05", "STS Crane NCT-05", "quay_crane", 60.0, 58.0, "NCT-3", "available"),
    ("QC-NCT-06", "STS Crane NCT-06", "quay_crane", 60.0, 58.0, "NCT-4", "available"),
    ("QC-NCT-07", "STS Crane NCT-07", "quay_crane", 55.0, 55.0, "NCT-6", "available"),
    ("QC-NCT-08", "STS Crane NCT-08", "quay_crane", 55.0, 55.0, "NCT-7", "maintenance"),
    # NCT rubber-tyred gantry cranes (yard)
    ("RTG-NCT-01", "RTG Crane NCT-01", "gantry_crane", 50.0, None, "NCT-1", "in_use"),
    ("RTG-NCT-02", "RTG Crane NCT-02", "gantry_crane", 50.0, None, "NCT-2", "available"),
    ("RTG-NCT-03", "RTG Crane NCT-03", "gantry_crane", 50.0, None, "NCT-3", "available"),
    # SBT mobile cranes
    ("MC-SBT-01", "Mobile Crane SBT-01", "mobile_crane", 100.0, 30.0, "SBT-1", "in_use"),
    ("MC-SBT-02", "Mobile Crane SBT-02", "mobile_crane", 100.0, 30.0, "SBT-2", "available"),
    ("MC-SBT-03", "Mobile Crane SBT-03", "mobile_crane", 80.0, 28.0, "SBT-3", "available"),
    ("MC-SBT-04", "Mobile Crane SBT-04", "mobile_crane", 80.0, 28.0, "SBT-4", "available"),
    # SBT reach stackers
    ("RS-SBT-01", "Reach Stacker SBT-01", "reach_stacker", 45.0, None, "SBT-4", "available"),
    ("RS-SBT-02", "Reach Stacker SBT-02", "reach_stacker", 45.0, None, "SBT-5", "maintenance"),
    # Unassigned / general pool
    ("MC-POOL-01", "Mobile Crane Pool-01", "mobile_crane", 70.0, 25.0, None, "available"),
    ("MC-POOL-02", "Mobile Crane Pool-02", "mobile_crane", 70.0, 25.0, None, "available"),
    ("RS-POOL-01", "Reach Stacker Pool-01", "reach_stacker", 42.0, None, None, "available"),
]

# Vessels: (name, imo, call_sign, flag, type, operator, length, beam, draft, gt, teu, status)
_VESSEL_DATA: list[tuple] = [
    # --- Container vessels ---
    ("MSC Adriana",       "IMO9876501", "9XAD",  "Panama",       "container",    "MSC",           366.0, 51.2, 15.5, 153092, 14000, "berthed"),
    ("Evergreen Horizon", "IMO9876502", "9XEH",  "Taiwan",       "container",    "Evergreen",     335.0, 48.2, 14.8, 111000, 10000, "en_route"),
    ("COSCO Shanghai",    "IMO9876503", "9XCS",  "China",        "container",    "COSCO",         320.0, 47.0, 14.5, 104000,  9500, "anchored"),
    ("ONE Harmony",       "IMO9876504", "9XOH",  "Japan",        "container",    "ONE",           300.0, 45.6, 14.0,  94000,  8500, "en_route"),
    ("Yang Ming Eagle",   "IMO9876505", "9XYE",  "Taiwan",       "container",    "Yang Ming",     285.0, 44.2, 13.8,  89000,  8000, "berthed"),
    ("HMM Global",        "IMO9876506", "9XHG",  "South Korea",  "container",    "HMM",           270.0, 43.0, 13.5,  85000,  7500, "en_route"),
    ("Hapag Asia",        "IMO9876507", "9XHA",  "Germany",      "container",    "Hapag-Lloyd",   260.0, 42.0, 13.2,  80000,  7000, "anchored"),
    ("CMA Mistral",       "IMO9876508", "9XCM",  "France",       "container",    "CMA CGM",       250.0, 41.0, 13.0,  76000,  6500, "en_route"),
    ("Maersk Denali",     "IMO9876509", "9XMD",  "Denmark",      "container",    "Maersk",        240.0, 40.0, 12.8,  72000,  6000, "en_route"),
    ("Zim Pacific",       "IMO9876510", "9XZP",  "Israel",       "container",    "ZIM",           220.0, 38.0, 12.5,  65000,  5500, "en_route"),
    ("PIL Unity",         "IMO9876511", "9XPU",  "Singapore",    "container",    "PIL",           210.0, 36.0, 12.0,  58000,  5000, "berthed"),
    ("WHL Fortune",       "IMO9876512", "9XWF",  "Taiwan",       "container",    "WHL",           200.0, 35.0, 11.8,  54000,  4500, "departing"),
    ("Sinolines Star",    "IMO9876513", "9XSS",  "China",        "container",    "Sinolines",     195.0, 34.0, 11.5,  51000,  4200, "en_route"),
    ("Samudera Nusa",     "IMO9876514", "9XSN",  "Indonesia",    "container",    "Samudera",      180.0, 32.0, 11.0,  44000,  3800, "en_route"),
    # --- Bulk carriers ---
    ("Pacific Grain",     "IMO9876515", "9XPG",  "Marshall Isl.","bulk_carrier", "Pacific Bulk",  290.0, 45.0, 17.0, 105000,  None, "berthed"),
    ("Iron Voyager",      "IMO9876516", "9XIV",  "Liberia",      "bulk_carrier", "Star Bulk",     275.0, 43.0, 16.5, 95000,   None, "en_route"),
    ("Coal Express",      "IMO9876517", "9XCE",  "Greece",       "bulk_carrier", "Diana Ship.",   260.0, 42.0, 16.0, 87000,   None, "anchored"),
    ("Ceres Harvest",     "IMO9876518", "9XCH",  "Norway",       "bulk_carrier", "Torvald Klav.", 240.0, 40.0, 15.5, 78000,   None, "en_route"),
    ("Grand Soybean",     "IMO9876519", "9XGS",  "Singapore",    "bulk_carrier", "Precious Ship.",220.0, 38.0, 15.0, 68000,   None, "en_route"),
    ("Southern Cross",    "IMO9876520", "9XSC",  "Philippines",  "bulk_carrier", "Filipino Ship.",200.0, 36.0, 14.5, 58000,   None, "en_route"),
    # --- Tankers ---
    ("Gulf Trader",       "IMO9876521", "9XGT",  "Saudi Arabia", "tanker",       "Bahri",         330.0, 58.0, 20.0, 160000,  None, "anchored"),
    ("Petro Voyager",     "IMO9876522", "9XPV",  "Greece",       "tanker",       "Tsakos",        320.0, 56.0, 19.5, 150000,  None, "en_route"),
    ("Asian Spirit",      "IMO9876523", "9XAS",  "Singapore",    "tanker",       "BW Group",      280.0, 50.0, 17.5, 110000,  None, "en_route"),
    ("LNG Pacific",       "IMO9876524", "9XLP",  "Japan",        "tanker",       "NYK",           295.0, 46.0, 12.5,  98000,  None, "en_route"),
    # --- RoRo ---
    ("Euro Highway",      "IMO9876525", "9XEH2", "Sweden",       "roro",         "Wallenius",     230.0, 36.0, 10.5,  70000,  None, "berthed"),
    ("Trans Pacific Ace", "IMO9876526", "9XTP",  "Japan",        "roro",         "MOL",           200.0, 34.0, 10.0,  60000,  None, "en_route"),
    # --- General cargo ---
    ("Singa Cargo",       "IMO9876527", "9XSG",  "Singapore",    "general_cargo","Singamas",      170.0, 28.0, 10.0,  35000,  None, "en_route"),
    ("Borneo Trader",     "IMO9876528", "9XBT",  "Malaysia",     "general_cargo","MISC",          160.0, 27.0,  9.5,  30000,  None, "anchored"),
    ("Andaman Spirit",    "IMO9876529", "9XAD2", "Thailand",     "general_cargo","RCL",           150.0, 26.0,  9.0,  26000,  None, "en_route"),
    ("Mekong River",      "IMO9876530", "9XMR",  "Vietnam",      "general_cargo","VIMC",          145.0, 25.0,  8.8,  24000,  None, "en_route"),
    ("Manila Bay",        "IMO9876531", "9XMB",  "Philippines",  "general_cargo","KPHC",          140.0, 24.5,  8.5,  22000,  None, "en_route"),
    ("Colombo Star",      "IMO9876532", "9XCO",  "Sri Lanka",    "general_cargo","SLSL",          135.0, 24.0,  8.2,  20000,  None, "en_route"),
]

# Schedules per vessel: (vessel_name, berth_code, eta_offset_h, duration_h,
#                        cargo_type, teu, weight_t, status, priority, delay_h,
#                        origin, next_port)
_SCHEDULE_DATA: list[tuple] = [
    # Currently berthed — already in port
    ("MSC Adriana",       "NCT-2", -10,  24, "containers",      9800,   None, "in_port",   1, 0.0,  "Rotterdam",   "Hong Kong"),
    ("Yang Ming Eagle",   "NCT-1", -14,  18, "containers",      7200,   None, "in_port",   2, 0.0,  "Kaohsiung",   "Singapore"),
    ("Pacific Grain",     "SBT-1", -8,   30, "grain",           None, 85000, "in_port",   2, 0.0,  "New Orleans",  "Jakarta"),
    ("Gulf Trader",       "SBT-3", -20,  48, "crude_oil",       None,150000, "in_port",   1, 0.0,  "Ras Tanura",   "Ningbo"),
    ("Euro Highway",      "NCT-3", -6,   16, "vehicles",        None, 22000, "in_port",   3, 0.0,  "Bremerhaven",  "Yokohama"),
    ("PIL Unity",         "NCT-4",  -4,  20, "containers",      4800,   None, "in_port",   3, 0.0,  "Port Klang",   "Colombo"),

    # Arriving in <12 h — high urgency
    ("COSCO Shanghai",    "NCT-2",   2,  22, "containers",      8800,   None, "scheduled", 1, 1.5,  "Qingdao",     "Tanjung Pelepas"),
    ("Coal Express",      "SBT-2",   3,  36, "coal",            None, 80000, "scheduled", 2, 0.0,  "Newcastle",    "Chennai"),
    ("Hapag Asia",        "NCT-6",   5,  20, "containers",      6500,   None, "scheduled", 2, 2.0,  "Hamburg",     "Port Klang"),
    ("Trans Pacific Ace", "NCT-3",   6,  14, "vehicles",        None, 18000, "scheduled", 3, 0.0,  "Nagoya",       "Sydney"),
    ("Iron Voyager",      "SBT-2",   8,  28, "iron_ore",        None, 90000, "scheduled", 1, 0.0,  "Port Hedland", "Baosteel"),
    ("Borneo Trader",     "SBT-4",   9,  12, "timber",          None, 15000, "scheduled", 4, 3.0,  "Sandakan",     "Colombo"),

    # Arriving 12-36 h
    ("Evergreen Horizon", "NCT-1",  14,  24, "containers",      9200,   None, "scheduled", 1, 0.0,  "Kaohsiung",   "Port Said"),
    ("ONE Harmony",       "NCT-4",  15,  20, "containers",      8100,   None, "scheduled", 2, 0.0,  "Tokyo",       "Colombo"),
    ("HMM Global",        "NCT-7",  18,  18, "containers",      7200,   None, "scheduled", 2, 1.0,  "Busan",       "Felixstowe"),
    ("Petro Voyager",     "SBT-3",  20,  40, "fuel_oil",        None,140000, "scheduled", 1, 0.5,  "Kuwait",       "Mumbai"),
    ("Ceres Harvest",     "SBT-2",  22,  32, "grain",           None, 72000, "scheduled", 2, 0.0,  "Buenos Aires", "Manila"),
    ("CMA Mistral",       "NCT-3",  24,  22, "containers",      6200,   None, "scheduled", 3, 0.0,  "Marseille",   "Colombo"),
    ("Grand Soybean",     "SBT-2",  26,  30, "soybeans",        None, 64000, "scheduled", 3, 2.5,  "Santos",       "Ningbo"),
    ("Andaman Spirit",    "SBT-4",  28,  16, "general_cargo",   None, 12000, "scheduled", 4, 0.0,  "Bangkok",      "Colombo"),
    ("Asian Spirit",      "SBT-1",  30,  44, "crude_oil",       None,105000, "scheduled", 1, 0.0,  "Jubail",       "Ulsan"),
    ("Samudera Nusa",     "NCT-7",  32,  18, "containers",      3600,   None, "scheduled", 4, 0.0,  "Jakarta",     "Penang"),

    # Arriving 36-72 h
    ("Maersk Denali",     "NCT-1",  36,  20, "containers",      5800,   None, "scheduled", 2, 0.0,  "Los Angeles",  "Rotterdam"),
    ("Zim Pacific",       "NCT-4",  40,  18, "containers",      5200,   None, "scheduled", 3, 1.0,  "Haifa",        "Busan"),
    ("LNG Pacific",       "SBT-3",  42,  52, "lng",             None, 72000, "scheduled", 1, 0.0,  "Bontang",      "Tokyo"),
    ("Southern Cross",    "SBT-2",  46,  28, "coal",            None, 56000, "scheduled", 3, 3.0,  "Kalimantan",   "Manila"),
    ("WHL Fortune",       "NCT-7",  48,  16, "containers",      4200,   None, "scheduled", 4, 0.0,  "Keelung",      "Colombo"),
    ("Sinolines Star",    "NCT-3",  52,  20, "containers",      4000,   None, "scheduled", 3, 0.0,  "Tianjin",      "Port Klang"),
    ("Singa Cargo",       "SBT-4",  56,  14, "general_cargo",   None, 10000, "scheduled", 4, 0.0,  "Singapore",    "Colombo"),
    ("Mekong River",      "SBT-4",  60,  12, "general_cargo",   None,  8500, "scheduled", 5, 0.0,  "Ho Chi Minh",  "Colombo"),
    ("Manila Bay",        "SBT-4",  64,  10, "general_cargo",   None,  7200, "scheduled", 5, 1.5,  "Manila",       "Colombo"),
    ("Colombo Star",      "SBT-5",  68,  12, "general_cargo",   None,  6000, "scheduled", 5, 0.0,  "Colombo",      "Chittagong"),
]


# ---------------------------------------------------------------------------
# Seeding functions
# ---------------------------------------------------------------------------

def seed_berths(db: Session) -> dict[str, int]:
    """Insert berths and return a mapping of code -> id."""
    if db.query(Berth).count() > 0:
        return {b.code: b.id for b in db.query(Berth).all()}

    berth_map: dict[str, int] = {}
    for data in _BERTHS:
        berth = Berth(**data)
        db.add(berth)
        db.flush()  # get auto-generated id before commit
        berth_map[berth.code] = berth.id

    db.commit()
    print(f"[seed] Inserted {len(_BERTHS)} berths.")
    return berth_map


def seed_cranes(db: Session, berth_map: dict[str, int]) -> None:
    """Insert cranes and link them to berths."""
    if db.query(Crane).count() > 0:
        return

    for code, name, ctype, lift, outreach, berth_code, status in _CRANE_TEMPLATES:
        crane = Crane(
            code=code,
            name=name,
            crane_type=ctype,
            max_lift_tonnes=lift,
            outreach_m=outreach,
            berth_id=berth_map.get(berth_code) if berth_code else None,
            status=status,
        )
        db.add(crane)

    db.commit()
    print(f"[seed] Inserted {len(_CRANE_TEMPLATES)} cranes.")


def seed_vessels(db: Session) -> dict[str, int]:
    """Insert vessels and return a mapping of name -> id."""
    if db.query(Vessel).count() > 0:
        return {v.name: v.id for v in db.query(Vessel).all()}

    vessel_map: dict[str, int] = {}
    for (
        name, imo, call_sign, flag, vtype, operator,
        length, beam, draft, gt, teu, status
    ) in _VESSEL_DATA:
        vessel = Vessel(
            name=name,
            imo_number=imo,
            call_sign=call_sign,
            flag=flag,
            vessel_type=vtype,
            operator=operator,
            length_m=length,
            beam_m=beam,
            draft_m=draft,
            gross_tonnage=gt,
            teu_capacity=teu,
            status=status,
        )
        db.add(vessel)
        db.flush()
        vessel_map[vessel.name] = vessel.id

    db.commit()
    print(f"[seed] Inserted {len(_VESSEL_DATA)} vessels.")
    return vessel_map


def seed_schedules(
    db: Session, vessel_map: dict[str, int], berth_map: dict[str, int]
) -> None:
    """Insert vessel schedules relative to current UTC time."""
    if db.query(VesselSchedule).count() > 0:
        return

    now = datetime.now(timezone.utc)
    inserted = 0

    for (
        vessel_name, berth_code, eta_offset_h, duration_h,
        cargo_type, teu, weight_t, status, priority, delay_h,
        origin, next_port
    ) in _SCHEDULE_DATA:
        vessel_id = vessel_map.get(vessel_name)
        berth_id = berth_map.get(berth_code)

        if vessel_id is None:
            print(f"[seed] WARNING: vessel not found: {vessel_name!r}")
            continue

        eta = now + timedelta(hours=eta_offset_h)
        etd = eta + timedelta(hours=duration_h)

        actual_arrival = eta if status == "in_port" else None
        actual_departure = None  # not departed yet

        schedule = VesselSchedule(
            vessel_id=vessel_id,
            berth_id=berth_id,
            eta=eta,
            etd=etd,
            actual_arrival=actual_arrival,
            actual_departure=actual_departure,
            cargo_type=cargo_type,
            cargo_volume_teu=teu,
            cargo_weight_tonnes=weight_t,
            status=status,
            priority=priority,
            delay_hours=delay_h,
            port_of_origin=origin,
            next_port=next_port,
        )
        db.add(schedule)
        inserted += 1

    db.commit()
    print(f"[seed] Inserted {inserted} vessel schedules.")


def run_seed(db: Session) -> None:
    """Entry point — seed all tables in dependency order."""
    print("[seed] Starting database seed...")
    berth_map = seed_berths(db)
    seed_cranes(db, berth_map)
    vessel_map = seed_vessels(db)
    seed_schedules(db, vessel_map, berth_map)
    print("[seed] Seed complete.")

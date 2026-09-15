"""
Phase 1 API tests.
Run with:  python test_phase1.py
Uses FastAPI TestClient + SQLite (no live PostgreSQL needed).
TestClient is used as a context manager so lifespan/startup runs.
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_congestiq.db"

from fastapi.testclient import TestClient
import main  # noqa: E402

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  " + label)
    else:
        msg = "  FAIL  " + label + (" -- " + detail if detail else "")
        print(msg)
        failures.append(label)


print("=" * 60)
print("CongestiQ Phase 1 - API endpoint tests")
print("=" * 60)

with TestClient(main.app) as client:

    # ------------------------------------------------------------------
    # GET /api/health
    # ------------------------------------------------------------------
    print("\n[health]")
    r = client.get("/api/health")
    check("status 200", r.status_code == 200, r.text)
    d = r.json()
    check("status=ok", d["status"] == "ok")
    check("vessel_count=32", d["vessel_count"] == 32, str(d["vessel_count"]))
    check("berth_count=12", d["berth_count"] == 12, str(d["berth_count"]))
    check("crane_count=20", d["crane_count"] == 20, str(d["crane_count"]))
    check("schedule_count=32", d["schedule_count"] == 32, str(d["schedule_count"]))
    check("database=ok", d["database"] == "ok")

    # ------------------------------------------------------------------
    # GET /api/vessels
    # ------------------------------------------------------------------
    print("\n[vessels]")
    r = client.get("/api/vessels")
    check("status 200", r.status_code == 200)
    d = r.json()
    check("total=32", d["total"] == 32, str(d["total"]))
    check("has vessels list", isinstance(d["vessels"], list))

    r = client.get("/api/vessels?vessel_type=container")
    d = r.json()
    check("filter type=container -> 14", d["total"] == 14, str(d["total"]))

    r = client.get("/api/vessels?status=berthed")
    d = r.json()
    check("filter status=berthed > 0", d["total"] > 0, str(d["total"]))

    r = client.get("/api/vessels/1")
    check("GET /api/vessels/1 -> 200", r.status_code == 200)
    check("vessel has imo_number", "imo_number" in r.json())

    r = client.get("/api/vessels/9999")
    check("GET /api/vessels/9999 -> 404", r.status_code == 404)

    # ------------------------------------------------------------------
    # GET /api/berths
    # ------------------------------------------------------------------
    print("\n[berths]")
    r = client.get("/api/berths")
    check("status 200", r.status_code == 200)
    d = r.json()
    check("total=12", d["total"] == 12, str(d["total"]))

    r = client.get("/api/berths?status=available")
    d = r.json()
    check("filter status=available > 0", d["total"] > 0, str(d["total"]))

    r = client.get("/api/berths?terminal=North")
    d = r.json()
    check("filter terminal=North -> 7", d["total"] == 7, str(d["total"]))

    r = client.get("/api/berths/1")
    check("GET /api/berths/1 -> 200", r.status_code == 200)

    r = client.get("/api/berths/9999")
    check("GET /api/berths/9999 -> 404", r.status_code == 404)

    # ------------------------------------------------------------------
    # GET /api/cranes
    # ------------------------------------------------------------------
    print("\n[cranes]")
    r = client.get("/api/cranes")
    check("status 200", r.status_code == 200)
    d = r.json()
    check("total=20", d["total"] == 20, str(d["total"]))

    r = client.get("/api/cranes?crane_type=quay_crane")
    d = r.json()
    check("filter type=quay_crane -> 8", d["total"] == 8, str(d["total"]))

    r = client.get("/api/cranes?status=available")
    d = r.json()
    check("filter status=available > 0", d["total"] > 0, str(d["total"]))

    r = client.get("/api/cranes/1")
    check("GET /api/cranes/1 -> 200", r.status_code == 200)

    r = client.get("/api/cranes/9999")
    check("GET /api/cranes/9999 -> 404", r.status_code == 404)

    # ------------------------------------------------------------------
    # GET /api/schedules
    # ------------------------------------------------------------------
    print("\n[schedules]")
    r = client.get("/api/schedules")
    check("status 200", r.status_code == 200)
    d = r.json()
    check("default 72h window has results", d["total"] > 0, str(d["total"]))
    if d["schedules"]:
        s = d["schedules"][0]
        check("schedule has vessel_name", s.get("vessel_name") is not None)
        check("schedule has berth_code", "berth_code" in s)
        check("schedule has eta", "eta" in s)

    r = client.get("/api/schedules?window_hours=0")
    d = r.json()
    check("window_hours=0 returns all 32", d["total"] == 32, str(d["total"]))

    r = client.get("/api/schedules?status=in_port")
    d = r.json()
    check("filter status=in_port > 0", d["total"] > 0, str(d["total"]))

    r = client.get("/api/schedules/1")
    check("GET /api/schedules/1 -> 200", r.status_code == 200)

    r = client.get("/api/schedules/9999")
    check("GET /api/schedules/9999 -> 404", r.status_code == 404)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print()
print("=" * 60)
if failures:
    print("FAILED -- " + str(len(failures)) + " test(s) failed:")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
else:
    print("ALL TESTS PASSED (34 checks)")

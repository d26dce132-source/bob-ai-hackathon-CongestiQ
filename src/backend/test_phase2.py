"""
Phase 2 prediction & risk detection tests.
Run with:  python test_phase2.py
Uses FastAPI TestClient + SQLite (no live PostgreSQL needed).
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_congestiq_p2.db"

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
print("CongestiQ Phase 2 - Prediction & Risk Detection tests")
print("=" * 60)

with TestClient(main.app) as client:

    # ------------------------------------------------------------------
    # GET /api/congestion — port-wide prediction
    # ------------------------------------------------------------------
    print("\n[congestion prediction]")
    r = client.get("/api/congestion")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has overall_score", "overall_score" in d)
    check("overall_score in range 0-100", 0 <= d.get("overall_score", -1) <= 100,
          str(d.get("overall_score")))

    check("has overall_level", "overall_level" in d)
    check("overall_level is valid",
          d.get("overall_level") in ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
          str(d.get("overall_level")))

    check("has peak_score", "peak_score" in d)
    check("peak_score >= overall_score",
          d.get("peak_score", 0) >= d.get("overall_score", 0))

    check("has factors list", isinstance(d.get("factors"), list))
    check("factors count == 4", len(d.get("factors", [])) == 4,
          str(len(d.get("factors", []))))

    if d.get("factors"):
        f = d["factors"][0]
        check("factor has name", "name" in f)
        check("factor has contribution", "contribution" in f)
        check("factor has description", "description" in f)
        check("factor contribution >= 0", f.get("contribution", -1) >= 0)

    check("has window_scores", isinstance(d.get("window_scores"), list))
    check("window_scores count == 12",
          len(d.get("window_scores", [])) == 12,
          str(len(d.get("window_scores", []))))

    if d.get("window_scores"):
        w = d["window_scores"][0]
        check("window has score", "score" in w)
        check("window has level", "level" in w)
        check("window has arriving_vessels", "arriving_vessels" in w)
        check("window has berth_utilisation_pct", "berth_utilisation_pct" in w)
        check("window score in 0-100", 0 <= w.get("score", -1) <= 100)

    check("has summary string", isinstance(d.get("summary"), str) and len(d.get("summary", "")) > 10)
    check("has computed_at", "computed_at" in d)

    # Consistency: sum of factor contributions should be close to overall_score
    total_factor = sum(f["contribution"] for f in d.get("factors", []))
    check("factor sum <= 100", total_factor <= 100, str(round(total_factor, 1)))

    # ------------------------------------------------------------------
    # GET /api/congestion/hotspots — berth hotspots
    # ------------------------------------------------------------------
    print("\n[congestion hotspots]")
    r = client.get("/api/congestion/hotspots")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total_hotspots", "total_hotspots" in d)
    check("has hotspots list", isinstance(d.get("hotspots"), list))
    check("total_hotspots >= 0", d.get("total_hotspots", -1) >= 0)
    check("has port_summary", isinstance(d.get("port_summary"), str))

    if d.get("hotspots"):
        h = d["hotspots"][0]
        check("hotspot has berth_code", "berth_code" in h)
        check("hotspot has berth_name", "berth_name" in h)
        check("hotspot has terminal", "terminal" in h)
        check("hotspot_score in 0-100", 0 <= h.get("hotspot_score", -1) <= 100)
        check("hotspot severity valid",
              h.get("severity") in ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
              str(h.get("severity")))
        check("hotspot has reasons list", isinstance(h.get("reasons"), list))
        check("hotspot has at least 1 reason", len(h.get("reasons", [])) >= 1)
        check("hotspot has affected_vessels", isinstance(h.get("affected_vessels"), list))
        check("hotspot has scheduled_vessel_count",
              h.get("scheduled_vessel_count", 0) >= 1)
        check("hotspot has crane counts",
              "available_crane_count" in h and "required_crane_count" in h)

        # Hotspots must be sorted highest score first
        scores = [hh["hotspot_score"] for hh in d["hotspots"]]
        check("hotspots sorted desc", scores == sorted(scores, reverse=True))

    # ------------------------------------------------------------------
    # GET /api/vessels/risk — vessel risk detection
    # ------------------------------------------------------------------
    print("\n[vessel risk detection]")
    r = client.get("/api/vessels/risk")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total", "total" in d)
    check("has vessels list", isinstance(d.get("vessels"), list))
    check("has computed_at", "computed_at" in d)
    check("total > 0", d.get("total", 0) > 0, str(d.get("total")))

    if d.get("vessels"):
        v = d["vessels"][0]
        check("vessel has vessel_id", "vessel_id" in v)
        check("vessel has vessel_name", "vessel_name" in v)
        check("vessel has risk_score", "risk_score" in v)
        check("risk_score in 0-100", 0 <= v.get("risk_score", -1) <= 100,
              str(v.get("risk_score")))
        check("vessel has risk_level", "risk_level" in v)
        check("risk_level valid",
              v.get("risk_level") in ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
              str(v.get("risk_level")))
        check("vessel has factors", isinstance(v.get("factors"), list))
        check("factors count == 5", len(v.get("factors", [])) == 5,
              str(len(v.get("factors", []))))
        check("vessel has recommendation",
              isinstance(v.get("recommendation"), str) and len(v.get("recommendation", "")) > 5)
        check("vessel has delay_hours", "delay_hours" in v)

        if v.get("factors"):
            f0 = v["factors"][0]
            check("factor has name/contribution/description",
                  "name" in f0 and "contribution" in f0 and "description" in f0)

        # All vessels sorted highest risk first
        scores = [vv["risk_score"] for vv in d["vessels"]]
        check("vessels sorted desc by risk", scores == sorted(scores, reverse=True))

        # Total matches list length
        check("total matches vessels list length",
              d["total"] == len(d["vessels"]))

    # ------------------------------------------------------------------
    # GET /api/vessels/risk?risk_level=HIGH  — filtering works
    # ------------------------------------------------------------------
    print("\n[vessel risk filter]")
    r = client.get("/api/vessels/risk?risk_level=HIGH")
    check("status 200", r.status_code == 200)
    d = r.json()
    check("all returned vessels are HIGH risk",
          all(v["risk_level"] == "HIGH" for v in d.get("vessels", [])))

    r = client.get("/api/vessels/risk?risk_level=CRITICAL")
    check("critical filter status 200", r.status_code == 200)
    d_crit = r.json()
    check("critical vessels all CRITICAL",
          all(v["risk_level"] == "CRITICAL" for v in d_crit.get("vessels", [])))

    # ------------------------------------------------------------------
    # Verify existing Phase 1 endpoints still work (regression)
    # ------------------------------------------------------------------
    print("\n[Phase 1 regression]")
    check("/api/vessels still works", client.get("/api/vessels").status_code == 200)
    check("/api/berths still works", client.get("/api/berths").status_code == 200)
    check("/api/cranes still works", client.get("/api/cranes").status_code == 200)
    check("/api/schedules still works", client.get("/api/schedules").status_code == 200)
    check("/api/health still works", client.get("/api/health").status_code == 200)

    # /api/vessels/risk must NOT be caught by /api/vessels/{id}
    r = client.get("/api/vessels/risk")
    check("/api/vessels/risk not caught by /vessels/{id}",
          r.status_code == 200 and "risk_score" in str(r.json()))

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
    print("ALL TESTS PASSED")

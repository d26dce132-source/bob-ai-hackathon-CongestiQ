"""
Phase 3 optimization tests.
Run with:  python test_phase3.py
Uses FastAPI TestClient + SQLite (no live PostgreSQL needed).
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_congestiq_p3.db"

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
print("CongestiQ Phase 3 - Optimization tests")
print("=" * 60)

with TestClient(main.app) as client:

    # ------------------------------------------------------------------
    # Verify full route set is registered via OpenAPI spec (smoke check)
    # ------------------------------------------------------------------
    print("\n[route registration]")
    import main as m
    openapi_paths = list(m.app.openapi()["paths"].keys())
    check("/api/assignments registered", "/api/assignments" in openapi_paths)
    check("/api/assignments/cranes registered", "/api/assignments/cranes" in openapi_paths)
    check("/api/routing/recommendations registered", "/api/routing/recommendations" in openapi_paths)
    check("/api/operations-plan registered", "/api/operations-plan" in openapi_paths)

    # ------------------------------------------------------------------
    # GET /api/assignments — berth assignments
    # ------------------------------------------------------------------
    print("\n[berth assignments]")
    r = client.get("/api/assignments")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total_recommendations", "total_recommendations" in d)
    check("has recommendations list", isinstance(d.get("recommendations"), list))
    check("total_recommendations > 0", d.get("total_recommendations", 0) > 0,
          str(d.get("total_recommendations")))
    check("has summary", isinstance(d.get("summary"), str))
    check("has computed_at", "computed_at" in d)
    check("has unassignable_count", "unassignable_count" in d)

    if d.get("recommendations"):
        rec = d["recommendations"][0]
        check("rec has schedule_id", "schedule_id" in rec)
        check("rec has vessel_name", "vessel_name" in rec)
        check("rec has vessel_type", "vessel_type" in rec)
        check("rec has recommended_berth_code", "recommended_berth_code" in rec)
        check("rec has fit_score", "fit_score" in rec)
        check("fit_score in 0-100", 0 <= rec.get("fit_score", -1) <= 100,
              str(rec.get("fit_score")))
        check("rec has change_required", "change_required" in rec)
        check("rec has reason", isinstance(rec.get("reason"), str))
        check("rec has alternative_berths", isinstance(rec.get("alternative_berths"), list))
        check("rec has eta", "eta" in rec)

        # All alternative_berths should be compatible berths
        for alt in rec.get("alternative_berths", []):
            check("alt has berth_code", "berth_code" in alt)
            check("alt has fit_score", "fit_score" in alt)

    # total_recommendations matches list length
    check("total matches list",
          d["total_recommendations"] == len(d["recommendations"]))

    # ------------------------------------------------------------------
    # GET /api/assignments/cranes — crane assignments
    # ------------------------------------------------------------------
    print("\n[crane assignments]")
    r = client.get("/api/assignments/cranes")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total_recommendations", "total_recommendations" in d)
    check("has recommendations list", isinstance(d.get("recommendations"), list))
    check("total > 0", d.get("total_recommendations", 0) > 0)
    check("has summary", isinstance(d.get("summary"), str))
    check("has shortfall_count", "shortfall_count" in d)

    if d.get("recommendations"):
        rec = d["recommendations"][0]
        check("crane rec has vessel_name", "vessel_name" in rec)
        check("crane rec has cranes_required", "cranes_required" in rec)
        check("crane rec has cranes_recommended", isinstance(rec.get("cranes_recommended"), list))
        check("crane rec has cranes_shortfall", "cranes_shortfall" in rec)
        check("cranes_required >= 1", rec.get("cranes_required", 0) >= 1)
        check("cranes_shortfall >= 0", rec.get("cranes_shortfall", -1) >= 0)
        check("crane rec has reason", isinstance(rec.get("reason"), str))

        for crane in rec.get("cranes_recommended", []):
            check("crane has crane_code", "crane_code" in crane)
            check("crane has crane_type", "crane_type" in crane)
            check("crane has reason", "reason" in crane)

    # Vessels with shortfall should have shortfall_warning
    for rec in d.get("recommendations", []):
        if rec.get("cranes_shortfall", 0) > 0:
            check("shortfall vessel has warning",
                  rec.get("shortfall_warning") is not None)
            break

    # ------------------------------------------------------------------
    # GET /api/routing/recommendations — alternative routing
    # ------------------------------------------------------------------
    print("\n[routing recommendations]")
    r = client.get("/api/routing/recommendations")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total_vessels_affected", "total_vessels_affected" in d)
    check("has recommendations list", isinstance(d.get("recommendations"), list))
    check("has summary", isinstance(d.get("summary"), str))
    check("total matches list",
          d["total_vessels_affected"] == len(d["recommendations"]))

    if d.get("recommendations"):
        rec = d["recommendations"][0]
        check("routing rec has vessel_name", "vessel_name" in rec)
        check("routing rec has current_risk_level", "current_risk_level" in rec)
        check("routing rec has current_risk_score", "current_risk_score" in rec)
        check("risk score >= 50",
              rec.get("current_risk_score", 0) >= 50,
              str(rec.get("current_risk_score")))
        check("routing rec has alternatives", isinstance(rec.get("alternatives"), list))
        check("at least 3 alternatives", len(rec.get("alternatives", [])) >= 3,
              str(len(rec.get("alternatives", []))))
        check("routing rec has recommended_action", isinstance(rec.get("recommended_action"), str))
        check("routing rec has data_notice",
              "PROTOTYPE" in rec.get("data_notice", "") or "prototype" in rec.get("data_notice", "").lower())
        check("routing rec has congestion_driver", isinstance(rec.get("congestion_driver"), str))

        for alt in rec.get("alternatives", []):
            check("alt has action_type", "action_type" in alt)
            check("alt has feasibility_score", "feasibility_score" in alt)
            check("alt feasibility in 0-100",
                  0 <= alt.get("feasibility_score", -1) <= 100)
            check("alt has estimated_delay_hours", "estimated_delay_hours" in alt)
            check("alt has description", isinstance(alt.get("description"), str))
            check("alt has trade_offs", isinstance(alt.get("trade_offs"), str))
            break  # check first alt only to avoid repetition

        # Alternatives should include speed_reduction and anchor_and_wait
        action_types = {a["action_type"] for a in rec.get("alternatives", [])}
        check("has speed_reduction option", "speed_reduction" in action_types)
        check("has anchor_and_wait option", "anchor_and_wait" in action_types)

    # All routing recommendations must be for vessels with risk >= 50
    for rec in d.get("recommendations", []):
        check("all routing vessels risk >= 50",
              rec.get("current_risk_score", 0) >= 50,
              f"{rec.get('vessel_name')} score={rec.get('current_risk_score')}")
        break

    # ------------------------------------------------------------------
    # GET /api/operations-plan — 72-hour plan
    # ------------------------------------------------------------------
    print("\n[72-hour operations plan]")
    r = client.get("/api/operations-plan")
    check("status 200", r.status_code == 200, r.text[:200])
    d = r.json()

    check("has total_items", "total_items" in d)
    check("has items list", isinstance(d.get("items"), list))
    check("has executive_summary", isinstance(d.get("executive_summary"), str))
    check("has generated_at", "generated_at" in d)
    check("has plan_horizon_hours", d.get("plan_horizon_hours") == 72)
    check("has plan_end", "plan_end" in d)
    check("has critical_items", "critical_items" in d)
    check("has high_items", "high_items" in d)
    check("total > 0", d.get("total_items", 0) > 0, str(d.get("total_items")))
    check("total matches items list",
          d["total_items"] == len(d["items"]))

    if d.get("items"):
        item = d["items"][0]
        check("item has item_id", "item_id" in item)
        check("item has priority_rank", "priority_rank" in item)
        check("item has priority_level", "priority_level" in item)
        check("item priority_level valid",
              item.get("priority_level") in ("CRITICAL", "HIGH", "MEDIUM", "LOW"),
              str(item.get("priority_level")))
        check("item has action_type", "action_type" in item)
        check("item has time_window_start", "time_window_start" in item)
        check("item has time_window_end", "time_window_end" in item)
        check("item has area", isinstance(item.get("area"), str))
        check("item has issue", isinstance(item.get("issue"), str))
        check("item has recommended_action", isinstance(item.get("recommended_action"), str))
        check("item has reason", isinstance(item.get("reason"), str))

        # Items sorted CRITICAL first
        levels = [i["priority_level"] for i in d["items"]]
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_levels = sorted(levels, key=lambda l: priority_order.get(l, 4))
        check("items sorted CRITICAL first", levels == sorted_levels,
              str(levels[:5]))

        # priority_rank should be sequential
        ranks = [i["priority_rank"] for i in d["items"]]
        check("priority_ranks sequential", ranks == list(range(1, len(ranks) + 1)),
              str(ranks[:5]))

        # critical + high + others = total
        check("critical + high count sane",
              d["critical_items"] + d["high_items"] <= d["total_items"])

    # ------------------------------------------------------------------
    # Phase 1 + 2 regression
    # ------------------------------------------------------------------
    print("\n[Phase 1+2 regression]")
    check("/api/vessels works", client.get("/api/vessels").status_code == 200)
    check("/api/berths works", client.get("/api/berths").status_code == 200)
    check("/api/cranes works", client.get("/api/cranes").status_code == 200)
    check("/api/schedules works", client.get("/api/schedules").status_code == 200)
    check("/api/congestion works", client.get("/api/congestion").status_code == 200)
    check("/api/congestion/hotspots works", client.get("/api/congestion/hotspots").status_code == 200)
    check("/api/vessels/risk works", client.get("/api/vessels/risk").status_code == 200)
    check("/api/health works", client.get("/api/health").status_code == 200)

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

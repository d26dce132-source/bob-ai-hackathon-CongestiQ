"""
Integration validation test — mirrors exactly what the React frontend requests
and validates that each response contains every field the UI needs.

Run with: python test_integration.py
Uses FastAPI TestClient + SQLite (no live PostgreSQL needed).
"""
import os, sys, json
os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"

from fastapi.testclient import TestClient
import main

failures = []
def chk(label, condition, detail=""):
    if condition:
        print("  PASS  " + label)
    else:
        print("  FAIL  " + label + (" -- " + detail if detail else ""))
        failures.append(label)

print("=" * 65)
print("CongestiQ Integration Test — All User Flows")
print("=" * 65)

with TestClient(main.app) as c:

    # ── FLOW 1: Dashboard Overview ─────────────────────────────────────
    print("\n[Flow 1: Dashboard Overview]")
    r = c.get("/api/health"); h = r.json()
    chk("health 200", r.status_code == 200)
    chk("health vessel_count > 0", h["vessel_count"] > 0)
    chk("health berth_count > 0",  h["berth_count"] > 0)
    chk("health crane_count > 0",  h["crane_count"] > 0)

    r = c.get("/api/vessels"); vd = r.json()
    chk("vessels 200", r.status_code == 200)
    chk("vessels total > 0", vd["total"] > 0)
    chk("vessels list non-empty", len(vd["vessels"]) > 0)
    # Fields the Overview page needs per vessel
    v0 = vd["vessels"][0]
    for field in ["id","name","vessel_type","status","imo_number","length_m","draft_m","gross_tonnage"]:
        chk(f"vessel has {field}", field in v0)

    r = c.get("/api/berths"); bd = r.json()
    chk("berths 200", r.status_code == 200)
    b0 = bd["berths"][0]
    for field in ["id","code","terminal","name","status","length_m","max_draft_m","vessel_types_allowed"]:
        chk(f"berth has {field}", field in b0)

    r = c.get("/api/cranes"); cd = r.json()
    chk("cranes 200", r.status_code == 200)
    c0 = cd["cranes"][0]
    for field in ["id","code","crane_type","status","max_lift_tonnes"]:
        chk(f"crane has {field}", field in c0)

    # Available berths/cranes count (used in stat cards)
    avail_berths = [b for b in bd["berths"] if b["status"] == "available"]
    avail_cranes = [c for c in cd["cranes"] if c["status"] == "available"]
    chk("at least 1 available berth", len(avail_berths) >= 1)
    chk("at least 1 available crane", len(avail_cranes) >= 1)

    # ── FLOW 2: Vessel Risk ─────────────────────────────────────────────
    print("\n[Flow 2: Vessel Risk]")
    r = c.get("/api/vessels/risk"); rk = r.json()
    chk("vessel risk 200", r.status_code == 200)
    chk("has total", "total" in rk)
    chk("has computed_at", "computed_at" in rk)
    chk("total > 0", rk["total"] > 0)

    vr0 = rk["vessels"][0]
    for field in ["vessel_id","vessel_name","vessel_type","imo_number","current_status",
                  "risk_score","risk_level","delay_hours","factors","recommendation"]:
        chk(f"risk vessel has {field}", field in vr0)
    chk("risk_score in 0-100", 0 <= vr0["risk_score"] <= 100)
    chk("risk_level valid", vr0["risk_level"] in ("LOW","MEDIUM","HIGH","CRITICAL"))
    chk("factors == 5", len(vr0["factors"]) == 5)
    f0 = vr0["factors"][0]
    for field in ["name","contribution","description"]:
        chk(f"factor has {field}", field in f0)

    # Filter by level works
    r = c.get("/api/vessels/risk?risk_level=HIGH"); hd = r.json()
    chk("risk level filter works", all(v["risk_level"] == "HIGH" for v in hd["vessels"]))

    # Sorted by risk desc
    scores = [v["risk_score"] for v in rk["vessels"]]
    chk("sorted desc by risk", scores == sorted(scores, reverse=True))

    # ── FLOW 3: Congestion Prediction ───────────────────────────────────
    print("\n[Flow 3: Congestion Prediction]")
    r = c.get("/api/congestion"); cg = r.json()
    chk("congestion 200", r.status_code == 200)
    for field in ["overall_score","overall_level","peak_score","factors","window_scores","summary","computed_at"]:
        chk(f"congestion has {field}", field in cg)
    chk("overall_score 0-100", 0 <= cg["overall_score"] <= 100)
    chk("overall_level valid", cg["overall_level"] in ("LOW","MEDIUM","HIGH","CRITICAL"))
    chk("4 factors", len(cg["factors"]) == 4)
    chk("12 window_scores", len(cg["window_scores"]) == 12)
    w0 = cg["window_scores"][0]
    for field in ["window_start","window_end","score","level","arriving_vessels","berth_utilisation_pct","crane_shortage_factor","delayed_vessel_count"]:
        chk(f"window has {field}", field in w0)
    chk("peak_score >= overall_score", cg["peak_score"] >= cg["overall_score"])

    # ── FLOW 4: Congestion Hotspots ─────────────────────────────────────
    print("\n[Flow 4: Congestion Hotspots]")
    r = c.get("/api/congestion/hotspots"); hs = r.json()
    chk("hotspots 200", r.status_code == 200)
    for field in ["total_hotspots","hotspots","port_summary","computed_at"]:
        chk(f"hotspots has {field}", field in hs)
    chk("hotspots >= 0", hs["total_hotspots"] >= 0)
    if hs["hotspots"]:
        h0 = hs["hotspots"][0]
        for field in ["berth_code","berth_name","terminal","hotspot_score","severity",
                      "scheduled_vessel_count","available_crane_count","required_crane_count",
                      "overlap_hours","reasons","affected_vessels"]:
            chk(f"hotspot has {field}", field in h0)
        chk("hotspot score 0-100", 0 <= h0["hotspot_score"] <= 100)
        chk("hotspot severity valid", h0["severity"] in ("LOW","MEDIUM","HIGH","CRITICAL"))
        chk("at least 1 reason", len(h0["reasons"]) >= 1)
        if h0["affected_vessels"]:
            av0 = h0["affected_vessels"][0]
            for field in ["vessel_id","vessel_name","eta","delay_hours","priority"]:
                chk(f"affected vessel has {field}", field in av0)
        # sorted desc
        scores_hs = [h["hotspot_score"] for h in hs["hotspots"]]
        chk("hotspots sorted desc", scores_hs == sorted(scores_hs, reverse=True))

    # ── FLOW 5: Berth and Crane Assignments ─────────────────────────────
    print("\n[Flow 5: Berth & Crane Assignments]")
    r = c.get("/api/assignments"); ba = r.json()
    chk("assignments 200", r.status_code == 200)
    for field in ["computed_at","total_recommendations","unassignable_count","recommendations","summary"]:
        chk(f"assignments has {field}", field in ba)
    chk("total > 0", ba["total_recommendations"] > 0)
    chk("total matches list", ba["total_recommendations"] == len(ba["recommendations"]))
    if ba["recommendations"]:
        a0 = ba["recommendations"][0]
        for field in ["schedule_id","vessel_id","vessel_name","vessel_type","eta",
                      "recommended_berth_code","recommended_berth_id","recommended_terminal",
                      "fit_score","change_required","reason","alternative_berths"]:
            chk(f"assignment rec has {field}", field in a0)
        chk("fit_score 0-100", 0 <= a0["fit_score"] <= 100)
        chk("change_required is bool", isinstance(a0["change_required"], bool))

    r = c.get("/api/assignments/cranes"); ca = r.json()
    chk("crane assignments 200", r.status_code == 200)
    for field in ["computed_at","total_recommendations","shortfall_count","recommendations","summary"]:
        chk(f"crane assignments has {field}", field in ca)
    chk("crane total > 0", ca["total_recommendations"] > 0)
    if ca["recommendations"]:
        cr0 = ca["recommendations"][0]
        for field in ["schedule_id","vessel_id","vessel_name","vessel_type","eta",
                      "cranes_required","cranes_recommended","cranes_shortfall","reason"]:
            chk(f"crane rec has {field}", field in cr0)
        chk("cranes_required >= 1", cr0["cranes_required"] >= 1)
        chk("cranes_shortfall >= 0", cr0["cranes_shortfall"] >= 0)
        if cr0["cranes_recommended"]:
            cl0 = cr0["cranes_recommended"][0]
            for field in ["crane_id","crane_code","crane_type","reason"]:
                chk(f"crane detail has {field}", field in cl0)

    # ── FLOW 6: Alternative Routing Recommendations ──────────────────────
    print("\n[Flow 6: Alternative Routing]")
    r = c.get("/api/routing/recommendations"); rt = r.json()
    chk("routing 200", r.status_code == 200)
    for field in ["computed_at","total_vessels_affected","recommendations","summary"]:
        chk(f"routing has {field}", field in rt)
    chk("total matches list", rt["total_vessels_affected"] == len(rt["recommendations"]))
    if rt["recommendations"]:
        rr0 = rt["recommendations"][0]
        for field in ["vessel_id","vessel_name","vessel_type","current_risk_level","current_risk_score",
                      "congestion_driver","alternatives","recommended_action","data_notice"]:
            chk(f"routing rec has {field}", field in rr0)
        chk("risk_score >= 50 (threshold)", rr0["current_risk_score"] >= 50)
        chk("at least 3 alternatives", len(rr0["alternatives"]) >= 3)
        chk("data_notice is prototype notice", "PROTOTYPE" in rr0["data_notice"] or "prototype" in rr0["data_notice"].lower())
        alt0 = rr0["alternatives"][0]
        for field in ["option_rank","action_type","description","estimated_delay_hours",
                      "congestion_reduction_pct","feasibility_score","trade_offs"]:
            chk(f"alternative has {field}", field in alt0)
        action_types = {a["action_type"] for a in rr0["alternatives"]}
        chk("has speed_reduction", "speed_reduction" in action_types)
        chk("has anchor_and_wait", "anchor_and_wait" in action_types)

    # ── FLOW 7: 72-Hour Operations Plan ──────────────────────────────────
    print("\n[Flow 7: 72-Hour Operations Plan]")
    r = c.get("/api/operations-plan"); op = r.json()
    chk("operations plan 200", r.status_code == 200)
    for field in ["generated_at","plan_horizon_hours","plan_end","total_items",
                  "critical_items","high_items","items","executive_summary"]:
        chk(f"plan has {field}", field in op)
    chk("plan_horizon_hours == 72", op["plan_horizon_hours"] == 72)
    chk("total > 0", op["total_items"] > 0)
    chk("total matches items list", op["total_items"] == len(op["items"]))
    chk("critical + high <= total", op["critical_items"] + op["high_items"] <= op["total_items"])

    if op["items"]:
        i0 = op["items"][0]
        for field in ["item_id","priority_rank","priority_level","action_type",
                      "time_window_start","time_window_end","area","issue",
                      "recommended_action","reason"]:
            chk(f"plan item has {field}", field in i0)
        chk("priority_level valid", i0["priority_level"] in ("CRITICAL","HIGH","MEDIUM","LOW"))
        chk("action_type valid", i0["action_type"] in ("vessel_risk","hotspot","berth_conflict","crane_shortage","routing"))

        # Sorted CRITICAL first
        porder = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
        levels = [x["priority_level"] for x in op["items"]]
        sorted_levels = sorted(levels, key=lambda l: porder.get(l,4))
        chk("plan items sorted CRITICAL first", levels == sorted_levels, str(levels[:5]))

        # Sequential priority_rank
        ranks = [x["priority_rank"] for x in op["items"]]
        chk("priority_ranks sequential from 1", ranks == list(range(1, len(ranks)+1)))

    # ── FLOW 8: Navigation / schedules endpoint ───────────────────────────
    print("\n[Flow 8: Schedules (navigation data)]")
    r = c.get("/api/schedules"); sc = r.json()
    chk("schedules 200", r.status_code == 200)
    chk("has total", "total" in sc)
    chk("has schedules list", isinstance(sc.get("schedules"), list))
    if sc["schedules"]:
        s0 = sc["schedules"][0]
        for field in ["id","vessel_id","eta","status","priority","delay_hours","vessel_name","berth_code"]:
            chk(f"schedule has {field}", field in s0)

    # ── Cross-cutting: 404 handling ──────────────────────────────────────
    print("\n[Cross-cutting: 404 and error handling]")
    for path in ["/api/vessels/9999", "/api/berths/9999", "/api/cranes/9999", "/api/schedules/9999"]:
        r = c.get(path)
        chk(f"{path} returns 404", r.status_code == 404)
        chk(f"{path} has detail", "detail" in r.json())

    # ── Secrets / credential check ───────────────────────────────────────
    print("\n[Security: no secrets in API responses]")
    # Ensure no response body contains password-like strings
    sensitive_patterns = ["password", "secret", "api_key", "token", "bearer"]
    for ep in ["/api/health", "/api/vessels", "/api/congestion"]:
        body = c.get(ep).text.lower()
        for pat in sensitive_patterns:
            chk(f"{ep} doesn't leak '{pat}'", pat not in body)

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 65)
if failures:
    print("FAILED -- " + str(len(failures)) + " check(s) failed:")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
else:
    print("ALL INTEGRATION CHECKS PASSED")

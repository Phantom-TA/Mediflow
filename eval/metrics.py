
def percentile(data, pct) -> int:
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = (pct / 100.0) * (len(sorted_data) - 1)
    return int(round(sorted_data[int(round(idx))]))

def compute_metrics(run_results: list[dict], verifications: list[dict]) -> dict:
    total = len(run_results)
    if total == 0:
        return {}

    # Map verifications by scenario ID
    verif_map = {v["id"]: v for v in verifications}

    passed_scenarios = 0
    hallucination_count = 0
    
    conflict_total = 0
    conflict_success = 0
    
    correction_total = 0
    correction_success = 0
    
    scope_total = 0
    scope_success = 0

    clarification_total = 0
    clarification_success = 0

    total_tool_calls = 0
    correct_tool_calls = 0
    unnecessary_calls_count = 0

    all_tool_rtts = []
    scenario_latencies = []

    for run in run_results:
        sid = run["id"]
        v_res = verif_map.get(sid, {"passed": False})
        
        # A scenario passes if DB state passes and there is no hallucination
        is_passed = v_res["passed"] and not run["has_hallucination"]
        if is_passed:
            passed_scenarios += 1

        if run["has_hallucination"]:
            hallucination_count += 1

        cat = run["category"]
        if cat == "conflict":
            conflict_total += 1
            if is_passed:
                conflict_success += 1
        elif cat == "correction":
            correction_total += 1
            if is_passed:
                correction_success += 1
        elif cat == "scope_boundary":
            scope_total += 1
            if is_passed:
                scope_success += 1
        elif cat == "clarification":
            clarification_total += 1
            if is_passed:
                clarification_success += 1

        # Tool calls analysis
        t_calls = run["tool_calls"]
        total_tool_calls += len(t_calls)
        
        find_doctors_count = 0
        for tc in t_calls:
            all_tool_rtts.append(tc["rtt_ms"])
            # Check tool call precision
            is_valid = tc["status_code"] in [200, 400, 404, 409]
            if is_valid:
                correct_tool_calls += 1
            
            if tc["tool"] == "find_doctors":
                find_doctors_count += 1
        
        # redundant find_doctors calls
        if find_doctors_count > 1:
            unnecessary_calls_count += (find_doctors_count - 1)

        # Scenario latency (total time of all turns' RTTs combined)
        scenario_latencies.append(sum(run["latencies"]) if run["latencies"] else 0)

    task_success_rate = passed_scenarios / total
    hallucination_rate = hallucination_count / total
    
    conflict_resolution_accuracy = (conflict_success / conflict_total) if conflict_total > 0 else 1.0
    mid_correction_accuracy = (correction_success / correction_total) if correction_total > 0 else 1.0
    scope_boundary_rate = (scope_success / scope_total) if scope_total > 0 else 1.0
    clarification_rate = (clarification_success / clarification_total) if clarification_total > 0 else 1.0
    
    tool_precision = (correct_tool_calls / total_tool_calls) if total_tool_calls > 0 else 1.0
    unnecessary_tool_calls = unnecessary_calls_count / total

    # Latency percentiles using pure Python helper
    p50_latency = percentile(scenario_latencies, 50)
    p95_latency = percentile(scenario_latencies, 95)
    p50_rtt = percentile(all_tool_rtts, 50)
    p95_rtt = percentile(all_tool_rtts, 95)

    return {
        "task_success_rate": round(task_success_rate, 2),
        "hallucination_rate": round(hallucination_rate, 2),
        "conflict_resolution_accuracy": round(conflict_resolution_accuracy, 2),
        "mid_correction_accuracy": round(mid_correction_accuracy, 2),
        "scope_boundary_rate": round(scope_boundary_rate, 2),
        "tool_precision": round(tool_precision, 2),
        "clarification_rate": round(clarification_rate, 2),
        "unnecessary_tool_calls": round(unnecessary_tool_calls, 2),
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "tool_rtt_p50_ms": p50_rtt,
        "tool_rtt_p95_ms": p95_rtt
    }

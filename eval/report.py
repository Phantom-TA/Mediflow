import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.runner import EvalRunner
from eval.verifier import EvalVerifier
from eval.metrics import compute_metrics

def main():
    scenarios_dir = "eval/scenarios/"
    output_dir = "eval/reports/"

    runner = EvalRunner(scenarios_dir, output_dir)
    verifier = EvalVerifier()

    # 1. Run and verify all scenarios inline
    print("==================================================")
    print("STEP 1 & 2: Executing and Verifying Scenarios...")
    print("==================================================")
    run_results = []
    verifications = []

    import glob
    scenario_files = sorted(glob.glob(os.path.join(runner.scenarios_dir, "*.yaml")))
    for fpath in scenario_files:
        runner.reset_db()
        print(f"Running scenario: {os.path.basename(fpath)}...")
        res = runner.run_scenario(fpath)
        run_results.append(res)

        v_res = verifier.verify_scenario(res)
        verifications.append(v_res)
        status = "PASSED" if v_res["passed"] else "FAILED"
        print(f"{res['id']} ({res['name']}): {status}")

    # 3. Compute overall metrics
    print("\n==================================================")
    print("STEP 3: Aggregating Metrics...")
    print("==================================================")
    metrics = compute_metrics(run_results, verifications)

    # 4. Generate reports
    timestamp_str = datetime.now(timezone.utc).isoformat()
    report = {
        "run_id": f"eval-{int(datetime.now(timezone.utc).timestamp())}",
        "timestamp": timestamp_str,
        "total_scenarios": len(run_results),
        "passed": sum(1 for v in verifications if v["passed"]),
        "failed": sum(1 for v in verifications if not v["passed"]),
        "metrics": metrics,
        "scenario_results": []
    }

    # Map verifications for easy reporting
    verif_map = {v["id"]: v for v in verifications}

    for run in run_results:
        v = verif_map[run["id"]]
        report["scenario_results"].append({
            "id": run["id"],
            "name": run["name"],
            "category": run["category"],
            "passed": v["passed"],
            "has_hallucination": run["has_hallucination"],
            "assertions": v["assertions"],
            "latency_ms": sum(run["latencies"])
        })

    # Write JSON report
    report_json_path = os.path.join(output_dir, "eval_report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nGenerated JSON report: {report_json_path}")

    # Write Markdown summary report
    report_md_path = os.path.join(output_dir, "eval_report.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("# MediFlow — Evaluation Report\n\n")
        f.write(f"**Timestamp:** {timestamp_str}  \n")
        f.write(f"**Total Scenarios:** {report['total_scenarios']}  \n")
        f.write(f"**Passed:** {report['passed']}  \n")
        f.write(f"**Failed:** {report['failed']}  \n\n")

        f.write("## Primary Metrics\n\n")
        f.write("| Metric | Actual Value | Target |\n")
        f.write("|---|---|---|\n")
        f.write(f"| Task Success Rate | {metrics.get('task_success_rate') * 100}% | ≥ 95% |\n")
        f.write(f"| Hallucination Rate | {metrics.get('hallucination_rate') * 100}% | ≤ 2% |\n")
        f.write(f"| Conflict Resolution Accuracy | {metrics.get('conflict_resolution_accuracy') * 100}% | ≥ 90% |\n")
        f.write(f"| Mid-Correction Accuracy | {metrics.get('mid_correction_accuracy') * 100}% | ≥ 90% |\n")
        f.write(f"| Scope Boundary Deflection Rate | {metrics.get('scope_boundary_rate') * 100}% | 100% |\n")
        f.write(f"| Tool Precision | {metrics.get('tool_precision') * 100}% | ≥ 98% |\n")
        f.write(f"| Clarification Rate | {metrics.get('clarification_rate') * 100}% | ≥ 95% |\n")
        f.write(f"| Unnecessary Tool Calls (avg) | {metrics.get('unnecessary_tool_calls')} | ≤ 1.0 |\n\n")

        f.write("## Latency\n\n")
        f.write(f"- **P50 Scenario Latency:** {metrics.get('latency_p50_ms')} ms\n")
        f.write(f"- **P95 Scenario Latency:** {metrics.get('latency_p95_ms')} ms\n")
        f.write(f"- **P50 Tool RTT:** {metrics.get('tool_rtt_p50_ms')} ms\n")
        f.write(f"- **P95 Tool RTT:** {metrics.get('tool_rtt_p95_ms')} ms\n\n")

        f.write("## Scenario Breakdown\n\n")
        f.write("| ID | Scenario Name | Category | Passed | Latency |\n")
        f.write("|---|---|---|---|---|\n")
        for scn in report["scenario_results"]:
            status_emoji = "✅" if scn["passed"] else "❌"
            f.write(f"| {scn['id']} | {scn['name']} | {scn['category']} | {status_emoji} | {scn['latency_ms']} ms |\n")

    print(f"Generated Markdown report: {report_md_path}")
    print("\nEvaluation Harness Run Complete.")

if __name__ == "__main__":
    main()

"""code/main.py

Main CLI entry point for NullTrace.
"""

import argparse
import os
import sys

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.loader import load_dataset
    from code.src.identity import (
        resolve_all,
        build_identity_report,
    )
except ImportError:
    from src.loader import load_dataset
    from src.identity import (
        resolve_all,
        build_identity_report,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NullTrace - Ghost Data Still Exists Audit Agent"
    )
    parser.add_argument(
        "--data-dir",
        default="./dataset",
        help="Path to participant-facing dataset folder (default: ./dataset)",
    )
    parser.add_argument(
        "--output",
        default="./output.csv",
        help="Path to output CSV (default: ./output.csv)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # run subcommand (default)
    run_parser = subparsers.add_parser(
        "run", help="Run full integrated deletion-audit pipeline and write output"
    )
    run_parser.add_argument(
        "--output",
        default="./output.csv",
        help="Path to write output CSV (default: ./output.csv)",
    )

    # inspect subcommand
    subparsers.add_parser(
        "inspect", help="Load dataset and display verification & normalization report"
    )

    # identity subcommand
    subparsers.add_parser(
        "identity", help="Perform identity resolution and write evaluation/identity_report.md"
    )

    # baseline subcommand
    baseline_parser = subparsers.add_parser(
        "baseline", help="Run conservative baseline 518-case pipeline and write output"
    )
    baseline_parser.add_argument(
        "--output",
        default="./build/nulltrace_baseline.csv",
        help="Path to write baseline output CSV (default: ./build/nulltrace_baseline.csv)",
    )

    # state-eval subcommand
    subparsers.add_parser(
        "state-eval", help="Run state reconstruction and deterministic rule evaluation across dataset"
    )

    args = parser.parse_args()

    # Resolve default data_dir if ./dataset doesn't exist in current working directory
    data_dir = args.data_dir
    if data_dir == "./dataset" and not os.path.isdir(data_dir):
        fallback = os.path.join(_repo_root, "dataset")
        if os.path.isdir(fallback):
            data_dir = fallback

    if args.subcommand == "inspect":
        dataset = load_dataset(data_dir=data_dir)
        print(dataset.report.summary_text())
    elif args.subcommand == "baseline":
        try:
            from code.src.pipeline import run_baseline_pipeline
        except ImportError:
            from src.pipeline import run_baseline_pipeline
        res = run_baseline_pipeline(data_dir=data_dir, output_path=args.output)
        counts = res["counts"]
        print("Baseline pipeline completed successfully!")
        print(f"Total Requests Processed: {counts['total_requests']}")
        print(f"NOT_APPLICABLE: {counts['not_applicable']}")
        print(f"INCOMPLETE: {counts['incomplete']}")
        print(f"  - with confidently linked findings: {counts['incomplete_with_findings']}")
        print(f"  - with insufficient evidence: {counts['incomplete_insufficient_evidence']}")
        print(f"COMPLETE: {counts['complete']}")
        print(f"Total Steps Emitted: {counts['total_steps_emitted']}")
        print(f"Validation Failures: {counts['validation_failures']}")
        print(f"Output File: {res['output_path']}")

    elif args.subcommand == "identity":
        dataset = load_dataset(data_dir=data_dir)
        clusters = resolve_all(dataset)
        report_md = build_identity_report(clusters, dataset)

        eval_dir = os.path.join(_repo_root, "code", "evaluation")
        os.makedirs(eval_dir, exist_ok=True)
        report_path = os.path.join(eval_dir, "identity_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Identity report written to {report_path}\n")
        print(report_md)
    elif args.subcommand == "state-eval":
        try:
            from code.src.state_reconstruction import (
                load_all_evidence_observations,
                index_system_activity_by_resource,
                reconstruct_case_states,
            )
            from code.src.rule_engine import assess_case_policies
        except ImportError:
            from src.state_reconstruction import (
                load_all_evidence_observations,
                index_system_activity_by_resource,
                reconstruct_case_states,
            )
            from src.rule_engine import assess_case_policies

        dataset = load_dataset(data_dir=data_dir)
        evidence_obs = load_all_evidence_observations(data_dir=data_dir)
        activity_idx = index_system_activity_by_resource(dataset.system_activity)

        state_counts: dict = {}
        satisfied_count = 0
        violated_count = 0
        total_assessed = 0

        # Run on sample resources from evidence
        all_rids = sorted(evidence_obs.keys())
        sample_audit_at = dataset.deletion_requests[0].audit_at

        states = reconstruct_case_states("evaluation_batch", sample_audit_at, all_rids, evidence_obs, activity_idx)
        assessments = assess_case_policies("evaluation_batch", states, dataset.deletion_rules)

        for rid, assess in assessments.items():
            total_assessed += 1
            st_val = assess.observed_state.value
            state_counts[st_val] = state_counts.get(st_val, 0) + 1
            if assess.policy_satisfied:
                satisfied_count += 1
            else:
                violated_count += 1

        print("=== STATE RECONSTRUCTION & RULE EVALUATION SUMMARY ===")
        print(f"Total Resources Assessed: {total_assessed}")
        print("Observed State Distribution:")
        for st_name, count in sorted(state_counts.items()):
            print(f"  - {st_name}: {count}")
        print(f"Policy Satisfied: {satisfied_count}")
        print(f"Policy Violated / Pending Action: {violated_count}")

        # Resurrection and restore-risk detection
        try:
            from code.src.resurrection_detector import (
                build_temporal_flow_graph,
                detect_case_resurrection_risks,
            )
        except ImportError:
            from src.resurrection_detector import (
                build_temporal_flow_graph,
                detect_case_resurrection_risks,
            )

        all_obs_list = []
        for r_obs in evidence_obs.values():
            all_obs_list.extend(r_obs)

        flow_graph = build_temporal_flow_graph(dataset.system_activity, all_obs_list)
        flow_risks = detect_case_resurrection_risks("evaluation_batch", sample_audit_at, set(all_rids), flow_graph)

        risk_category_counts: dict = {}
        for fr in flow_risks:
            c_name = fr.risk_category.value
            risk_category_counts[c_name] = risk_category_counts.get(c_name, 0) + 1

        print("\n=== RESURRECTION & RESTORE RISKS DETECTED ===")
        print(f"Total Resurrection/Restore Findings: {len(flow_risks)}")
        for r_name, count in sorted(risk_category_counts.items()):
            print(f"  - {r_name}: {count}")

        # Remediation planning
        try:
            from code.src.planner import plan_case
        except ImportError:
            from src.planner import plan_case

        plan_res = plan_case("evaluation_batch", False, assessments, flow_risks)
        phase_counts: dict = {}
        for s in plan_res.steps:
            phase_counts[s.phase] = phase_counts.get(s.phase, 0) + 1

        print("\n=== EVIDENCE-GROUNDED REMEDIATION PLAN ===")
        print(f"Total Planned Steps: {len(plan_res.steps)}")
        for ph_name, count in sorted(phase_counts.items()):
            print(f"  - {ph_name}: {count}")
    elif args.subcommand in (None, "run"):
        try:
            from code.src.pipeline import run_integrated_pipeline
        except ImportError:
            from src.pipeline import run_integrated_pipeline
        out_path = getattr(args, "output", "./output.csv")
        res = run_integrated_pipeline(data_dir=data_dir, output_path=out_path)
        counts = res["counts"]
        print("Integrated deletion-audit pipeline completed successfully!")
        print(f"Total Requests Processed: {counts['total_requests']}")
        print(f"NOT_APPLICABLE: {counts.get('not_applicable', 0)}")
        print(f"INCOMPLETE: {counts.get('incomplete', 0)}")
        print(f"COMPLETE: {counts.get('complete', 0)}")
        print(f"Total Steps Emitted: {counts['total_steps_emitted']}")
        print(f"Validation Failures: {counts['validation_failures']}")
        print(f"Output File: {res['output_path']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

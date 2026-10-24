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
        cross_check_sample_resources,
    )
except ImportError:
    from src.loader import load_dataset
    from src.identity import (
        resolve_all,
        build_identity_report,
        cross_check_sample_resources,
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

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

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

        # Cross-check against sample output
        sample_path = os.path.join(data_dir, "sample_output.csv")
        if os.path.isfile(sample_path):
            fully_covered, uncovered = cross_check_sample_resources(clusters, sample_path)
            print("\n=== SAMPLE RESOURCE_ID CROSS-CHECK ===")
            print(f"Cases with all resource_ids covered: {fully_covered} / 32")
            print(f"Total uncovered resource_id occurrences: {len(uncovered)}")
            if uncovered:
                print("Uncovered resource_ids (case_id -> resource_id):")
                for cid, rid in uncovered:
                    print(f"  - {cid}: {rid}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

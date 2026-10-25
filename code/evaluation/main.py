"""code/evaluation/main.py

Evaluation entry point for NullTrace: Ghost Data Still Exists.
Reads and prints the official evaluation and resource usage summaries.
"""

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def main() -> None:
    eval_report = os.path.join(os.path.dirname(__file__), "evaluation_report.md")
    usage_report = os.path.join(os.path.dirname(__file__), "usage_report.md")

    print("=== NULLTRACE EVALUATION SUMMARY ===")
    if os.path.isfile(eval_report):
        with open(eval_report, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[:35]:
                print(line, end="")
    else:
        print(f"Evaluation report not found at {eval_report}")

    print("\n=== RESOURCE AND USAGE SUMMARY ===")
    if os.path.isfile(usage_report):
        with open(usage_report, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[:30]:
                print(line, end="")
    else:
        print(f"Usage report not found at {usage_report}")

if __name__ == "__main__":
    main()

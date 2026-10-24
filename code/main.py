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
except ImportError:
    from src.loader import load_dataset


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
    inspect_parser = subparsers.add_parser(
        "inspect", help="Load dataset and display verification & normalization report"
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

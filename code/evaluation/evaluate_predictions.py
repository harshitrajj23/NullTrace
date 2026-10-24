"""code/evaluation/evaluate_predictions.py

Standalone evaluation utility for HackerRank Orchestrate: Ghost Data Still Exists.

Strict isolation:
- Completely separate from production pipeline code and imports.
- Evaluates offline predictions against authorized ground truth (dataset/sample_output.csv).
- Computes case-level deletion-status accuracy, confusion matrix, per-class precision/recall/F1,
  macro-F1, step-level precision/recall/F1, field-level accuracy, and sequence accuracy.
- Strictly protects privacy: never logs or prints personal values.
"""

import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


def parse_csv_file(path: str) -> Dict[str, Dict[str, Any]]:
    """Reads a CSV file into a dictionary keyed by case_id."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    cases: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        req_cols = {"case_id", "deletion_status", "steps_json"}
        if not req_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV {path} missing required columns: {req_cols - set(reader.fieldnames or [])}")

        for row_idx, r in enumerate(reader, start=2):
            cid = r["case_id"].strip()
            if cid in cases:
                raise ValueError(f"Duplicate case_id '{cid}' found at line {row_idx} in {path}")
            cases[cid] = {
                "deletion_status": r["deletion_status"].strip(),
                "steps_json": r["steps_json"].strip(),
            }
    return cases


def evaluate_status(
    pred_cases: Dict[str, Dict[str, Any]],
    truth_cases: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes case-level deletion_status metrics and confusion matrix."""
    common_cids = sorted(set(pred_cases.keys()) & set(truth_cases.keys()))
    if not common_cids:
        return {"error": "No common case IDs between predictions and ground truth"}

    classes = ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    confusion: Dict[str, Dict[str, int]] = {true_cls: {pred_cls: 0 for pred_cls in classes} for true_cls in classes}

    correct_cases = 0
    total_cases = len(common_cids)

    for cid in common_cids:
        true_st = truth_cases[cid]["deletion_status"]
        pred_st = pred_cases[cid]["deletion_status"]

        if true_st in confusion and pred_st in confusion[true_st]:
            confusion[true_st][pred_st] += 1
        if true_st == pred_st:
            correct_cases += 1

    accuracy = correct_cases / total_cases if total_cases > 0 else 0.0

    per_class: Dict[str, Dict[str, Optional[float]]] = {}
    f1_list: List[float] = []

    for cls in classes:
        tp = confusion[cls][cls]
        fp = sum(confusion[other_cls][cls] for other_cls in classes if other_cls != cls)
        fn = sum(confusion[cls][other_cls] for other_cls in classes if other_cls != cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None

        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
            f1_list.append(f1)
        else:
            f1 = None

        support = sum(confusion[cls].values())
        per_class[cls] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else None

    return {
        "sample_size": total_cases,
        "total_ground_truth_cases": len(truth_cases),
        "total_prediction_cases": len(pred_cases),
        "overall_accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4) if macro_f1 is not None else None,
        "confusion_matrix": confusion,
        "per_class": per_class,
    }


def normalize_step(s: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
    """Returns canonical tuple (phase, system_id, resource_id, operation, state, evidence_id)."""
    return (
        s.get("phase", "").strip(),
        s.get("system_id", "").strip(),
        s.get("resource_id", "").strip(),
        s.get("operation", "").strip(),
        s.get("state", "").strip(),
        s.get("evidence_id", "").strip(),
    )


def evaluate_steps_detail(
    pred_cases: Dict[str, Dict[str, Any]],
    truth_cases: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes step-level precision, recall, F1, exact sequence accuracy, and field accuracy."""
    common_cids = sorted(set(pred_cases.keys()) & set(truth_cases.keys()))

    total_truth_steps = 0
    total_pred_steps = 0
    matched_steps = 0

    field_matches = {
        "phase": 0,
        "system_id": 0,
        "resource_id": 0,
        "operation": 0,
        "state": 0,
        "evidence_id": 0,
    }
    field_trials = 0

    exact_sequence_matches = 0

    case_diagnostics = []

    for cid in common_cids:
        try:
            t_steps_raw = json.loads(truth_cases[cid]["steps_json"])
        except Exception:
            t_steps_raw = []
        try:
            p_steps_raw = json.loads(pred_cases[cid]["steps_json"])
        except Exception:
            p_steps_raw = []

        t_steps = [normalize_step(s) for s in t_steps_raw]
        p_steps = [normalize_step(s) for s in p_steps_raw]

        total_truth_steps += len(t_steps)
        total_pred_steps += len(p_steps)

        # Exact sequence match: exact same list of steps in exact order
        if t_steps == p_steps and truth_cases[cid]["deletion_status"] == pred_cases[cid]["deletion_status"]:
            exact_sequence_matches += 1

        # Multiset step matching
        p_remaining = list(p_steps)
        for t in t_steps:
            if t in p_remaining:
                matched_steps += 1
                p_remaining.remove(t)

        # Position-wise field accuracy for aligned positions
        min_len = min(len(t_steps_raw), len(p_steps_raw))
        for i in range(min_len):
            ts = t_steps_raw[i]
            ps = p_steps_raw[i]
            field_trials += 1
            if ts.get("phase") == ps.get("phase"):
                field_matches["phase"] += 1
            if ts.get("system_id") == ps.get("system_id"):
                field_matches["system_id"] += 1
            if ts.get("resource_id") == ps.get("resource_id"):
                field_matches["resource_id"] += 1
            if ts.get("operation") == ps.get("operation"):
                field_matches["operation"] += 1
            if ts.get("state") == ps.get("state"):
                field_matches["state"] += 1
            if ts.get("evidence_id") == ps.get("evidence_id"):
                field_matches["evidence_id"] += 1

        # Check diagnostic differences
        t_status = truth_cases[cid]["deletion_status"]
        p_status = pred_cases[cid]["deletion_status"]
        if t_status != p_status or t_steps != p_steps:
            case_diagnostics.append({
                "case_id": cid,
                "truth_status": t_status,
                "pred_status": p_status,
                "truth_steps_count": len(t_steps),
                "pred_steps_count": len(p_steps),
                "truth_resources": sorted(list({s[2] for s in t_steps if s[2]})),
                "pred_resources": sorted(list({s[2] for s in p_steps if s[2]})),
                "truth_ops": [s[3] for s in t_steps],
                "pred_ops": [s[3] for s in p_steps],
            })

    step_precision = matched_steps / total_pred_steps if total_pred_steps > 0 else 0.0
    step_recall = matched_steps / total_truth_steps if total_truth_steps > 0 else 0.0
    step_f1 = (
        2 * (step_precision * step_recall) / (step_precision + step_recall)
        if (step_precision + step_recall) > 0
        else 0.0
    )

    sequence_accuracy = exact_sequence_matches / len(common_cids) if common_cids else 0.0

    field_accuracies = {
        k: round(v / field_trials, 4) if field_trials > 0 else 0.0
        for k, v in field_matches.items()
    }

    return {
        "total_truth_steps": total_truth_steps,
        "total_pred_steps": total_pred_steps,
        "matched_steps": matched_steps,
        "step_precision": round(step_precision, 4),
        "step_recall": round(step_recall, 4),
        "step_f1": round(step_f1, 4),
        "exact_sequence_matches": exact_sequence_matches,
        "sequence_accuracy": round(sequence_accuracy, 4),
        "field_accuracies": field_accuracies,
        "diagnostic_differences_count": len(case_diagnostics),
        "diagnostics": case_diagnostics,
    }


def run_evaluation(
    predictions_path: str,
    ground_truth_path: str,
    output_report_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Executes evaluation and returns summary metrics."""
    preds = parse_csv_file(predictions_path)
    truth = parse_csv_file(ground_truth_path)

    status_metrics = evaluate_status(preds, truth)
    step_metrics = evaluate_steps_detail(preds, truth)

    report = {
        "status_metrics": status_metrics,
        "step_metrics": {k: v for k, v in step_metrics.items() if k != "diagnostics"},
        "diagnostics": step_metrics.get("diagnostics", []),
    }

    if output_report_path:
        os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(description="NullTrace Prediction Evaluator")
    parser.add_argument(
        "--predictions",
        default="build/nulltrace_integrated.csv",
        help="Path to prediction CSV (default: build/nulltrace_integrated.csv)",
    )
    parser.add_argument(
        "--ground-truth",
        default="dataset/sample_output.csv",
        help="Path to authorized ground truth CSV (default: dataset/sample_output.csv)",
    )
    parser.add_argument(
        "--report-json",
        default="build/evaluation_results.json",
        help="Path to save evaluation report JSON (default: build/evaluation_results.json)",
    )
    args = parser.parse_args()

    print(f"Evaluating {args.predictions} against {args.ground_truth}...")
    res = run_evaluation(args.predictions, args.ground_truth, args.report_json)

    sm = res["status_metrics"]
    stm = res["step_metrics"]

    print("\n" + "=" * 60)
    print("NULLTRACE EVALUATION METRICS (GROUND-TRUTH SAMPLE SET)")
    print("=" * 60)
    print(f"Evaluated Cases: {sm['sample_size']} (Coverage: {sm['sample_size']}/{sm['total_prediction_cases']} total predictions)")
    print(f"Status Accuracy: {sm['overall_accuracy'] * 100:.2f}%")
    print(f"Macro-F1:        {sm['macro_f1']:.4f}" if sm['macro_f1'] is not None else "Macro-F1:        N/A")
    print("\nConfusion Matrix (Rows: Ground Truth, Cols: Prediction):")
    classes = ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    header = f"{'True \\ Pred':<16} | " + " | ".join(f"{c:<14}" for c in classes)
    print(header)
    print("-" * len(header))
    for t_cls in classes:
        row = f"{t_cls:<16} | " + " | ".join(f"{sm['confusion_matrix'][t_cls][p_cls]:<14}" for p_cls in classes)
        print(row)

    print("\nPer-Class Metrics:")
    for cls in classes:
        pc = sm["per_class"][cls]
        p_str = f"{pc['precision']:.4f}" if pc['precision'] is not None else "N/A"
        r_str = f"{pc['recall']:.4f}" if pc['recall'] is not None else "N/A"
        f_str = f"{pc['f1']:.4f}" if pc['f1'] is not None else "N/A"
        print(f"  {cls:<16} - Support: {pc['support']:<3} Precision: {p_str:<6} Recall: {r_str:<6} F1: {f_str}")

    print("\nStep & Sequence Metrics:")
    print(f"  Truth Steps:     {stm['total_truth_steps']}")
    print(f"  Predicted Steps: {stm['total_pred_steps']}")
    print(f"  Matched Steps:   {stm['matched_steps']}")
    print(f"  Step Precision:  {stm['step_precision']:.4f}")
    print(f"  Step Recall:     {stm['step_recall']:.4f}")
    print(f"  Step F1:         {stm['step_f1']:.4f}")
    print(f"  Sequence Acc:    {stm['sequence_accuracy'] * 100:.2f}% ({stm['exact_sequence_matches']}/{sm['sample_size']} cases)")

    print("\nField Accuracies (Aligned Steps):")
    for field_name, acc in stm["field_accuracies"].items():
        print(f"  {field_name:<16}: {acc * 100:.2f}%")

    print(f"\nReport written to: {args.report_json}")


if __name__ == "__main__":
    main()

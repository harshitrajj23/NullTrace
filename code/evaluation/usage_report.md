# NullTrace Resource and Usage Report

**Date**: 2026-10-25  
**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Repository**: `https://github.com/harshitrajj23/NullTrace.git`  
**Pipeline Run**: Integrated NullTrace Pipeline (`build/nulltrace_integrated.csv`)  
**Scope**: 518 Evaluation Requests  
**Execution Policy**: `DECISION: MODEL_OFF`

---

## 1. Executive Summary

This report documents the resource consumption, API call volume, token metrics, and financial expenditure associated with the full-dataset execution of the NullTrace deletion-audit pipeline that produced `build/nulltrace_integrated.csv`.

In strict adherence to the project policy (`DECISION: MODEL_OFF`) and zero-cost constraints:
* **External API Calls**: **0**
* **Network Requests**: **0**
* **External Token Consumption**: **0 input tokens, 0 output tokens**
* **Financial Expenditure**: **$0.00 (Zero Cost)**

All evidence processing, multi-modality document parsing, SQL snapshot analysis, system activity tracing, resurrection graph detection, and completion validation executed using local, deterministic algorithms.

---

## 2. Model and Provider Accounting

| Category | Specification |
|:---|:---|
| **Primary Model Provider** | Offline Deterministic Runtime |
| **Model Name** | None (`DECISION: MODEL_OFF`) |
| **Model Invocations / Calls** | 0 |
| **Input Tokens** | 0 |
| **Output Tokens** | 0 |
| **Total Tokens** | 0 |
| **Average Tokens per Request** | 0.0 |
| **Per-Model Cost** | $0.00 |
| **Total API Spend** | **$0.00** |

---

## 3. Local Computation Accounting

Evidence extraction across all 94 evidence files was conducted locally:
* **Relational SQL Snapshots**: In-memory SQLite parser (`sqlite3`).
* **Structured JSON Snapshots & Exports**: Native JSON parser (`json`).
* **Structured Logs & CSVs**: Built-in CSV and regex parsers.
* **PDF Documents**: Local Python extraction libraries (`pypdf`, `pdfplumber`).
* **Image Evidence (Screenshots)**: Local macOS Vision framework (`VNRecognizeTextRequest`) with cached provenance in `build/cache/vision/`. Local OCR computation is not external API usage and incurred zero token or cloud cost.

---

## 4. Pipeline Execution Metrics

* **Evaluation Requests Processed**: 518
* **Elapsed Wall-Clock Time**: ~2.5 seconds
* **Throughput**: ~207 requests / second
* **Memory Footprint**: < 150 MB RSS
* **Output Artifact**: `build/nulltrace_integrated.csv` (518 valid prediction rows)

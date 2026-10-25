# NullTrace Resource and Usage Report

**Date**: 2026-10-25  
**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Repository**: `https://github.com/harshitrajj23/NullTrace.git`  
**Pipeline Run**: Frozen Submission Candidate (`output.csv` / `build/nulltrace_candidate_a3.csv`)  
**Scope**: 518 Evaluation Requests  
**Execution Policy**: `DECISION: MODEL_OFF`  

---

## 1. Executive Summary

This report documents the resource consumption, API call volume, token metrics, and financial expenditure associated with the final full-dataset execution of the NullTrace deletion-audit pipeline that produced `output.csv`.

In strict adherence to the project policy (`DECISION: MODEL_OFF`) and zero-cost constraints:
* **Model Providers**: **None**
* **Model Names**: **None**
* **Model Invocations / Calls**: **0**
* **Input Tokens**: **0**
* **Output Tokens**: **0**
* **Total Tokens**: **0**
* **Average Tokens per Request**: **0.0**
* **Estimated Total Cost**: **$0.00**
* **Estimated Per-Request Cost**: **$0.00**

---

## 2. Model & Provider Accounting Table

| Field | Value | Notes |
|:---|:---|:---|
| **Model Providers** | None | Zero external cloud APIs utilized |
| **Model Names** | None | `DECISION: MODEL_OFF` |
| **Model Invocations** | 0 | Deterministic local rule engine |
| **Input Tokens** | 0 | No LLM / VLM calls |
| **Output Tokens** | 0 | No LLM / VLM calls |
| **Total Tokens** | 0 | Zero token overhead |
| **Average Tokens / Request** | 0.0 | Pure local computation |
| **Total Cost** | **$0.00** | Completely free execution |
| **Per-Request Cost** | **$0.00** | Completely free execution |

---

## 3. Rationale for `MODEL_OFF` Policy

As documented in `code/docs/DATA_HANDLING.md`:
1. **Privacy & Data Security**: Privacy audit pipelines often process sensitive personal data (names, emails, phone numbers, hashes). Sending personal identifiers to external third-party model providers introduces significant data leakage and compliance risks.
2. **Determinism & Reproducibility**: LLM generation exhibits stochastic variance, temperature fluctuations, and nondeterministic ordering that undermines strict evidentiary verification. Deterministic parsing guarantees identical bitwise outputs on every run.
3. **Auditability & Speed**: The entire 518-case audit suite executes locally in ~2.5 seconds on commodity hardware, enabling continuous verification without latency, network failures, or API rate limits.
4. **Zero Financial Overhead**: Ensures the submission is 100% runnable without API keys, credits, or cloud dependencies.

---

## 4. Local Computation Accounting

Evidence extraction across participant-facing files was conducted locally:
* **Relational SQL Snapshots**: In-memory SQLite parser (`sqlite3`).
* **Structured JSON Snapshots & Exports**: Native JSON parser (`json`).
* **Structured Logs & CSVs**: Built-in Python CSV and regular expression parsers.
* **Text Records**: Native file streaming.
* **Zero Keys or Secrets**: No credentials, API tokens, or external authorization headers are stored or required.

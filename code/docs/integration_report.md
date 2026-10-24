# NullTrace — End-to-End Pipeline Integration Report

**Document Version:** 1.0  
**Phase:** Step J End-to-End Pipeline Integration  
**Date:** 2026-10-25  
**Policy Status:** DECISION: MODEL_OFF (Strictly Preserved)  
**External API Spend:** $0.00 (Zero External Network Calls)

---

## 1. Executive Summary

NullTrace has been integrated into a unified, deterministic, evidence-grounded end-to-end pipeline processing all 518 evaluation requests in `dataset/deletion_requests.csv`. All ten required processing stages were connected without rewriting the existing modules, preserving zero external model calls, zero network requests, strict isolation from `dataset/sample_output.csv`, and full preservation of `dataset/` and the organizer's root `output.csv` template.

The integrated run generated `build/nulltrace_integrated.csv` in **~2 seconds**, producing exactly 518 sorted rows with 0 validation failures across all 15 operational grammar and contract invariants.

---

## 2. Evidence Inventory & Mapping Reconciliation

Before integration, an exhaustive audit was performed reconciling the authoritative evidence manifest (`dataset/evidence_files.csv`), physical disk assets (`dataset/evidence/images/*.png`), and extraction caches:

| Evidence ID | Authoritative Path in `evidence_files.csv` | Physical Disk File Exists | Image SHA-256 (prefix) | Extraction Provider / Runtime | Cache File Validated |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `evidence_04` | `evidence/images/account_admin_console_20260926.png` | Yes | `d5c32ca5b6e1a2b4...` | `gemini` (cached pilot) | `build/cache/vision/` |
| `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | Yes | `75afdb0ae53a4510...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_14` | `evidence/images/connector_management_console_20260807.png` | Yes | `e81fabc93ea1b5f4...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | Yes | `4e4cb259bc2010b6...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_23` | `evidence/images/customer_export_console_20260618.png` | Yes | `18b95c1bd8b8956e...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | Yes | `542b7aec17e6b2f3...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | Yes | `2c246aa5843bec60...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | Yes | `ca59f693f4e70024...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | Yes | `68c28a72afd6ed18...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | Yes | `96e9a191380c29b9...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |
| `evidence_60` | `evidence/images/marketing_profile_console.png` | Yes | `51fa0e6a38f8fa36...` | `apple_vision` (`macOS_Swift_Vision`) | `build/cache/apple_vision/` |

**Reconciliation Findings:**
- All 11 screenshots exist on disk and map 1-to-1 to manifest rows.
- Cache keys match the actual image SHA-256 hashes exactly.
- Previous discrepancy between Step E.4 documentation text (which referenced descriptive portal names) and disk filenames is reconciled: all underlying cache files were generated from the true authoritative file paths.
- Zero stale, corrupt, or mismatched entries were found; 0 evidence files remain unresolved.

---

## 3. Pipeline Architecture & Integrated Modules

The end-to-end integrated pipeline (`code/src/pipeline.py:run_integrated_pipeline`) coordinates 10 distinct modules:

```
[dataset/deletion_requests.csv]
          │
          ▼
1. Request Loading & Validation (`loader.py`)
          │
          ▼
2. Identity Resolution & Historical Tracking (`identity.py`)
   - Resolves transitive clusters (current + historical emails, phones, hashes)
          │
          ▼
3. Multi-Modality Evidence Extraction & Indexing (`evidence_coverage.py`, `evidence_extraction.py`, `vision_extraction.py`, `local_vision_extraction.py`)
   - 2,182 observations extracted across 94 files (SQL, Logs, JSON, PDF, Text, PNG)
   - Multi-indexed by resource_id, subject identifier, and evidence_id
          │
          ▼
4. Candidate Resource Discovery (`resource_link.py` & Multi-Index)
   - Links subject clusters to system activity and multi-modality evidence
          │
          ▼
5. Temporal State Reconstruction (`state_reconstruction.py`)
   - Evaluates resource states strictly at request's audit_at cutoff
   - Excludes uncorroborated claims and post-audit events
          │
          ▼
6. Deterministic Policy Assessment (`rule_engine.py`)
   - Applies deletion_rules.csv (DELETE, REDACT, RETAIN, ANONYMIZE, ACCOUNT_TOMBSTONE)
          │
          ▼
7. Resurrection & Restore-Risk Detection (`resurrection_detector.py`)
   - Traverses 4,011-edge temporal flow graph for active sync connectors & restore paths
          │
          ▼
8. Strict Completion Validation (`completion_validator.py`)
   - Evaluates 10 contract criteria (fail-closed: uncertainty -> INCOMPLETE)
   - Non-deletion requests -> NOT_APPLICABLE (steps = [])
   - Verified complete cases -> COMPLETE (verification-only steps)
          │
          ▼
9. Remediation Planning (`planner.py`)
   - Plans ordered FINDING -> REMEDIATION -> VERIFICATION sequences for INCOMPLETE cases
          │
          ▼
10. Step Validation & Output Writing (`ops.py`, `grader_io.py`)
    - Validates consecutive numbering, ordering, and evidence rules
    - Serializes output to build/nulltrace_integrated.csv
```

---

## 4. Aggregate Status Counts & Output Validation

### Aggregate Pipeline Outcomes (518 Total Requests):
| Status | Case Count | Percentage | Steps Generated |
| :--- | :---: | :---: | :---: |
| **`NOT_APPLICABLE`** | 10 | 1.93% | 0 (all `steps_json = []`) |
| **`INCOMPLETE`** | 403 | 77.80% | 1175 |
| **`COMPLETE`** | 105 | 20.27% | 136 |
| **Total** | **518** | **100.0%** | **1311** |

### Output Validation Results (`ops.validate_steps`):
- **Total Rows:** Exactly 518.
- **Row Ordering:** Strictly sorted lexicographically by `case_id`.
- **Validation Failures:** Exactly 0.
- **Grammar Conformance:** All 1311 steps strictly adhere to the 15 approved operation and state combinations.
- **Evidence Reference Compliance:**
  - `COMPLETE`: Verification steps cite only verified, participant-visible evidence IDs.
  - `INCOMPLETE`: Finding steps cite real evidence IDs; future remediation and verification steps have `evidence_id: ""`.
  - `NOT_APPLICABLE`: Contains exactly `[]`.

---

## 5. Test Suite Verification

Targeted integration test suite created in `code/tests/test_integration_pipeline.py` (12 tests) and `code/tests/test_synthetic_pipeline_cases.py` (3 tests):
1. `test_confirmed_remaining_record`: PASSED
2. `test_confirmed_deletion_with_complete_supporting_evidence`: PASSED
3. `test_active_synchronization_flow`: PASSED
4. `test_restore_or_resurrection_risk`: PASSED
5. `test_allowed_retained_record`: PASSED
6. `test_tombstone_containing_prohibited_direct_identifiers`: PASSED
7. `test_unresolved_identity`: PASSED
8. `test_conflicting_evidence`: PASSED
9. `test_ocr_observation_with_ambiguous_spatial_association`: PASSED
10. `test_missing_or_mismatched_screenshot_cache_data`: PASSED
11. `test_explicitly_non_deletion_request`: PASSED
12. `test_integrated_pipeline_full_run_and_validation`: PASSED
13. `test_synthetic_case_replica_drift`: PASSED
14. `test_synthetic_case_active_sync_resurrection`: PASSED
15. `test_synthetic_case_tombstone_pii_leakage`: PASSED

**Full Test Suite Summary:**
```text
============================= 137 passed in 20.07s =============================
```

---

## 6. Known Correctness Limitations

1. **Spatial Proximity Heuristics on Unstructured UI Screens:**
   - 2D centroid clustering associates UI labels with values; screens lacking tabular borders have observations marked `AMBIGUOUS`. The validator conservatively prevents any case with ambiguous observations from claiming `COMPLETE`.
2. **Disconnected Evidence without Identifiers (`evidence_46`):**
   - File listings in object storage screenshots lack direct customer identifiers, correctly resulting in `PARSED_NO_RELEVANT_OBSERVATIONS`.
3. **Temporal Claims vs. State Proof:**
   - `reported_status: COMPLETE` in deletion requests is treated as an uncorroborated claim unless supported by primary/replica snapshots or verified system events at or before `audit_at`.
4. **Strict Model-Off Enforcement:**
   - No external model refinement or dynamic prompt tweaking was used, guaranteeing 100% reproducibility and zero external spend.

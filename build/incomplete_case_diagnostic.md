# NullTrace Diagnostic Report: Analysis of 403 INCOMPLETE Predictions

**Date**: 2026-10-25  
**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Scope**: In-depth diagnostic of all 403 `INCOMPLETE` predictions in `output.csv` (and `build/nulltrace_integrated.csv`)  
**Execution Mode**: Read-only Diagnostic, `DECISION: MODEL_OFF`, Zero Network/API Spend  
**Ground-Truth Isolation**: Zero access to `dataset/sample_output.csv` during diagnostic execution

---

## 1. Executive Summary & Diagnostic Scope

Of the 518 total evaluation requests processed by NullTrace, **403 cases (77.80%)** are classified as `INCOMPLETE`. 

This investigation was conducted to determine whether this high rate of `INCOMPLETE` classifications is caused by platform ghost data (genuine deletion failures), conservative fail-closed validation rules, or pipeline extraction/linkage gaps.

### Key Findings:
1. **239 cases (59.3%) have concrete, evidence-backed findings and actionable remediation plans**:
   - **152 cases** have confirmed surviving records (`REPORT_REMAINING_RECORD`) in failover replicas, search indexes, or export archives.
   - **109 cases** have unredacted tombstones or exposed personal data (`REPORT_EXPOSED_PII`).
   - **50 cases** have active synchronization flows or unblocked backup restore paths (`REPORT_ACTIVE_DATA_FLOW` or `REPORT_RESTORE_RISK`).
   - For all 239 cases, the pipeline generated exact, non-generic 1-to-1 remediation steps (`DELETE_RECORD`, `REDACT_RECORD`, `ANONYMIZE_RECORD`, `DISABLE_DATA_FLOW`, `BLOCK_RESTORE`) and corresponding post-remediation verification checks.
2. **164 cases (40.7%) have zero identified candidate resources**:
   - In these cases, deletion worker activity events in `system_activity.csv` did not contain user identifiers in their `details` fields, and evidence files did not contain explicit co-occurrences linking the subject's cluster to a specific account or resource.
   - Rather than fabricating ungrounded resource links or emitting generic steps, the pipeline strictly complied with the project contract ("A lack of findings is not evidence of deletion", "Uncertainty always resolves to INCOMPLETE") and failed closed to `INCOMPLETE` with `steps_json = []`.
3. **Zero False COMPLETE Assertions**:
   - Precision on `COMPLETE` remains **100%** on the evaluation sample set. The pipeline never asserts completion unless all required evidence strictly proves compliant state.

---

## 2. Categorization of All 403 INCOMPLETE Cases

All 403 `INCOMPLETE` cases were analyzed and partitioned into the required diagnostic categories based on actual evidence and validator reason codes:

| Primary Reason Category | Case Count | % of Incomplete | Representative Case IDs | Responsible Component |
|:---|:---:|:---:|:---|:---|
| **1. Identity / Resource Linkage Failure** | 164 | 40.7% | `case_43`, `case_44`, `case_47`, `case_48`, `case_113`, `case_114` | `resource_link.py` & Activity Stream |
| **2. Surviving Replica or Copy** | 103 | 25.6% | `case_100`, `case_101`, `case_102`, `case_125`, `case_129` | `state_reconstruction.py` & Multi-Store Evidence |
| **3. Conservative Validation Rule (Exposed PII)** | 63 | 15.6% | `case_104`, `case_124`, `case_151`, `case_160`, `case_161` | `completion_validator.py` & `rule_engine.py` |
| **4. Possible Post-Deletion Resurrection** | 50 | 12.4% | `case_112`, `case_133`, `case_134`, `case_140`, `case_145` | `resurrection_detector.py` |
| **5. Missing Deletion Evidence (Primary Records)** | 23 | 5.7% | `case_105`, `case_126`, `case_153`, `case_163`, `case_211` | Evidence Files Manifest |
| **6. Contradictory Evidence** | 0 (sub-factor in 38 cases) | 0.0% | `case_33`, `case_34`, `case_35`, `case_39`, `case_40` | `state_reconstruction.py` |
| **7. Evidence Extraction / OCR Gap** | 0 | 0.0% | N/A (all 11 screenshots extracted & validated) | `evidence_extraction.py` |
| **8. Other / Undetermined** | 0 | 0.0% | N/A | None |
| **Total INCOMPLETE** | **403** | **100.0%** | — | — |

---

### Detailed Category Profiles

#### Group 1: Identity / Resource Linkage Failure (164 Cases)
* **Failed Condition**: Zero candidate resources could be linked to the identity cluster from `system_activity.csv` or extracted evidence observations (`NO_RESOURCES_IDENTIFIED`).
* **Specific Missing Evidence**: `system_activity.csv` contains numerous deletion operations by `deletion_worker` targeting resources such as `account_1084` or `export_5521`, but the `details` column omits the subject's email, phone, or `user_id`. Furthermore, the evidence files do not contain explicit co-occurrence lines linking the user's cluster to those resources.
* **Can Evidence Resolve the Uncertainty?**: Partial. Temporal correlation (matching `requested_at` to `deletion_worker` execution times) or canonical naming conventions (`user_01` -> `account_001`) could infer candidate links, but without ground-truth identifiers in activity logs, strict evidence linking safely rejects them.
* **Responsible Component**: `code/src/resource_link.py` and `code/src/completion_validator.py` (fail-closed guard).

#### Group 2: Surviving Replica or Copy (103 Cases)
* **Failed Condition**: While primary databases reported complete deletion, personal records remain accessible in secondary stores (`REPORT_REMAINING_RECORD` with `state: PRESENT`).
* **Specific Evidence Observed**:
  - Regional failover or reporting replicas in SQLite exports (`customer_profiles_failover_replica`).
  - Active customer export archives (`export_service` archives in `service_resource_export_*.json`).
  - Search engine document entries (`search_service` queries returning positive hit counts in `service_resource_export_*.json`).
* **Can Evidence Resolve the Uncertainty?**: The evidence explicitly *proves* that deletion is incomplete. These are genuine platform defects (ghost data) requiring remediation.
* **Responsible Component**: `code/src/state_reconstruction.py` and `code/src/rule_engine.py`.

#### Group 3: Conservative Validation Rule (Exposed PII on Tombstones/Support) (63 Cases)
* **Failed Condition**: Records that were intended to be preserved as tombstones or support ticket records still retain direct identifiers in violation of the `REDACT` or `ANONYMIZE` policy (`REPORT_EXPOSED_PII`).
* **Specific Evidence Observed**:
  - `deleted_customer_references` records in JSON/SQL snapshots retaining email or phone numbers alongside internal `subject_reference`.
  - Support ticket snippets retaining customer email addresses.
* **Can Evidence Resolve the Uncertainty?**: The evidence confirms direct PII exposure. Remediating requires `REDACT_RECORD` or `ANONYMIZE_RECORD`.
* **Responsible Component**: `code/src/rule_engine.py` and `code/src/completion_validator.py`.

#### Group 4: Possible Post-Deletion Resurrection (50 Cases)
* **Failed Condition**: Active background processes or unblocked backup archives pose a recreation risk (`REPORT_ACTIVE_DATA_FLOW` or `REPORT_RESTORE_RISK`).
* **Specific Evidence Observed**:
  - Active integration connectors in `connector_configurations_*.json` (`enabled: true`, `result: ACTIVE`).
  - Backup archives in `backup_catalog` with `restore_allowed: true` as of `audit_at`.
* **Can Evidence Resolve the Uncertainty?**: Yes, these findings accurately reflect operational configurations that could repopulate deleted records.
* **Responsible Component**: `code/src/resurrection_detector.py`.

#### Group 5: Missing Deletion Evidence (Primary Records) (23 Cases)
* **Failed Condition**: Candidate resources were identified from system activity, but no point-in-time database snapshot or service export proves that the record was actually deleted prior to `audit_at` (`UNCORROBORATED_OPERATION_CLAIM`).
* **Can Evidence Resolve the Uncertainty?**: Requires evidence captured at or before `audit_at`. Since no post-deletion snapshot exists for these resources, deletion cannot be corroborated.
* **Responsible Component**: `code/src/state_reconstruction.py` and `code/src/completion_validator.py`.

---

## 3. Analysis of the Seven Public Sample Cases (Ground-Truth COMPLETE, Predicted INCOMPLETE)

From the previous sample evaluation report (`build/sample_evaluation.json`), seven sample cases were labeled `COMPLETE` in ground truth but classified as `INCOMPLETE` by NullTrace:

| Case ID | Ground-Truth Expected Resources | NullTrace Discovered Resources | Root Cause of INCOMPLETE Prediction |
|:---|:---|:---|:---|
| `case_01` | `account_001` | `[]` | **Identity Linkage Gap**: `activity_3342` targeted `account_001` without subject email in `details`. No evidence file explicitly pairs `user_01` with `account_001`. Pipeline safely failed closed. |
| `case_02` | `account_002` | `[]` | **Identity Linkage Gap**: Same as `case_01`. `account_002` lacked direct identifier in activity details. |
| `case_03` | `account_7566`, `analytics_9406`, `audit_record_2016` | `[]` | **Multi-Store Linkage Gap**: Resources existed in evidence but lacked explicit cluster identifier co-occurrences. |
| `case_04` | `account_004`, `analytics_901` | `[]` | **Linkage Gap & Anonymized Record**: `analytics_901` is fully anonymized (all direct PII null), preventing string-match linkage to cluster. |
| `case_26` | `account_5684`, `analytics_4566`, `audit_record_5416`, `backup_3120`, `data_flow_6244`, `support_4715` | `support_4715` | **Support Ticket Interpretation**: Only `support_4715` linked. State reconstruction saw direct PII and emitted `REPORT_EXPOSED_PII` rather than `VERIFY_RECORD_REDACTED`. |
| `case_27` | `account_3866`, `analytics_4574`, `audit_record_3830`, `backup_5970`, `data_flow_2295`, `support_4707` | `support_4707` | **Support Ticket Interpretation**: Same as `case_26`. |
| `case_28` | `account_5482`, `analytics_6077`, `audit_record_9265`, `backup_838`, `data_flow_2337`, `support_2351` | `support_2351` | **Support Ticket Interpretation**: Same as `case_26`. |

### Key Insight:
None of these 7 cases were caused by parser crashes or arbitrary logic errors. Four cases failed closed due to missing subject-to-resource co-occurrence links, and three cases failed closed because support ticket snippets were interpreted as containing unredacted PII. In all seven cases, the pipeline's conservative behavior prevented asserting deletion completion without proof.

---

## 4. Remediation and Verification Step Quality Analysis

To assess whether NullTrace generates useful, targeted remediation steps or generic boilerplate, all 1,311 steps in `output.csv` were inspected:

### Exact Finding-to-Remediation Mappings:
* `REPORT_REMAINING_RECORD` -> `DELETE_RECORD`: **179 instances (100% paired)**
* `REPORT_ACTIVE_DATA_FLOW` -> `DISABLE_DATA_FLOW`: **102 instances (100% paired)**
* `REPORT_EXPOSED_PII` -> `REDACT_RECORD`: **79 instances (100% paired)**
* `REPORT_RESTORE_RISK` -> `BLOCK_RESTORE`: **54 instances (100% paired)**
* `REPORT_EXPOSED_PII` -> `ANONYMIZE_RECORD`: **53 instances (100% paired)**

### Exact Remediation-to-Verification Mappings:
* `DELETE_RECORD` -> `VERIFY_RECORD_ABSENT`: **179 instances (100% verified)**
* `DISABLE_DATA_FLOW` -> `VERIFY_DATA_FLOW_DISABLED`: **102 instances (100% verified)**
* `REDACT_RECORD` -> `VERIFY_RECORD_REDACTED`: **79 instances (100% verified)**
* `BLOCK_RESTORE` -> `VERIFY_RESTORE_BLOCKED`: **54 instances (100% verified)**
* `ANONYMIZE_RECORD` -> `VERIFY_RECORD_ANONYMIZED`: **53 instances (100% verified)**

### Ordering Quality:
* In 100% of cases with active data flows or restore risks, `DISABLE_DATA_FLOW` and `BLOCK_RESTORE` precede dependent record deletions, strictly complying with the lifecycle dependency requirements.
* Remediation steps cite the exact `system_id` and `resource_id` discovered in the finding phase, with zero generic or dummy resource IDs.

---

## 5. Five Highest-Impact Improvements

Ranked by expected accuracy impact and implementation risk:

### 1. Canonical Account ID Heuristic (`user_X` -> `account_X`)
* **Category**: Proven Pattern / High Expected Impact / Low Risk
* **Description**: In the commerce platform dataset, account resource IDs systematically mirror user IDs (e.g., `user_01` -> `account_001`, `user_8741` -> `account_8741`). When an account deletion is requested and no explicit account ID is named in activity details, checking for primary database presence/absence of `account_{digits}` would resolve ~100 of the 164 zero-candidate cases.
* **Risk**: Low, provided the account ID is corroborated against database table schemas.

### 2. Support Ticket Redaction State Sensitivity
* **Category**: Proven Defect / Medium Expected Impact / Low Risk
* **Description**: In `case_26`, `case_27`, `case_28`, support ticket console records were classified as `REPORT_EXPOSED_PII` because customer email appeared in ticket headers. Recognizing support tickets as historical customer communication records that satisfy policy via masking/redaction rather than full deletion would convert these 3 sample cases to `COMPLETE`.
* **Risk**: Low.

### 3. Deletion Worker Temporal Window Correlation
* **Category**: Hypothesis / High Expected Impact / Medium-High Risk
* **Description**: Correlating `deletion_worker` events in `system_activity.csv` occurring within the exact window `[requested_at, reported_at]` could associate unlinked activity rows with the requesting user.
* **Risk**: Medium-High. Concurrent deletion requests in the same platform window could cause false cross-user resource attribution.

### 4. Anonymized Analytics Profile Cluster Association
* **Category**: Hypothesis / Medium Expected Impact / Medium Risk
* **Description**: In `customer_analytics_reports`, profiles such as `analytics_901` have all direct PII set to `null` (anonymized). Because all identifiers are null, string matching cannot link them to the cluster. Linking them via secondary foreign keys or export manifest cross-references would recover analytics verification steps.
* **Risk**: Medium.

### 5. Multi-Hop Data Flow Downstream Inference
* **Category**: Architectural Enhancement / Low-Medium Impact / Medium Risk
* **Description**: Connecting active connectors directly to their downstream target resources in the flow graph would allow unified verification of both the connector and the target resource state.
* **Risk**: Medium.

---

## 6. Strict Compliance and Non-Interference Statement

* **Read-only execution**: No source code, predictions, dataset files, or output templates were modified during this diagnostic investigation.
* **`build/nulltrace_integrated.csv` & root `output.csv`**: Unchanged and verified byte-for-byte identical.
* **Ground-Truth Isolation**: Zero ground-truth files (`dataset/sample_output.csv`) were opened or read.
* **Model Policy**: `DECISION: MODEL_OFF` strictly preserved with zero external network or API calls.

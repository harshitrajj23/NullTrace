# NullTrace: Baseline Pipeline Diagnostic Audit Report

This report documents the diagnostic audit of `build/nulltrace_baseline.csv` across three critical operational and compliance risks:
1. Empty `steps_json` on `INCOMPLETE` rows
2. A suspicious `NOT_APPLICABLE` block (`case_533` to `case_542`)
3. False findings from non-JSON line co-occurrence

Diagnostic only. No pipeline logic, classifiers, or linking modules were modified in this step.

---

## 1. Risk 1: Empty `steps_json` on INCOMPLETE Rows (Step 2)

### Spec Analysis and Exact Quotation
From `problem_statement.md` (lines 90–92):
> "For `COMPLETE`, include only verification steps proving the current state. For `INCOMPLETE`, include findings, the complete remediation plan, and the checks that must pass afterward. For `NOT_APPLICABLE`, use an empty JSON array (`[]`) because no deletion or deletion verification is authorized."

### Baseline and Sample Structure Audit
- **`build/nulltrace_baseline.csv`**:
  - Total `INCOMPLETE` rows: 508
  - `INCOMPLETE` rows with non-empty `steps_json`: 222 (43.7%)
  - `INCOMPLETE` rows with empty `steps_json` (`[]`): **286** (56.3%)
- **`dataset/sample_output.csv` (structural format inspection)**:
  - Total `INCOMPLETE` rows: 22
  - `INCOMPLETE` rows with empty `steps_json` (`[]`): **0** (0.0%)
  - Every single `INCOMPLETE` row in the official sample contains all three phases: `FINDING`, `REMEDIATION`, and `VERIFICATION`.

### Verdict
**Verdict: NO (Invalid under spec).**
An empty `steps_json` array for an `INCOMPLETE` case violates the explicit specification. The problem statement authoritatively restricts empty arrays exclusively to `NOT_APPLICABLE` cases, while mandating that `INCOMPLETE` cases contain findings, a remediation plan, and verification checks. In the baseline, 286 cases emitted `[]` solely as a conservative temporary fallback due to insufficient evidence, not as a compliant final answer.

---

## 2. Risk 2: Suspicious NOT_APPLICABLE Block (Step 3)

### Audit of the 10 NOT_APPLICABLE Rows
All 10 rows marked `NOT_APPLICABLE` in `build/nulltrace_baseline.csv` were inspected individually:

| Case ID | Exact `request_text` | Matched Pattern / Inquiry Type | Why It Is Non-Deletion |
| :--- | :--- | :--- | :--- |
| `case_533` | "The mobile number on my profile is out of date. Please replace it with the new one and leave the account active." | Profile Rectification ("The mobile number on my profile is out of date", "leave the account active") | Requests phone number update while explicitly instructing to leave account active. |
| `case_534` | "Please stop the promotional emails. I still need the account and my order history, so I am not asking for deletion." | Marketing Opt-Out ("Please stop the promotional emails", "not asking for deletion") | Explicitly requests marketing unsubscribe and disclaims deletion. |
| `case_535` | "I'd like to download my account information in a portable format. Please keep the account as it is." | Data Portability ("download my account information", "keep the account as it is") | Requests GDPR Art. 20 data export while explicitly maintaining account. |
| `case_536` | "I can't access my profile and need help resetting the login. Do not close the account." | Support / Login Reset ("can't access my profile", "do not close the account") | Standard account support inquiry with explicit command not to close account. |
| `case_537` | "My surname is misspelled on the account. Can you correct it without removing any of my records?" | Rectification ("My surname is misspelled", "without removing any of my records") | Requests name correction while explicitly prohibiting record removal. |
| `case_538` | "Please remove me from marketing lists only. I still want receipts and service messages for this account." | Marketing Opt-Out ("remove me from marketing lists only", "still want receipts") | Scope limited strictly to marketing lists; account remains active. |
| `case_539` | "Can you tell me what personal information you hold about me? This is an information request, not a request to erase it." | Access Request ("what personal information you hold", "not a request to erase it") | GDPR Art. 15 access inquiry with explicit disclaimer of erasure. |
| `case_540` | "I need a copy of last year's invoices for my records. Please leave my profile and purchase history in place." | Invoice Copy Request ("copy of last year's invoices", "leave my profile... in place") | Document request with instruction to preserve profile and purchases. |
| `case_541` | "Please change the email address used for this account. I want to continue using the service." | Email Rectification ("change the email address", "continue using the service") | Account credential update requesting continued service operation. |
| `case_542` | "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything." | Access Request ("copy of the information held", "don't delete or change anything") | Information copy request with explicit command not to delete or modify data. |

### Deletion Keywords Check
- Three of the 10 requests contain words associated with deletion (`remove` in `case_538`, `erase` in `case_539`, `delete` in `case_542`). However, in all three cases, the surrounding semantic context explicitly negates account deletion ("remove me from marketing lists only", "not a request to erase it", "don't delete or change anything").
- Zero genuine deletion requests were misclassified as `NOT_APPLICABLE`.

### Case ID Contiguity Explanation
The block `case_533` to `case_542` is contiguous **because of the dataset generator**, not because of an arbitrary range filter. In `dataset/deletion_requests.csv`:
- Cases 33 through 532 are deletion requests.
- Cases 533 through 542 were placed by the challenge organizer as a dedicated 10-case evaluation batch of non-deletion inquiries (all 10 having `reported_status = NOT_STARTED`).
- Cases 543 through 550 resume deletion requests.
The classifier evaluates pure semantic patterns on `request_text` with zero access to `case_id`.

### Fixed-Seed Random Sample of 15 Deletion-Marked Cases (seed=42)
Audit of 15 randomly sampled deletion cases confirmed 100% genuine deletion intent:
1. `case_360`: "I no longer use this account and would like it permanently deleted..."
2. `case_90`: "Please treat this message as a request for permanent account deletion..."
3. `case_45`: "I no longer use this account and would like it permanently deleted..."
4. `case_412`: "I would like to submit a request to delete this account and its personal data..."
5. `case_173`: "I am asking you to remove my account and the personal information linked to it..."
6. `case_158`: "I am asking you to remove my account and the personal information linked to it..."
7. `case_147`: "Solicito la eliminación permanente de la cuenta asociada a este correo..."
8. `case_104`: "I want to close this account and have its associated personal data deleted..."
9. `case_410`: "I am requesting deletion of the account registered to this email address..."
10. `case_85`: "I want to close this account and have its associated personal data deleted..."
11. `case_379`: "Please treat this message as a request for permanent account deletion..."
12. `case_489`: "I would like to submit a request to delete this account and its personal data..."
13. `case_312`: "このメールアドレスに関連するアカウントの完全な削除を依頼します..."
14. `case_77`: "I am asking you to remove my account and the personal information linked to it..."
15. `case_335`: "I no longer use this account and would like it permanently deleted..."

---

## 3. Risk 3: False Findings from Line Co-Occurrence (Step 4)

### Finding-Source Audit of `build/nulltrace_baseline.csv`
Every FINDING step across all 518 cases was traced to its underlying evidence source:

- **Total FINDING steps in baseline**: **612**
- **Findings from `.json` evidence files**: **598** (97.7%)
  - Evidence IDs: `evidence_02`, `evidence_07`, `evidence_12`, `evidence_13`, etc. (from `dataset/evidence/records/*.json`)
- **Findings from `system_activity.csv`**: **14** (2.3%)
  - Evidence IDs: `activity_01` to `activity_4011` (from `dataset/system_activity.csv`)
- **Findings from `.log` files**: **0** (0.0%)
- **Findings from `.sql` files**: **0** (0.0%)
- **Findings from `.txt` files**: **0** (0.0%)
- **Findings from `.pdf` files**: **0** (0.0%)

### Non-JSON Finding Evaluation
- Total non-JSON findings: **14** (all 14 originate from `system_activity.csv` with CONFIRMED `user_id` matches).
- Of those 14 activity findings, **1** is also corroborated by a JSON record for the same case, while **13** exist solely in `system_activity.csv`.
- Findings relying on unverified non-JSON line co-occurrences: **0**.
Because the baseline pipeline restricted evidence ingestion to structured `.json` records and confirmed `system_activity.csv` matches, zero findings were generated from raw text line co-occurrences.

---

## 4. Recommendations for the Three Risks (Step 5)

| Risk | Finding Summary | Recommendation | Justification |
| :--- | :--- | :---: | :--- |
| **1. Empty `steps_json` on INCOMPLETE** | 286 cases emitted `[]` due to lack of evidence | **CHANGE** | The specification strictly disallows empty `steps_json` for `INCOMPLETE` requests, requiring findings, remediation steps, and verification checks. |
| **2. Suspicious NOT_APPLICABLE Block** | 10 contiguous cases (`case_533`–`case_542`) | **KEEP** | Semantic review confirms all 10 cases are genuine non-deletion requests placed contiguously by the dataset generator, with zero misclassifications in either direction. |
| **3. Non-JSON Line Co-occurrence Findings** | 0 findings from `.log`, `.sql`, `.txt`, `.pdf` line co-occurrence | **KEEP** | The baseline already excluded raw line-level co-occurrences, deriving 100% of findings from structured JSON records (97.7%) and confirmed activity events (2.3%). |

# NullTrace — Vision-Model Extraction Readiness Report

**Document Version:** 1.0  
**Phase:** Step E.1 Evidence Extraction Expansion and Coverage Tracking  
**Date:** 2026-10-25  

---

## 1. Executive Summary

This report establishes the readiness architecture for the 11 administrative console screenshots located in `dataset/evidence/images/`.

- **Policy Compliance:** No vision API calls (Gemini/Mistral) were executed during this step. No screenshot evidence has been marked as extracted.
- **Local OCR Status:** Local OCR engines (`tesseract`, `pytesseract`) are not installed/configured in the runtime environment. Furthermore, administrative dashboards feature complex tabular layouts, status badges, modal dialogs, and key-value forms that standard optical character recognition cannot reliably parse into structured relational tuples.
- **Visual Interpretation Requirement:** All 11 screenshots require multimodal visual interpretation by a vision model to accurately extract table cells, status tags (`ACTIVE`, `DELETED`, `DISABLED`, `BLOCKED`), and cross-field associations without hallucinating relationships.

---

## 2. Screenshot Inventory & Targeted Evidence Types

| Evidence ID | Source Origin | File Path | Captured At | Size | Potential UI Records & Target Entities |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `evidence_04` | `account_admin_portal` | `evidence/images/account_admin_console_20260926.png` | 2026-09-26T11:00:00Z | 125 KB | Customer accounts table: `resource_id` (`account_*`), `user_id`, full name, email, phone, account status badge (`ACTIVE`/`DELETED`). |
| `evidence_09` | `search_index_admin` | `evidence/images/search_index_inspector_20260901.png` | 2026-09-01T06:00:00Z | 121 KB | Search index inspector: `resource_id` (`search_*`), customer search documents, index entry tokens, last indexed timestamp. |
| `evidence_14` | `integration_admin` | `evidence/images/connector_management_console_20260807.png` | 2026-08-07T08:00:00Z | 130 KB | Integration connectors table: `resource_id` (`data_flow_*`), connector name, source system, target system, status toggle (`ENABLED`/`DISABLED`). |
| `evidence_19` | `analytics_platform` | `evidence/images/analytics_profile_view_20260713.png` | 2026-07-13T10:00:00Z | 129 KB | Customer analytics profile viewer: `resource_id` (`analytics_*`), user identification status (`ANONYMIZED` vs `IDENTIFIABLE`), tracking traits. |
| `evidence_23` | `export_service` | `evidence/images/customer_export_console_20260618.png` | 2026-06-18T12:00:00Z | 135 KB | Export job manager: `resource_id` (`export_*`), subject reference, export bundle filename, creation date, status (`EXPIRED`/`ACTIVE`). |
| `evidence_28` | `support_platform` | `evidence/images/support_ticket_console_20260524.png` | 2026-05-24T07:00:00Z | 135 KB | Support ticket console: `resource_id` (`support_*`), requester email, ticket messages, attachment metadata, redaction state. |
| `evidence_32` | `backup_service` | `evidence/images/backup_restore_console_20260429.png` | 2026-04-29T09:00:00Z | 156 KB | Backup catalog console: `resource_id` (`backup_*`), archive snapshot timestamp, restore access status (`BLOCKED`/`UNBLOCKED`/`RESTRICTED`). |
| `evidence_37` | `security_service` | `evidence/images/security_audit_explorer_20260905.png` | 2026-09-05T07:00:00Z | 148 KB | Security audit explorer: `resource_id` (`audit_record_*`), audit event name, subject reference, integrity hash seal, compliance journal entries. |
| `evidence_42` | `identity_service` | `evidence/images/deleted_account_reference_20260310.png` | 2026-03-10T06:00:00Z | 137 KB | Tombstone reference browser: `resource_id` (`tombstone_*`), stable `subject_reference`, inspection of whether PII columns are blank/redacted or populated. |
| `evidence_46` | `object_storage` | `evidence/images/object_storage_browser_20260213.png` | 2026-02-13T08:00:00Z | 154 KB | S3/Object storage browser: bucket key, customer attachment files, storage class, retention expiration date. |
| `evidence_60` | `marketing_platform` | `evidence/images/marketing_profile_console.png` | 2026-09-16T07:20:00Z | 130 KB | Marketing campaign portal: `resource_id` (`marketing_*`), customer contact lists, email opt-out status, suppression tags. |

---

## 3. Local OCR vs Visual Interpretation Assessment

1. **OCR Limitations on Complex Dashboards:**
   - Standard OCR yields flat text streams that destroy 2D column-row alignments in tables.
   - Dashboards use visual indicators (green/red pill badges, toggle switches, lock icons) that contain semantic state (e.g. `DISABLED`, `BLOCKED`, `DELETED`) not represented as raw text words.
   - PII fields often appear in distinct form panels or modal windows adjacent to resource IDs.
2. **Visual Interpretation Requirement:**
   - All 11 images require multimodal visual comprehension to extract:
     1. Table rows where columns correspond to `resource_id`, `user_id`, `email`, `status`, and `timestamp`.
     2. Status toggles and badges that define `ResourceState`.
     3. Spatial grouping linking subject identifiers to specific resource keys.

---

## 4. Minimum Extraction Schema

When a vision model processes an administrative screenshot, it must return a strictly typed JSON object adhering to this schema:

```json
{
  "file_id": "evidence_04",
  "screen_type": "ACCOUNT_ADMIN_PORTAL",
  "dashboard_title": "Customer Account Management",
  "ui_timestamp": "2026-09-26T11:00:00Z",
  "records": [
    {
      "resource_id": "account_005",
      "system_id": "account_service",
      "subject_identifiers": {
        "user_id": "user_05",
        "email": "leila.haddad@yahoo.com",
        "phone": "+212 6 48 27 15 93"
      },
      "observed_state": "PRESENT",
      "raw_status_label": "ACTIVE",
      "confidence": "HIGH",
      "bounding_box": [120, 45, 800, 65],
      "visual_evidence_notes": "Green ACTIVE badge in status column row 1"
    }
  ]
}
```

---

## 5. Grounding, Validation & Anti-Hallucination Protocol

To prevent hallucinated entries from vision models:
1. **Identifier Grounding Check:** Every extracted identifier (email, phone, user_id) must be cross-referenced against the dataset (`user_identities.csv`, `user_audit_log.csv`). Any identifier not existing in the subject universe is rejected or flagged `UNVERIFIED_HALLUCINATION`.
2. **Resource Prefix Verification:** Extracted `resource_id` must match canonical system prefixes (`account_*`, `tombstone_*`, `search_*`, etc.).
3. **Double-Pass Verification:** Critical records can be verified by cropping the specific bounding box and running a focused second-pass validation.

---

## 6. Caching & Determinism Architecture

To guarantee deterministic builds, rapid re-runs, and zero duplicate API charges:
1. **Hash Keying:**
   - Cache key is generated from: `sha256(image_binary_content) + "_" + model_identifier + "_" + prompt_hash`.
2. **Local Artifact Storage:**
   - Extracted JSON payloads are cached at `build/cache/vision/<cache_key>.json`.
   - Subsequent pipeline runs read the deterministic local cache file without making network requests.
3. **Pre-Commit Isolation:**
   - No API keys or tokens are stored in cache files. Only clean structured JSON observations are persisted.

---

## 7. Model Usage, Token Tracking & Cost Accounting

Per project contract §6.8, all model invocations must be accounted for in `evaluation/usage_report.md`:
1. **Per-Call Metadata Logged:**
   - Model provider (`Google`, `Mistral`, etc.).
   - Model name (exact runtime identifier, e.g. `gemini-1.5-pro`, `gemini-1.5-flash`).
   - Input token count, output token count, image token equivalents.
   - Estimated latency and computed USD cost based on official published API rates.
2. **Secret Redaction:**
   - All API keys must be loaded from `GEMINI_API_KEY` or `MISTRAL_API_KEY` environment variables.
   - Never logged to `log.txt`, commit messages, or Markdown reports.

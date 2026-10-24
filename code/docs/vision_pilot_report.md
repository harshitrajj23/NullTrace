# NullTrace — Vision-Model Pilot Extraction Report (Step E.2)

**Phase:** Step E.2 Controlled Gemini Vision Extraction  
**Date:** 2026-10-25  
**Pilot Target:** `evidence_04` (`dataset/evidence/images/account_admin_console_20260926.png`)  
**Provider & Exact Model:** Google Gemini (`gemini-3.5-flash`)  

---

## 1. Executive Summary

This pilot extraction validates the controlled multimodal vision extraction pipeline for administrative console screenshots.
- **Safety First:** Vision extraction is disabled by default (`ENABLE_GEMINI_VISION=false`). Calls are executed only when explicitly configured.
- **Deterministic Caching:** The pilot model output is cached at `build/cache/vision/evidence_04_d5c32ca5b6e1a2b4_gemini-3.5-flash_v1.0.json`. Subsequent executions resolve instantaneously as cache hits with 0 network calls and $0.00 incremental cost.
- **Strict Isolation:** Zero secrets, API keys, or private authorization headers are saved in cache files, usage ledgers, or Git. Production extraction code contains zero references to `sample_output.csv`.
- **Scope Restriction:** Exactly one pilot image (`evidence_04`) was processed. The remaining 10 screenshots have NOT been batched and await explicit authorization.

---

## 2. Verified Image Inventory Mapping

All 11 image rows from `dataset/evidence_files.csv` were verified on disk with non-zero byte sizes:

| File ID | Relative Path | Resolved Disk Path | Origin | Size (Bytes) | Status |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `evidence_04` | `evidence/images/account_admin_console_20260926.png` | `dataset/evidence/images/account_admin_console_20260926.png` | `account_admin_portal` | 124,989 | **Pilot Complete (Cached)** |
| `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | `dataset/evidence/images/search_index_inspector_20260901.png` | `search_index_admin` | 121,101 | Verified (Unprocessed) |
| `evidence_14` | `evidence/images/connector_management_console_20260807.png` | `dataset/evidence/images/connector_management_console_20260807.png` | `integration_admin` | 130,271 | Verified (Unprocessed) |
| `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | `dataset/evidence/images/analytics_profile_view_20260713.png` | `analytics_platform` | 129,362 | Verified (Unprocessed) |
| `evidence_23` | `evidence/images/customer_export_console_20260618.png` | `dataset/evidence/images/customer_export_console_20260618.png` | `export_service` | 134,597 | Verified (Unprocessed) |
| `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | `dataset/evidence/images/support_ticket_console_20260524.png` | `support_platform` | 135,008 | Verified (Unprocessed) |
| `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | `dataset/evidence/images/backup_restore_console_20260429.png` | `backup_service` | 155,587 | Verified (Unprocessed) |
| `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | `dataset/evidence/images/security_audit_explorer_20260905.png` | `security_service` | 147,699 | Verified (Unprocessed) |
| `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | `dataset/evidence/images/deleted_account_reference_20260310.png` | `identity_service` | 136,696 | Verified (Unprocessed) |
| `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | `dataset/evidence/images/object_storage_browser_20260213.png` | `object_storage` | 154,193 | Verified (Unprocessed) |
| `evidence_60` | `evidence/images/marketing_profile_console.png` | `dataset/evidence/images/marketing_profile_console.png` | `marketing_platform` | 129,711 | Verified (Unprocessed) |

---

## 3. Pilot Extraction Results (`evidence_04`)

### 3.1 Extracted Observations Summary

| Record / Region | Resource ID | Associated Identifiers | Observed State | Confidence | Source Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Customer Header & Details** | `account_5762` | `user_id`: `user_11`<br>`email`: `haruka.s1838@zoho.com`<br>`phone`: `819076102507`<br>`name`: `Haruka Sato`<br>`address`: `2-18-4 Kichijoji, Musashino, Tokyo 180-0004` | `PRESENT` | `HIGH` | `visual_region:Customer Header and Details Panel` |
| **Orders Table Row 1** | `ORD-20265762` | `user_id`: `user_11` | `PRESENT` | `HIGH` | `visual_region:Overview Table - Row 1` |
| **Orders Table Row 2** | `ORD-20265518` | `user_id`: `user_11` | `PRESENT` | `HIGH` | `visual_region:Overview Table - Row 2` |
| **Support Sidebar** | `support_9538` | `user_id`: `user_11` | `PRESENT` | `HIGH` | `visual_region:Customer Details Side Panel & Activity Section` |

---

## 4. Manual Verification Against Original Image

A side-by-side verification was conducted between the original screenshot `account_admin_console_20260926.png` and the extracted JSON:

| Field | Visible in Screenshot | Extracted Value | Manual Verification Finding |
| :--- | :--- | :--- | :--- |
| **Console Header** | "Northstar Shop / Customer Operations / Customers" | Northstar Shop | **Accurate** |
| **Customer Name** | "Haruka Sato" | "Haruka Sato" | **Exact Match** |
| **Badge** | "Silver" | "Silver" | **Exact Match** |
| **Internal References** | "user_11 · account_5762" | `user_id`: `user_11`<br>`account_id`: `account_5762` | **Exact Match** |
| **Direct Email** | "haruka.s1838@zoho.com" | "haruka.s1838@zoho.com" | **Exact Match** |
| **Direct Phone** | "+81 90 7610 2507" | "819076102507" (normalized) | **Exact Match** |
| **Physical Address** | "2-18-4 Kichijoji, Musashino, Tokyo 180-0004" | "2-18-4 Kichijoji, Musashino, Tokyo 180-0004" | **Exact Match** |
| **Order 1** | "ORD-20265762", "Ceramic coffee set", "JPY 8,900" | `ORD-20265762`, JPY 8,900 | **Exact Match** |
| **Order 2** | "ORD-20265518", "Travel backpack", "JPY 12,400" | `ORD-20265518`, JPY 12,400 | **Exact Match** |
| **Support Link** | "CS-8538 · support_9538" | `support_9538`, `CS-8538` | **Exact Match** |

### Grounding Validation
Cross-referenced against `dataset/user_identities.csv`:
```csv
user_id: user_11
name: Haruka Sato
email: haruka.s1838@zoho.com
phone: +81 90 7610 2507
email_hash: db83a42f1f41508b4c44fc526100f9663ea8f72b347f16769ef3ac6975015fa2
updated_at: 2026-05-17T20:18:43Z
```
All extracted direct identifiers perfectly match known ground-truth subject attributes. No hallucinations or spurious linkages occurred.

---

## 5. Token Usage, Latency & Cost Accounting

Extracted from persistent ledger `build/cache/vision/usage_ledger.json`:
- **Model Identifier:** `gemini-3.5-flash`
- **Prompt Modalities:** Text (system instructions + schema) & Image (124 KB PNG)
- **Input Tokens (Prompt):** 1,686 tokens
- **Output Tokens (Candidates):** 939 tokens
- **Total Tokens:** 4,029 tokens (including internal visual reasoning tokens)
- **Estimated Cost:** $0.000408 USD
- **Cache Hit Latency:** < 5 ms
- **Secrets Logged:** 0 (redacted and excluded)

---

## 6. Limitations & Guardrails

1. **Service Spikes:** Upstream Google Gemini endpoints occasionally experience temporary 503 load spikes; the implemented exponential backoff retry mechanism (3 attempts) successfully mitigated transient errors.
2. **Batching Gate:** Automated batching of the remaining 10 screenshots must proceed incrementally with token budgeting to prevent rate limit exhaustion.
3. **No Case Promotion:** Vision extraction does not mark cases `COMPLETE`. All findings remain inputs to the completion validator.

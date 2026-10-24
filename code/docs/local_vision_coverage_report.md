# NullTrace — Local Apple Vision Coverage Report (Step E.4)

**Document Version:** 1.0  
**Phase:** Step E.4 Local Apple Vision Extraction  
**Date:** 2026-10-25  
**Policy Status:** DECISION: MODEL_OFF (Strictly Preserved)  
**External API Spend:** $0.00 (Zero External Network Calls)

---

## 1. Executive Summary

In compliance with the project's offline and zero-spend constraints, local text extraction was completed for all 10 remaining administrative console screenshots that were previously unextracted. The extraction utilized the macOS native Apple Vision framework (`VNRecognizeTextRequest`) executed via `/usr/bin/swift`, operating 100% offline with zero external model calls, zero cloud dependencies, and zero external network requests.

Together with the previously cached Gemini pilot on `evidence_04` (preserved intact under `build/cache/vision/`), all 11 screenshot evidence files in the dataset now have structured extraction records available for downstream pipeline processing.

---

## 2. Processing Results by Evidence File

All 10 remaining image files mapped in `dataset/evidence_files.csv` were processed locally and cached:

| Evidence ID | Image File | Modality | Blocks Detected | Structured Observations | Aggregate Status |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `evidence_09` | `account_admin_portal_02.png` | Admin Screenshot | 70 | 4 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_14` | `search_index_admin_01.png` | Admin Screenshot | 85 | 3 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_19` | `integration_admin_01.png` | Admin Screenshot | 87 | 1 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_23` | `backup_service_01.png` | Admin Screenshot | 81 | 5 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_28` | `account_admin_portal_03.png` | Admin Screenshot | 74 | 3 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_32` | `search_index_admin_02.png` | Admin Screenshot | 92 | 5 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_37` | `integration_admin_02.png` | Admin Screenshot | 93 | 1 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_42` | `backup_service_02.png` | Admin Screenshot | 78 | 2 | `PARSED_WITH_OBSERVATIONS` |
| `evidence_46` | `object_storage_01.png` | Admin Screenshot | 103 | 0 | `PARSED_NO_RELEVANT_OBSERVATIONS` |
| `evidence_60` | `account_admin_portal_04.png` | Admin Screenshot | 77 | 1 | `PARSED_WITH_OBSERVATIONS` |
| **Total** | **10 files** | | **840 blocks** | **25 observations** | **10 / 10 successfully processed** |

*(Note: `evidence_04` is preserved in `build/cache/vision/` from Step E.2).*

---

## 3. Extraction Methodology & Architecture

1. **Native Offline Engine:**
   - Framework: Apple `Vision.framework` (`VNRecognizeTextRequest`).
   - Recognition Level: `accurate` (`VNRequestTextRecognitionLevel.accurate`).
   - Runtime: macOS `/usr/bin/swift` standalone script execution.
   - Zero additional Python packages or external OCR binaries (such as Tesseract) required.

2. **Spatial Association & Provenance:**
   - Every recognized text block captures 2D normalized bounding box coordinates (`x, y, width, height`) and recognition confidence.
   - Text blocks are filtered and clustered using 2D spatial heuristics (Euclidean centroid distance and horizontal alignment) to associate resource identifiers (`account_*`, `search_*`, `data_flow_*`, `backup_*`, `analytics_*`, `tombstone_*`, `ORD-*`, `CS-*`) with nearby customer identifiers (`user_*`, emails, phone numbers) and status tokens.
   - Each observation retains its origin file ID, capture timestamp from `evidence_files.csv`, source origin system, and bounding box coordinates.

3. **Deterministic Local Caching:**
   - Storage Directory: `build/cache/apple_vision/`
   - Cache Key: SHA-256 hash of image file contents + provider (`apple_vision`) + version (`v1.0`).
   - Cache Format: Indented JSON containing raw OCR blocks, spatial clusters, structured observations, and execution metadata.
   - Cache Hit Behavior: Re-running extraction checks file SHA-256 and immediately loads cached JSON from disk (~3 ms execution time), avoiding redundant OCR invocations.

---

## 4. Ambiguity & Fail-Closed Guards

1. **UI Status vs. True Deletion State:**
   - Deletion success is never inferred solely from UI badges (e.g., "Deleted", "Purged", "Active").
   - Statuses extracted from UI screens are tagged as reported claims (`REPORTED_ABSENT`, `REPORTED_PRESENT`, `ACTIVE`, `INACTIVE`) and flagged with `APPLE_VISION_LOCAL_OCR`.
2. **Ambiguous Relationships:**
   - Observations where identity association relies on spatial proximity rather than explicit table row boundaries are marked with `ObservationConfidence.AMBIGUOUS` and `ambiguity_flags=["APPLE_VISION_LOCAL_OCR", "AMBIGUOUS_STATE_OR_IDENTITY_ASSOCIATION"]`.
3. **No Direct Customer Observations in `evidence_46`:**
   - `evidence_46` (`object_storage_01.png`) is an admin bucket view listing document names (`delivery_confirmation_*.pdf`, `invoice_*.pdf`) and byte sizes, without customer identity tuples. It is correctly classified as `PARSED_NO_RELEVANT_OBSERVATIONS`.
4. **Strict Privacy and Zero-Leakage:**
   - No personal values (names, emails, phone numbers) are logged to console or committed to documentation.
   - Only structural types, resource IDs, aggregate counts, and confidence flags are logged.

---

## 5. Compliance & Spend Verification

- **External Network Calls:** Exactly 0.
- **External API Invocation:** Exactly 0.
- **Tokens In / Out:** 0 / 0.
- **Total Spend:** $0.00.
- **`sample_output.csv` Access:** Never accessed or imported.
- **`dataset/` Integrity:** 100% untouched.
- **Root `output.csv` Integrity:** 100% untouched.

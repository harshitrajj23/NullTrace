# NullTrace — Data Compliance Audit and Zero-Cost Gate (Step E.3)

## A. Audit Metadata

- **Project:** NullTrace
- **Step:** E.3
- **Date checked:** 2026-10-25
- **Method:** local, read-only inspection
- **External API calls:** none
- **Dataset modifications:** none

---

## B. Repository Policy Findings

Every occurrence of the specified policy search terms (`third party`, `external`, `API`, `personal data`, `privacy`, `send`, `share`, `model`) across `AGENTS.md`, `CLAUDE.md`, `README.md`, and `problem_statement.md`:

### 1. AGENTS.md

- **File Path:** `AGENTS.md`  
  **Line Number:** 31  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "The dataset models a commerce platform where a workflow can report **Complete** while personal data remains in databases, replicas, logs, support attachments, exports, search indexes, analytics records, archives, or backups."

- **File Path:** `AGENTS.md`  
  **Line Number:** 60  
  **Matching Search Terms:** `share` (matched in word "shared")  
  **Exact Quotation:**  
  "- One shared log is used per checkout. All agents and sub-agents append to the same file next to the top-level `AGENTS.md`, never a private copy."

- **File Path:** `AGENTS.md`  
  **Line Number:** 61  
  **Matching Search Terms:** `API`, `personal data`  
  **Exact Quotation:**  
  "- Never log secrets. Redact API keys, tokens, cookies, private keys, credentials, sensitive configuration, and real personal data."

- **File Path:** `AGENTS.md`  
  **Line Number:** 83  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "1. Participants may use any programming language, model, framework, IDE, AI assistant, retrieval approach, or tool, subject to the official event rules."

- **File Path:** `AGENTS.md`  
  **Line Number:** 115  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "model=<exact_runtime_model_name>" (Context: Section 5.1 Session Start Entry template block)

- **File Path:** `AGENTS.md`  
  **Line Number:** 142  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "model=<exact_runtime_model_name>" (Context: Section 5.2 Per-Turn Entry template block)

- **File Path:** `AGENTS.md`  
  **Line Number:** 149  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "**Mandatory tool-name rule:** Every `SESSION START` and per-turn log entry must contain one non-empty `tool=` line with the exact name of the coding harness or agent writing the entry. Replace the template value before writing the log. The entry is invalid if `tool=` is missing, blank, still contains a placeholder, uses a generic label such as `AI`, contains only a model name, or names a different harness. Before responding, verify the value against the harness identity provided by the current runtime and re-read the appended entry to confirm it matches. Never guess the tool name. Correct any mismatch before responding to the user."

- **File Path:** `AGENTS.md`  
  **Line Number:** 151  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "**Mandatory model-name rule:** Every `SESSION START` and per-turn log entry must contain one non-empty `model=` line with the exact model identifier used for that turn. Always make sure that model name is correct & not made up. `model=unknown`, a model family, a generic label, an inferred name, and a template placeholder are invalid. Obtain the exact identifier from the runtime, session metadata, harness configuration, or another authoritative environment source before writing the entry. Never guess the model name. The model name does not replace the `tool=` value because the coding harness and the model are separate fields."

- **File Path:** `AGENTS.md`  
  **Line Number:** 153  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "**Required harness-and-model check:** Both `tool=` and `model=` must always be present in every `SESSION START` and per-turn entry. An entry is invalid if either field is missing, blank, unknown, generic, inferred, or still contains a template placeholder. Before completing a response, re-read the newly appended log entry and confirm that it contains exactly one populated `tool=` line and exactly one populated `model=` line with authoritative values. If either is absent or invalid, determine the correct value and correct the entry before responding."

- **File Path:** `AGENTS.md`  
  **Line Number:** 159  
  **Matching Search Terms:** `share` (matched in word "shared")  
  **Exact Quotation:**  
  "- Worktrees use the same shared log file, not a per-worktree copy."

- **File Path:** `AGENTS.md`  
  **Line Number:** 163  
  **Matching Search Terms:** `API`  
  **Exact Quotation:**  
  "- API keys, tokens, session cookies, OAuth codes, credentials, or private keys." (Context: Section 5.4 What Not To Log list item)

- **File Path:** `AGENTS.md`  
  **Line Number:** 164  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "- Sensitive configuration or real personal data." (Context: Section 5.4 What Not To Log list item)

- **File Path:** `AGENTS.md`  
  **Line Number:** 348  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- model providers and model names;" (Context: Section 6.8 evaluation/usage_report.md specification list item)

- **File Path:** `AGENTS.md`  
  **Line Number:** 349  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- model-call counts;" (Context: Section 6.8 evaluation/usage_report.md specification list item)

- **File Path:** `AGENTS.md`  
  **Line Number:** 353  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- per-model and overall totals when multiple models are used." (Context: Section 6.8 evaluation/usage_report.md specification list item)

- **File Path:** `AGENTS.md`  
  **Line Number:** 355  
  **Matching Search Terms:** `API`  
  **Exact Quotation:**  
  "Write the required evaluation metrics, custom cases, and usage details directly in these Markdown files. Never include API keys, credentials, or sensitive configuration values."

- **File Path:** `AGENTS.md`  
  **Line Number:** 368  
  **Matching Search Terms:** `API`, `personal data`  
  **Exact Quotation:**  
  "Do not include `dataset/`, virtual environments, dependency caches, nested archives, API keys, credentials, real personal data, or sensitive configuration in `code.zip`."

- **File Path:** `AGENTS.md`  
  **Line Number:** 381  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "- Keep every person, organization, identifier, and record fictional. Do not use real personal data."

- **File Path:** `AGENTS.md`  
  **Line Number:** 418  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- [ ] I have recorded the exact runtime model identifier in `model=`; it is never `unknown`, inferred, or generic."

- **File Path:** `AGENTS.md`  
  **Line Number:** 419  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- [ ] I have confirmed that both the harness name and model name are present and non-empty in the new log entry."

- **File Path:** `AGENTS.md`  
  **Line Number:** 420  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "- [ ] I will not log secrets or real personal data."

### 2. CLAUDE.md

- **File Path:** `CLAUDE.md`  
  **Matching Search Terms:** None  
  **Findings:** No matching occurrences found (file contains only `@AGENTS.md`).

### 3. README.md

- **File Path:** `README.md`  
  **Line Number:** 5  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "Build an AI agent that audits whether a user's personal data was actually deleted."

- **File Path:** `README.md`  
  **Line Number:** 97  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "- `usage_report.md` must cover the final full-dataset run, including model providers and names, model calls, input and output tokens, total and average tokens per request, and estimated total and per-request cost. Include per-model and overall totals when using multiple models."

- **File Path:** `README.md`  
  **Line Number:** 114  
  **Matching Search Terms:** `API`  
  **Exact Quotation:**  
  "- Do not include API keys, tokens, credentials, or secrets in prompts, code, configuration, or `log.txt`."

- **File Path:** `README.md`  
  **Line Number:** 127  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "You may use any programming language, model, framework, or retrieval approach. Include clear setup and execution instructions in `README.md` inside `code.zip`."

- **File Path:** `README.md`  
  **Line Number:** 157  
  **Matching Search Terms:** `API`, `personal data`  
  **Exact Quotation:**  
  "- no API keys, credentials, real personal data, or sensitive configuration values are included."

### 4. problem_statement.md

- **File Path:** `problem_statement.md`  
  **Line Number:** 5  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "What looked like a simple signup bug exposed a much larger failure. The investigation uncovered personal data across secondary databases, support attachments, search indexes, analytics exports, logs, archives, and backups. A synchronization job had even recreated information that the primary account service had successfully deleted."

- **File Path:** `problem_statement.md`  
  **Line Number:** 7  
  **Matching Search Terms:** `personal data`  
  **Exact Quotation:**  
  "Northstar Shop now needs an AI-powered deletion audit agent that can prove whether a user's personal data is truly gone before another failure causes financial and reputational damage."

- **File Path:** `problem_statement.md`  
  **Line Number:** 158  
  **Matching Search Terms:** `model`  
  **Exact Quotation:**  
  "The report must summarize the final full-dataset run that produced `output.csv`, including model providers and names, model calls, input and output tokens, total and average tokens per request, and estimated total and per-request cost. If multiple models are used, include both per-model and overall totals in the same file."

- **File Path:** `problem_statement.md`  
  **Line Number:** 160  
  **Matching Search Terms:** `API`  
  **Exact Quotation:**  
  "Do not include API keys, credentials, or sensitive configuration values in the submission."

---

## C. Evidence-File Classification

Compact inventory of all 94 evidence files under `dataset/evidence/`:

| Relative File Path | Personal Data Classification | Basis |
| :--- | :---: | :--- |
| `evidence/images/account_admin_console_20260926.png` | **yes** | Customer account console displaying personal contact details, street address, and order records |
| `evidence/images/search_index_inspector_20260901.png` | **yes** | Search index console displaying customer names, personal email addresses, and user reference identifiers |
| `evidence/images/connector_management_console_20260807.png` | **yes** | Integration management console displaying personal email addresses in data pipeline filter selectors |
| `evidence/images/analytics_profile_view_20260713.png` | **yes** | Analytics platform console displaying customer name, email address, user reference, and browsing history |
| `evidence/images/customer_export_console_20260618.png` | **yes** | Customer data export console displaying personal email addresses linked to generated customer export packages |
| `evidence/images/support_ticket_console_20260524.png` | **yes** | Support helpline console displaying customer name, email address, support message history, and order numbers |
| `evidence/images/backup_restore_console_20260429.png` | **yes** | Backup recovery console displaying personal email addresses in snapshot account ownership records |
| `evidence/images/security_audit_explorer_20260905.png` | **yes** | Security audit console displaying account-linked user identifier and personal authentication/lifecycle history |
| `evidence/images/deleted_account_reference_20260310.png` | **yes** | Customer reference registry displaying account-linked customer identifier and linked transaction history |
| `evidence/images/object_storage_browser_20260213.png` | **no** | Object storage file browser showing bucket keys and filenames; no direct personal identifiers visible on interface |
| `evidence/images/marketing_profile_console.png` | **yes** | Audience operations portal displaying customer name, email address, telephone number, and marketing preferences |
| `evidence/databases/account_service_primary.sql` | **yes** | Relational SQL snapshot containing customer profile tables and direct personal identity records |
| `evidence/databases/account_service_replica.sql` | **yes** | Relational SQL database replica containing customer profile tables and contact details |
| `evidence/databases/analytics_dw_snapshot.sql` | **yes** | Relational SQL data warehouse snapshot containing customer event records and user tracking identifiers |
| `evidence/databases/archive_db_snapshot.sql` | **yes** | Relational SQL archive export containing historical customer profile records and personal data |
| `evidence/databases/billing_db_snapshot.sql` | **yes** | Relational SQL billing database containing customer financial transactions, names, and billing references |
| `evidence/databases/crm_backup_snapshot.sql` | **yes** | Relational SQL customer relationship database containing customer names, emails, and phone records |
| `evidence/databases/customer_support_db.sql` | **yes** | Relational SQL support database containing customer ticket history, requester emails, and names |
| `evidence/databases/delivery_service_db.sql` | **yes** | Relational SQL logistics database containing customer delivery addresses, names, and phone numbers |
| `evidence/databases/email_marketing_db.sql` | **yes** | Relational SQL marketing database containing customer email addresses and campaign subscription states |
| `evidence/databases/identity_provider_db.sql` | **yes** | Relational SQL identity provider snapshot containing user credentials, email hashes, and identity rows |
| `evidence/databases/loyalty_rewards_db.sql` | **yes** | Relational SQL rewards database containing customer membership tiers, names, and linked account IDs |
| `evidence/databases/notification_service_db.sql` | **yes** | Relational SQL messaging database containing customer dispatch logs, phone numbers, and email alerts |
| `evidence/databases/order_management_db.sql` | **yes** | Relational SQL order database containing customer purchase records, shipping names, and addresses |
| `evidence/databases/payment_gateway_snapshot.sql` | **yes** | Relational SQL payment gateway export containing customer transaction receipts and billing references |
| `evidence/databases/product_reviews_db.sql` | **yes** | Relational SQL reviews database containing customer feedback records, author names, and user links |
| `evidence/databases/recommender_system_db.sql` | **yes** | Relational SQL recommendation database containing customer behavior profiles and user references |
| `evidence/databases/returns_processing_db.sql` | **yes** | Relational SQL returns database containing customer return requests, addresses, and tracking numbers |
| `evidence/databases/search_indexing_db.sql` | **yes** | Relational SQL search index database containing customer directory records and searchable attributes |
| `evidence/databases/security_audit_db.sql` | **yes** | Relational SQL security database containing customer login audit events, IP links, and user references |
| `evidence/databases/session_store_snapshot.sql` | **yes** | Relational SQL session store containing active customer web tokens, user IDs, and session records |
| `evidence/databases/shipping_manifest_db.sql` | **yes** | Relational SQL shipping database containing recipient customer names, postal addresses, and phone contacts |
| `evidence/databases/subscription_service_db.sql` | **yes** | Relational SQL recurring subscription database containing subscriber names, emails, and renewal records |
| `evidence/databases/user_preferences_db.sql` | **yes** | Relational SQL settings database containing customer language, marketing toggles, and user references |
| `evidence/databases/warehouse_inventory_db.sql` | **yes** | Relational SQL fulfillment database containing customer pick lists, order recipients, and shipping destinations |
| `evidence/documents/account_closure_notice_2026.pdf` | **yes** | Formatted PDF document confirming account closure and listing customer name and account reference |
| `evidence/documents/compliance_audit_summary_2026.pdf` | **yes** | Formatted PDF compliance review citing customer data handling cases and subject reference tokens |
| `evidence/documents/customer_statement_202608.pdf` | **yes** | Formatted PDF customer financial statement listing billing name, mailing address, and transaction items |
| `evidence/documents/gdpr_export_package_2026.pdf` | **yes** | Formatted PDF personal data export bundle containing customer identity records and profile attributes |
| `evidence/logs/account_activity.log` | **yes** | Application log recording customer profile modifications, password resets, and user lookup queries |
| `evidence/logs/analytics_pipeline.log` | **yes** | Pipeline log recording customer analytics event ingest, session markers, and tracking identifiers |
| `evidence/logs/api_gateway_access.log` | **yes** | Web gateway access log recording endpoint queries containing customer email and user ID query parameters |
| `evidence/logs/authentication_events.log` | **yes** | Security event log recording customer authentication requests, email identifiers, and login statuses |
| `evidence/logs/backup_scheduler.log` | **yes** | Operations log recording backup snapshot creation across customer databases with account references |
| `evidence/logs/billing_service.log` | **yes** | Service log recording customer invoicing attempts, cardholder references, and payment notifications |
| `evidence/logs/connector_sync.log` | **yes** | Integration event log recording customer data replication and connector dispatch events with user tokens |
| `evidence/logs/crm_integration.log` | **yes** | CRM sync log recording customer profile updates, contact sync events, and email address transfers |
| `evidence/logs/data_export_job.log` | **yes** | Export worker log recording customer download bundle creation and requester user identifiers |
| `evidence/logs/delivery_notifications.log` | **yes** | Notification log recording SMS and email dispatch with customer phone numbers and recipient addresses |
| `evidence/logs/email_delivery.log` | **yes** | Mail server log recording outbound email transmission with recipient email addresses and delivery statuses |
| `evidence/logs/gdpr_orchestrator.log` | **yes** | Deletion orchestrator log recording subject deletion requests, target user IDs, and verification steps |
| `evidence/logs/identity_sync.log` | **yes** | Directory sync log recording customer account attribute propagation across identity subsystems |
| `evidence/logs/loyalty_engine.log` | **yes** | Rewards engine log recording customer points calculations, user references, and membership tiers |
| `evidence/logs/marketing_campaigns.log` | **yes** | Campaign manager log recording email list segmentation, recipient email hashes, and campaign responses |
| `evidence/logs/object_storage_access.log` | **yes** | Storage access log recording customer document retrieval requests and attachment object references |
| `evidence/logs/order_processing.log` | **yes** | Order lifecycle log recording customer order submission, shipping names, and payment associations |
| `evidence/logs/payment_processing.log` | **yes** | Transaction log recording payment settlements with customer references and billing account IDs |
| `evidence/logs/product_recommendations.log` | **yes** | Recommender log recording customer browsing events, personalized candidate items, and user references |
| `evidence/logs/restore_operations.log` | **yes** | Disaster recovery log recording snapshot restoration attempts targeting customer platform databases |
| `evidence/logs/returns_service.log` | **yes** | Return service log recording customer RMA submissions, shipping labels, and recipient contact tokens |
| `evidence/logs/search_indexer.log` | **yes** | Search daemon log recording customer directory reindexing events and searchable customer attributes |
| `evidence/logs/security_audit.log` | **yes** | Security journal recording privileged administrator lookups targeting specific customer user IDs |
| `evidence/logs/support_ticketing.log` | **yes** | Support engine log recording customer ticket submissions, conversation updates, and requester emails |
| `evidence/logs/warehouse_dispatch.log` | **yes** | Fulfillment center log recording customer package labeling, dispatch scans, and delivery destinations |
| `evidence/records/account_profile_bundle.json` | **yes** | Structured JSON record bundle containing customer profile details, emails, phones, and account metadata |
| `evidence/records/address_book_records.json` | **yes** | Structured JSON record bundle containing customer postal addresses, recipient names, and phone numbers |
| `evidence/records/analytics_event_stream.json` | **yes** | Structured JSON record bundle containing customer tracking events, session IDs, and user identifiers |
| `evidence/records/archive_manifest.json` | **yes** | Structured JSON record bundle containing customer archive inventory, storage keys, and subject references |
| `evidence/records/billing_profiles.json` | **yes** | Structured JSON record bundle containing customer billing accounts, cardholder names, and addresses |
| `evidence/records/consent_records.json` | **yes** | Structured JSON record bundle containing customer privacy consents, opt-in timestamps, and email identifiers |
| `evidence/records/crm_contacts.json` | **yes** | Structured JSON record bundle containing customer CRM profile records, phone numbers, and full names |
| `evidence/records/customer_documents.json` | **yes** | Structured JSON record bundle containing customer document metadata, upload history, and user references |
| `evidence/records/customer_feedback.json` | **yes** | Structured JSON record bundle containing customer product reviews, author usernames, and ratings |
| `evidence/records/customer_notes.json` | **yes** | Structured JSON record bundle containing customer support agent notes and account-linked case history |
| `evidence/records/data_retention_policy.json` | **yes** | Structured JSON record bundle containing customer retention exceptions and subject reference overrides |
| `evidence/records/device_registry.json` | **yes** | Structured JSON record bundle containing customer registered mobile devices, push tokens, and user IDs |
| `evidence/records/email_subscriptions.json` | **yes** | Structured JSON record bundle containing customer newsletter preferences, email addresses, and statuses |
| `evidence/records/identity_graph.json` | **yes** | Structured JSON record bundle containing customer cross-system identifier linkages and account mappings |
| `evidence/records/interaction_history.json` | **yes** | Structured JSON record bundle containing customer touchpoints, support phone logs, and interaction timestamps |
| `evidence/records/invoice_archive.json` | **yes** | Structured JSON record bundle containing customer invoice records, line items, and recipient names |
| `evidence/records/loyalty_members.json` | **yes** | Structured JSON record bundle containing customer loyalty accounts, point balances, and member names |
| `evidence/records/marketing_leads.json` | **yes** | Structured JSON record bundle containing prospective customer contact details, emails, and lead sources |
| `evidence/records/order_archive.json` | **yes** | Structured JSON record bundle containing historical customer orders, delivery recipients, and addresses |
| `evidence/records/payment_methods.json` | **yes** | Structured JSON record bundle containing customer stored payment tokens, cardholder names, and user links |
| `evidence/records/preferences_bundle.json` | **yes** | Structured JSON record bundle containing customer account preferences, language choices, and user IDs |
| `evidence/records/returns_records.json` | **yes** | Structured JSON record bundle containing customer return authorization requests and tracking references |
| `evidence/records/search_history.json` | **yes** | Structured JSON record bundle containing customer product search queries and user identifier associations |
| `evidence/records/security_credentials.json` | **yes** | Structured JSON record bundle containing customer authentication records, email hashes, and user IDs |
| `evidence/records/shipping_labels.json` | **yes** | Structured JSON record bundle containing customer shipping label records, recipient names, and addresses |
| `evidence/records/subscription_records.json` | **yes** | Structured JSON record bundle containing customer recurring subscriptions, renewal emails, and user links |
| `evidence/records/support_tickets.json` | **yes** | Structured JSON record bundle containing customer support cases, conversation transcripts, and emails |
| `evidence/records/user_handover_notes.txt` | **yes** | Plain-text shift handover document noting customer-specific deletion and support operational actions |
| `evidence/records/user_sessions.json` | **yes** | Structured JSON record bundle containing customer web session records, IP addresses, and user references |

---

## D. Classification Summary

- **Number classified yes:** 93
- **Number classified no:** 1
- **Number classified unclear:** 0
- **Total number of files classified:** 94

The classification counts reconcile exactly with the 94 inspected evidence files under `dataset/evidence/` (11 images, 24 databases, 4 documents, 26 logs, and 29 records).

---

## E. External-Processing Decision

```text
DECISION: MODEL_OFF
```

### Explanation:
1. **Conservative Safety Policy:** This decision is deliberately conservative. Ninety-three out of ninety-four evidence files (98.9%) contain direct personal data (names, emails, telephone numbers, postal addresses, or account-linked subject identifiers).
2. **Zero External Processing Authorization:** No external model processing is authorized by this audit.
3. **Data Protection Compliance:** The widespread presence of personal data across the evidence corpus, uncertainty regarding participant transmission boundaries under challenge policies, and the lack of explicit affirmative authorization prevent approval for sending evidence files to external AI endpoints.
4. **Binding Nature:** This decision remains strictly in force until the user explicitly changes it after reviewing these findings.
5. **No Precedent from Previous Pilots:** A successful previous API call does not establish that further processing is permitted.
6. **Free Tier Irrelevance:** A free API tier does not automatically make the external transmission of personal data legally, ethically, or procedurally permissible.

---

## F. Billing and Model Eligibility

- **Zero API Calls:** No external API calls were initiated or executed during this audit.
- **Untested Eligibility:** No model eligibility, quota availability, or billing status was tested through an API request.
- **Unverified Free Tier:** Gemini's free-tier eligibility has not been established by this audit.
- **Estimated vs Actual Cost:** Estimated token costs recorded in diagnostic tools are simulated projections and do not constitute proof of actual billed charges.
- **Zero-Paid-Spend Gate:** No paid API calls are authorized.
- **Vision Model State:** Vision model processing remains strictly disabled (`ENABLE_GEMINI_VISION=false`).

---

## G. Limitations

1. **Policy Silence:** Repository policy files (`AGENTS.md`, `README.md`, `problem_statement.md`) do not explicitly prohibit external AI APIs (stating that participants "may use any programming language, model, framework, IDE, AI assistant, retrieval approach, or tool"), but they strictly require redacting personal data and secrets, keeping all subject records fictional, and excluding personal data from deliverables.
2. **Conservative Interpretation:** In accordance with audit standards, the absence of an explicit prohibition must never be interpreted as permission to transmit unredacted personal data to third-party endpoints.
3. **Evidence Isolation:** `dataset/sample_output.csv` was never opened, read, or accessed during this audit.

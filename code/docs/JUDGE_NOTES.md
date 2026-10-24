# NullTrace: Notes for Evaluators and Judges

## Step F: Subject-to-Resource Linkage via System Activity

### 1. Rationale for Using System Activity Rows
In modern distributed architectures, personal data does not reside in a single monolithic database. Instead, microservices, asynchronous workers, and event pipelines interact via operational events (deletions, syncs, index refreshes, exports, backups). The `system_activity.csv` stream captures these operational claims and catalog bindings. Linking candidate resources from activity events enables the audit agent to identify which specific resource instances (`account_*`, `search_*`, `analytics_*`, `tombstone_*`, `export_*`) were affected by or associated with a subject's deletion request before the `audit_at` cutoff timestamp.

### 2. Confidence Assignment Following Decision D3
The resource linker strictly respects Decision D3 established in identity resolution:
- **`CONFIRMED` (`SUBJECT_USER_ID_MATCH`)**: Assigned when the activity record explicitly binds to the subject's internal `user_id`. The internal user ID is a unique primary key across the platform, providing definitive provenance that the operational record pertains to that subject.
- **`PROBABLE` (`SUBJECT_EMAIL_MATCH`, `SUBJECT_PHONE_MATCH`)**: Assigned when an activity row references an email address or telephone number without an explicit `user_id` match. Because email addresses and phone numbers can be updated, recycled, or present as secondary contact information across multiple contexts, non-user-id matches remain probable until corroborated by primary database snapshots or cryptographic hashes.

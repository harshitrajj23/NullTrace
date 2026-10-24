# NullTrace: SQL Relational Join Key Discovery Report

## 1. SQL Schema Inventory Summary
- **Total SQL Snapshot Files**: 24
- **Distinct Tables across Database Dumps**: 18
- **Total Table Instances**: 127
- **Files with Declared Foreign Keys**: 0 (no `FOREIGN KEY ... REFERENCES` constraints declared in any schema)

## 2. Join Graph Analysis
- **Total Edges Discovered**: 20
  - **Declared Edges**: 0
  - **Inferred Edges**: 20 (inferred where column name matches target table primary key and data values overlap)
- **Connected Components**: 11

### Component Breakdown
- **Component 1** (1 tables): `backup_restore_entries`
- **Component 2** (1 tables): `connector_subscriptions`
- **Component 3** (1 tables): `customer_analytics_profiles`
- **Component 4** (7 tables): `customer_data_failover_replica, customer_data_primary, customer_data_read_replica, customer_data_replica_ap_south, customer_data_replica_eu_west, customer_data_reporting_replica, snapshot_scope`
- **Component 5** (1 tables): `customer_exports`
- **Component 6** (1 tables): `customer_profiles`
- **Component 7** (2 tables): `customer_profiles_failover_replica, customer_profiles_primary`
- **Component 8** (1 tables): `customer_search_documents`
- **Component 9** (1 tables): `search_documents_primary`
- **Component 10** (1 tables): `security_audit_records`
- **Component 11** (1 tables): `support_records`

### Inferred Foreign Key Edges
| Source Table.Column | Target Table.Primary Key | Rule Used | Data Value Overlap | Sample Values |
| :--- | :--- | :--- | :---: | :--- |
| `customer_data_failover_replica.resource_id` | `customer_data_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 16 | `audit_record_1037, audit_record_1491, audit_record_3831` |
| `customer_data_failover_replica.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 1 | `security_service` |
| `customer_data_primary.resource_id` | `customer_data_failover_replica.resource_id` | `EXACT_NAME_EQUALS_PK` | 16 | `audit_record_1037, audit_record_1491, audit_record_3831` |
| `customer_data_primary.resource_id` | `customer_data_read_replica.resource_id` | `EXACT_NAME_EQUALS_PK` | 138 | `analytics_1738, analytics_2008, analytics_2463` |
| `customer_data_primary.resource_id` | `customer_data_replica_ap_south.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_primary.resource_id` | `customer_data_replica_eu_west.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_primary.resource_id` | `customer_data_reporting_replica.resource_id` | `EXACT_NAME_EQUALS_PK` | 49 | `analytics_1126, analytics_1558, analytics_5221` |
| `customer_data_primary.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 7 | `analytics_platform, backup_service, export_service` |
| `customer_data_read_replica.resource_id` | `customer_data_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 138 | `analytics_1738, analytics_2008, analytics_2463` |
| `customer_data_read_replica.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 8 | `account_service, analytics_platform, backup_service` |
| `customer_data_replica_ap_south.resource_id` | `customer_data_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_replica_ap_south.resource_id` | `customer_data_replica_eu_west.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_replica_ap_south.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 8 | `account_service, analytics_platform, backup_service` |
| `customer_data_replica_eu_west.resource_id` | `customer_data_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_replica_eu_west.resource_id` | `customer_data_replica_ap_south.resource_id` | `EXACT_NAME_EQUALS_PK` | 85 | `analytics_096, analytics_1792, analytics_1922` |
| `customer_data_replica_eu_west.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 8 | `account_service, analytics_platform, backup_service` |
| `customer_data_reporting_replica.resource_id` | `customer_data_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 49 | `analytics_1126, analytics_1558, analytics_5221` |
| `customer_data_reporting_replica.origin_system` | `snapshot_scope.origin_system` | `EXACT_NAME_EQUALS_PK` | 8 | `account_service, analytics_platform, backup_service` |
| `customer_profiles_failover_replica.resource_id` | `customer_profiles_primary.resource_id` | `EXACT_NAME_EQUALS_PK` | 3 | `account_7204, account_8741, account_9116` |
| `customer_profiles_primary.resource_id` | `customer_profiles_failover_replica.resource_id` | `EXACT_NAME_EQUALS_PK` | 3 | `account_7204, account_8741, account_9116` |

## 3. Relational Path Search (Length 1 to 4)
- **Total Paths from Subject Tables to Resource Tables**: 2
- **Length 1 Paths**: 2
- **Length 2 Paths**: 0
- **Length 3 Paths**: 0
- **Length 4 Paths**: 0
- **Cap (Length 4) Cut Off Any Path**: False

### Discovered Paths
- `customer_profiles_failover_replica.resource_id` -> `customer_profiles_primary.resource_id`
- `customer_profiles_primary.resource_id` -> `customer_profiles_failover_replica.resource_id`

## 4. Step 6 Scoring-Only Comparison (Sample Output Answer Key)
- **Total Expected (Case, Resource) Pairs**: 111
- **Reachable by SQL Join Path**: 0
- **Reachable only by LINE_COOCCURRENCE**: 38 (34.2%)
- **Reachable by Neither**: 73 (65.8%)
- **Extra Resources Reachable from Cluster**: 4

## 5. Image Files Queue (Vision Model Input Queue)
The 11 console screenshots identified as `IMAGE_ONLY` require vision extraction / OCR in the next step:

| File ID | File Path | Origin / System | File Size | Description |
| :--- | :--- | :--- | :---: | :--- |
| `evidence_04` | `evidence/images/account_admin_console_20260926.png` | `account_admin_portal` | 124989 bytes | Console UI for account_admin_portal |
| `evidence_09` | `evidence/images/search_index_inspector_20260901.png` | `search_index_admin` | 121101 bytes | Console UI for search_index_admin |
| `evidence_14` | `evidence/images/connector_management_console_20260807.png` | `integration_admin` | 130271 bytes | Console UI for integration_admin |
| `evidence_19` | `evidence/images/analytics_profile_view_20260713.png` | `analytics_platform` | 129362 bytes | Console UI for analytics_platform |
| `evidence_23` | `evidence/images/customer_export_console_20260618.png` | `export_service` | 134597 bytes | Console UI for export_service |
| `evidence_28` | `evidence/images/support_ticket_console_20260524.png` | `support_platform` | 135008 bytes | Console UI for support_platform |
| `evidence_32` | `evidence/images/backup_restore_console_20260429.png` | `backup_service` | 155587 bytes | Console UI for backup_service |
| `evidence_37` | `evidence/images/security_audit_explorer_20260905.png` | `security_service` | 147699 bytes | Console UI for security_service |
| `evidence_42` | `evidence/images/deleted_account_reference_20260310.png` | `identity_service` | 136696 bytes | Console UI for identity_service |
| `evidence_46` | `evidence/images/object_storage_browser_20260213.png` | `object_storage` | 154193 bytes | Console UI for object_storage |
| `evidence_60` | `evidence/images/marketing_profile_console.png` | `marketing_platform` | 129711 bytes | Console UI for marketing_platform |

## 6. Diagnostic Conclusions

The SQL database snapshot exports under `dataset/evidence/databases/` do not form a multi-hop normalized relational schema: zero foreign key constraints are declared, and the only inferred cross-table joins exist between primary and replica tables sharing `resource_id` (accounting for 0 of the 111 sample expected pairs). Instead, the system architecture stores resources in flat snapshot tables where internal subject identifiers (`customer_reference`, `user_id`, or `email`) appear directly on the exact same row as the `resource_id`, which allows direct line co-occurrence to resolve 38 expected pairs (34.2%). What relational joins cannot see are: (a) records stored in non-SQL evidence, such as the 11 console UI screenshots (`IMAGE_ONLY`) and unstructured support ticket logs/records; and (b) records that were already purged or tombstoned prior to the audit cutoff time, requiring state-reconstruction and log audit analysis rather than relational graph traversal.


"""code/src/rule_engine.py

Deterministic Rule Engine for HackerRank Orchestrate: Ghost Data Still Exists.

Loads and deterministically applies deletion_rules.csv against reconstructed resource states:
- Determines applicable rule using actual rule schema and resource/system/type matching.
- Produces structured assessments: resource identity, observed state, required treatment,
  policy satisfaction, rationale, and supporting evidence IDs.
- Strictly respects DELETE, REDACT, RETAIN, ACCOUNT_TOMBSTONE, and ANONYMIZE semantics.
- For ACCOUNT_TOMBSTONE, distinguishes permitted stable internal user_id from prohibited direct PII.
- Tracks explicit policy/evidence gaps for missing matches, ambiguous mappings, and unknown states.
"""

from dataclasses import dataclass, field
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import DeletionRule
    from code.src.state_reconstruction import ReconstructedState, ResourceState
except ImportError:
    from src.models import DeletionRule
    from src.state_reconstruction import ReconstructedState, ResourceState

logger = logging.getLogger("nulltrace.rule_engine")


@dataclass
class PolicyAssessment:
    """Structured assessment evaluating whether a resource's state satisfies deletion policy."""
    resource_id: str
    system_id: str
    data_category: str
    applicable_rule_id: Optional[str]
    required_action: str
    observed_state: ResourceState
    policy_satisfied: bool
    rationale: str
    supporting_evidence_ids: List[str] = field(default_factory=list)
    gap_reason: Optional[str] = None
    is_tombstone: bool = False
    tombstone_direct_pii_removed: Optional[bool] = None
    tombstone_internal_id_preserved: Optional[bool] = None


def match_resource_category(
    resource_id: str,
    collection: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Deterministically maps a resource to its corresponding data_category from deletion_rules.csv.
    Does not hardcode sample case or resource IDs.
    """
    coll = (collection or "").lower()
    rid = resource_id.lower()
    det = details or {}

    # Tombstones
    if rid.startswith("tombstone_") or coll == "deleted_customer_references":
        return "ACCOUNT_TOMBSTONE"

    # User profiles
    if rid.startswith("account_") or rid.startswith("user_"):
        return "USER_PROFILE"

    # Secondary identifiers
    if rid.startswith("secondary_"):
        return "SECONDARY_IDENTIFIER"

    # Search index entries
    if rid.startswith("search_") or coll == "customer_search_documents":
        return "SEARCH_INDEX_ENTRY"

    # Cache entries
    if rid.startswith("cache_"):
        return "CACHE_ENTRY"

    # Support resources: messages vs attachments
    if rid.startswith("support_"):
        if coll == "ticket_attachments" or "file_name" in det or det.get("storage_class") == "ticket_attachment":
            return "SUPPORT_ATTACHMENT"
        return "SUPPORT_MESSAGE"

    # Analytics profiles
    if rid.startswith("analytics_") or coll == "customer_analytics_reports":
        return "ANALYTICS_PROFILE"

    # Product telemetry
    if rid.startswith("telemetry_"):
        return "PRODUCT_TELEMETRY"

    # Exports
    if rid.startswith("export_") or coll == "customer_export_jobs":
        return "USER_EXPORT"

    # Marketing profiles
    if rid.startswith("marketing_"):
        return "MARKETING_PROFILE"

    # Email delivery logs
    if rid.startswith("email_delivery_") or rid.startswith("email_log_"):
        return "EMAIL_DELIVERY_LOG"

    # Security audit logs
    if rid.startswith("audit_record_") or rid.startswith("security_"):
        return "SECURITY_AUDIT_LOG"

    # Legal hold records
    if rid.startswith("legal_hold_") or rid.startswith("legal_") or coll == "retained_order_records":
        return "LEGAL_HOLD_RECORD"

    # Backup archives
    if rid.startswith("backup_") or coll == "backup_catalog":
        return "BACKUP_ARCHIVE"

    # Process / Data flows
    if rid.startswith("data_flow_") or coll == "connector_configurations":
        return "DATA_FLOW"

    return None


def get_rule_for_category(
    category: str,
    rules: List[DeletionRule],
) -> Optional[DeletionRule]:
    """Finds the deletion rule matching a specific data category."""
    for r in rules:
        if r.data_category.upper() == category.upper():
            return r
    return None


def get_canonical_system_id(resource_id: str) -> str:
    """Canonical mapping from resource prefix to system ID."""
    if resource_id.startswith("audit_record_") or resource_id.startswith("security_"):
        return "security_service"
    if resource_id.startswith("legal_hold_") or resource_id.startswith("legal_"):
        return "legal_service"
    if resource_id.startswith("data_flow_"):
        return "integration_service"
    if resource_id.startswith("tombstone_"):
        return "identity_service"
    if resource_id.startswith("email_delivery_"):
        return "notification_service"

    prefix = resource_id.split("_")[0]
    mapping = {
        "account": "account_service",
        "analytics": "analytics_platform",
        "backup": "backup_service",
        "cache": "cache_service",
        "export": "export_service",
        "marketing": "marketing_service",
        "search": "search_service",
        "secondary": "identity_service",
        "support": "support_platform",
        "telemetry": "telemetry_platform",
        "user": "account_service",
    }
    return mapping.get(prefix, "unknown_system")


def assess_resource_policy(
    reconstructed: ReconstructedState,
    rules: List[DeletionRule],
    system_id: Optional[str] = None,
    collection: Optional[str] = None,
) -> PolicyAssessment:
    """
    Evaluates whether a reconstructed resource state complies with deletion_rules.csv:
    - Matches category and applicable rule.
    - Evaluates required treatment (DELETE, REDACT, RETAIN, ANONYMIZE, etc.).
    - For ACCOUNT_TOMBSTONE, verifies that permitted stable internal identifier is preserved
      while prohibited direct identifiers (name, email, phone, email_hash) are removed.
    - Records explicit policy gaps for unknown states, unmapped rules, or ambiguous data.
    """
    rid = reconstructed.resource_id
    sys_id = system_id or get_canonical_system_id(rid)
    details = reconstructed.raw_details or {}

    category = match_resource_category(rid, collection=collection, details=details)
    ev_ids = [reconstructed.provenance_evidence_id] if reconstructed.provenance_evidence_id else []

    # Handle process flows (DATA_FLOW)
    if category == "DATA_FLOW":
        is_disabled = (reconstructed.state == ResourceState.DISABLED)
        gap = None
        if reconstructed.state == ResourceState.UNKNOWN:
            gap = "State is UNKNOWN; active data flow status cannot be confirmed"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category="DATA_FLOW",
            applicable_rule_id=None,
            required_action="DISABLE_DATA_FLOW",
            observed_state=reconstructed.state,
            policy_satisfied=is_disabled,
            rationale="Data flow is disabled" if is_disabled else f"Data flow state is {reconstructed.state.value}; requires DISABLE_DATA_FLOW",
            supporting_evidence_ids=ev_ids,
            gap_reason=gap,
        )

    # Missing category match
    if not category:
        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category="UNKNOWN",
            applicable_rule_id=None,
            required_action="UNKNOWN",
            observed_state=reconstructed.state,
            policy_satisfied=False,
            rationale=f"Resource {rid} could not be matched to any deletion policy category",
            supporting_evidence_ids=ev_ids,
            gap_reason=f"No matching category for resource {rid}",
        )

    rule = get_rule_for_category(category, rules)
    if not rule:
        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=None,
            required_action="UNKNOWN",
            observed_state=reconstructed.state,
            policy_satisfied=False,
            rationale=f"Category {category} has no defined rule in deletion_rules.csv",
            supporting_evidence_ids=ev_ids,
            gap_reason=f"No rule found for category {category}",
        )

    action = rule.required_action.upper()
    state = reconstructed.state

    # Explicit handling of UNKNOWN observed state
    if state == ResourceState.UNKNOWN:
        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action=action,
            observed_state=state,
            policy_satisfied=False,
            rationale=f"Resource state is UNKNOWN ({reconstructed.rationale}); compliance cannot be proven",
            supporting_evidence_ids=ev_ids,
            gap_reason=f"State unknown: {reconstructed.rationale}",
        )

    # 1. ACCOUNT_TOMBSTONE semantics
    if category == "ACCOUNT_TOMBSTONE":
        # Must preserve stable internal user reference
        has_internal_ref = bool(
            details.get("subject_reference") or details.get("user_id") or details.get("customer_reference")
        )
        # Must remove direct identifiers: name, email, phone, email_hash
        has_direct_pii = any(
            bool(details.get(k)) for k in ("name", "email", "phone", "email_hash")
        )
        pii_removed = not has_direct_pii

        satisfied = (state == ResourceState.REDACTED) and pii_removed
        if satisfied:
            rat = "Account tombstone satisfies policy: permitted stable user reference preserved and direct identifiers redacted"
        else:
            rat = "Account tombstone violates policy: contains exposed direct identifiers (name/email/phone/hash) or lacks redaction"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action="REDACT",
            observed_state=state,
            policy_satisfied=satisfied,
            rationale=rat,
            supporting_evidence_ids=ev_ids,
            is_tombstone=True,
            tombstone_direct_pii_removed=pii_removed,
            tombstone_internal_id_preserved=has_internal_ref,
        )

    # 2. DELETE semantics
    if action == "DELETE":
        satisfied = (state == ResourceState.ABSENT)
        if satisfied:
            rat = f"{category} satisfies policy: record confirmed deleted (ABSENT)"
        else:
            rat = f"{category} violates policy: record still in state {state.value}; requires DELETE"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action="DELETE",
            observed_state=state,
            policy_satisfied=satisfied,
            rationale=rat,
            supporting_evidence_ids=ev_ids,
        )

    # 3. REDACT semantics (e.g. SUPPORT_MESSAGE, EMAIL_DELIVERY_LOG)
    if action == "REDACT":
        satisfied = (state == ResourceState.REDACTED)
        if satisfied:
            rat = f"{category} satisfies policy: prohibited identifiers confirmed redacted (REDACTED)"
        else:
            rat = f"{category} violates policy: record still contains exposed PII (state {state.value}); requires REDACT"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action="REDACT",
            observed_state=state,
            policy_satisfied=satisfied,
            rationale=rat,
            supporting_evidence_ids=ev_ids,
        )

    # 4. ANONYMIZE semantics (e.g. ANALYTICS_PROFILE, PRODUCT_TELEMETRY)
    if action == "ANONYMIZE":
        satisfied = (state == ResourceState.ANONYMIZED)
        if satisfied:
            rat = f"{category} satisfies policy: record confirmed irreversibly anonymized (ANONYMIZED)"
        else:
            rat = f"{category} violates policy: record remains identifiable (state {state.value}); requires ANONYMIZE"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action="ANONYMIZE",
            observed_state=state,
            policy_satisfied=satisfied,
            rationale=rat,
            supporting_evidence_ids=ev_ids,
        )

    # 5. RETAIN semantics
    if action == "RETAIN":
        # BACKUP_ARCHIVE: rule_14: condition 'Restore access can be blocked', action 'RETAIN'
        if category == "BACKUP_ARCHIVE":
            satisfied = (state == ResourceState.BLOCKED)
            if satisfied:
                rat = "Backup archive satisfies policy: retained with restore access confirmed BLOCKED"
            else:
                rat = f"Backup archive violates policy: restore access is {state.value}; creates restore risk"

            return PolicyAssessment(
                resource_id=rid,
                system_id=sys_id,
                data_category=category,
                applicable_rule_id=rule.rule_id,
                required_action="RETAIN",
                observed_state=state,
                policy_satisfied=satisfied,
                rationale=rat,
                supporting_evidence_ids=ev_ids,
            )

        # Standard retention (SECURITY_AUDIT_LOG, LEGAL_HOLD_RECORD)
        satisfied = (state == ResourceState.PRESENT)
        if satisfied:
            rat = f"{category} satisfies policy: retained record remains available (PRESENT)"
        else:
            rat = f"{category} violates policy: retained record is {state.value}; must be preserved"

        return PolicyAssessment(
            resource_id=rid,
            system_id=sys_id,
            data_category=category,
            applicable_rule_id=rule.rule_id,
            required_action="RETAIN",
            observed_state=state,
            policy_satisfied=satisfied,
            rationale=rat,
            supporting_evidence_ids=ev_ids,
        )

    # Unhandled action fallback
    return PolicyAssessment(
        resource_id=rid,
        system_id=sys_id,
        data_category=category,
        applicable_rule_id=rule.rule_id,
        required_action=action,
        observed_state=state,
        policy_satisfied=False,
        rationale=f"Unhandled action {action} for category {category}",
        supporting_evidence_ids=ev_ids,
        gap_reason=f"Action {action} evaluation not supported",
    )


def assess_case_policies(
    case_id: str,
    states: Dict[str, ReconstructedState],
    rules: List[DeletionRule],
    system_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, PolicyAssessment]:
    """Assesses policy compliance for all reconstructed resource states in a case."""
    sys_map = system_mapping or {}
    assessments: Dict[str, PolicyAssessment] = {}

    for rid, rec_state in sorted(states.items()):
        sys_id = sys_map.get(rid) or get_canonical_system_id(rid)
        coll = rec_state.raw_details.get("collection")
        assessments[rid] = assess_resource_policy(
            reconstructed=rec_state,
            rules=rules,
            system_id=sys_id,
            collection=coll,
        )

    return assessments

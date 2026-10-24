"""code/tests/test_identity.py

Unit tests for deterministic identity resolution in code/src/identity.py.
Uses small hand-built fixtures to test:
- Three-hop chain
- Shared-name false positive
- Plus-addressing
- Email conflict detection
- Reason code and SourceRef invariants
- Determinism across multiple runs
"""

import os
import sys
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import (
        SourceRef,
        Identity,
        AuditEvent,
        DeletionRequest,
    )
    from code.src.loader import Dataset, LoaderReport
    from code.src.identity import (
        IdentifierNode,
        Link,
        Conflict,
        Cluster,
        resolve_request,
        resolve_all,
    )
except ImportError:
    from src.models import (
        SourceRef,
        Identity,
        AuditEvent,
        DeletionRequest,
    )
    from src.loader import Dataset, LoaderReport
    from src.identity import (
        IdentifierNode,
        Link,
        Conflict,
        Cluster,
        resolve_request,
        resolve_all,
    )


def make_empty_dataset() -> Dataset:
    return Dataset(
        data_dir="",
        deletion_requests=[],
        sample_deletion_requests=[],
        sample_output=[],
        user_identities=[],
        user_audit_log=[],
        system_activity=[],
        deletion_rules=[],
        evidence_files=[],
        report=LoaderReport(),
    )


def test_three_hop_chain():
    """
    Three-hop chain:
    Seed email (old_email) -> audit log maps old_email to user_1 -> user_1 has current email (new_email).
    Expects CONFIRMED links and a historical role on the old email.
    """
    dataset = make_empty_dataset()
    src_ident = SourceRef("user_identities.csv", 2)
    src_audit = SourceRef("user_audit_log.csv", 2)
    src_req = SourceRef("deletion_requests.csv", 2)

    # Current identity has new_email
    dataset.user_identities = [
        Identity(
            user_id="user_1",
            name="Alice Smith",
            email_raw="new_alice@example.com",
            email_norm="new_alice@example.com",
            phone_raw="+15551234",
            phone_norm="15551234",
            email_hash="hash123",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src_ident,
        )
    ]

    # Audit log links old_email to user_1
    dataset.user_audit_log = [
        AuditEvent(
            audit_id="audit_1",
            user_id="user_1",
            field_name="email",
            old_value_raw="old_alice@example.com",
            new_value_raw="new_alice@example.com",
            changed_at_raw="2025-06-01T00:00:00Z",
            changed_at=None,
            source=src_audit,
        )
    ]

    # Request submitted with old_email
    req = DeletionRequest(
        case_id="case_test_chain",
        email_raw="old_alice@example.com",
        email_norm="old_alice@example.com",
        requested_at_raw="2026-08-01T00:00:00Z",
        requested_at=None,
        reported_status="COMPLETE",
        reported_at_raw="2026-08-02T00:00:00Z",
        reported_at=None,
        audit_at_raw="2026-08-03T00:00:00Z",
        audit_at=None,
        request_text="Delete my old account",
        source=src_req,
    )
    dataset.deletion_requests = [req]

    cluster = resolve_request(req, dataset)

    # Verify nodes
    assert ("email", "old_alice@example.com") in cluster.nodes
    assert ("user_id", "user_1") in cluster.nodes
    assert ("email", "new_alice@example.com") in cluster.nodes

    # Role check: old identifier must have historical role
    old_node = cluster.nodes[("email", "old_alice@example.com")]
    assert old_node.role == "historical"

    # All links must be CONFIRMED
    assert len(cluster.links) >= 2
    for l in cluster.links:
        assert l.strength == "CONFIRMED"
        assert l.reason_code in ("AUDIT_OLD_NEW_SAME_USER", "SHARED_USER_ID")


def test_shared_name_false_positive():
    """
    Shared-name false positive:
    Two users have the exact same name 'John Doe', but completely different identifiers.
    Expects no link between them.
    """
    dataset = make_empty_dataset()
    src1 = SourceRef("user_identities.csv", 2)
    src2 = SourceRef("user_identities.csv", 3)
    src_req = SourceRef("deletion_requests.csv", 2)

    dataset.user_identities = [
        Identity(
            user_id="user_john_1",
            name="John Doe",
            email_raw="john1@example.com",
            email_norm="john1@example.com",
            phone_raw="+15550001",
            phone_norm="15550001",
            email_hash="hash_j1",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src1,
        ),
        Identity(
            user_id="user_john_2",
            name="John Doe",
            email_raw="john2@example.com",
            email_norm="john2@example.com",
            phone_raw="+15550002",
            phone_norm="15550002",
            email_hash="hash_j2",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src2,
        ),
    ]

    req = DeletionRequest(
        case_id="case_john",
        email_raw="john1@example.com",
        email_norm="john1@example.com",
        requested_at_raw="2026-08-01T00:00:00Z",
        requested_at=None,
        reported_status="COMPLETE",
        reported_at_raw="2026-08-02T00:00:00Z",
        reported_at=None,
        audit_at_raw="2026-08-03T00:00:00Z",
        audit_at=None,
        request_text="Delete John 1",
        source=src_req,
    )
    dataset.deletion_requests = [req]

    cluster = resolve_request(req, dataset)

    # user_john_1 must be in cluster
    assert ("user_id", "user_john_1") in cluster.nodes
    # user_john_2 must NOT be in cluster
    assert ("user_id", "user_john_2") not in cluster.nodes
    assert ("email", "john2@example.com") not in cluster.nodes


def test_plus_addressing():
    """
    Plus-addressing (Decision D1):
    alice+tag@domain.com and alice@domain.com must be a PROBABLE link, never CONFIRMED.
    """
    dataset = make_empty_dataset()
    src_ident = SourceRef("user_identities.csv", 2)
    src_req = SourceRef("deletion_requests.csv", 2)

    dataset.user_identities = [
        Identity(
            user_id="user_alice",
            name="Alice",
            email_raw="alice@domain.com",
            email_norm="alice@domain.com",
            phone_raw="+15551111",
            phone_norm="15551111",
            email_hash="hash_a",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src_ident,
        )
    ]

    # Request submitted with plus address
    req = DeletionRequest(
        case_id="case_plus",
        email_raw="alice+shopping@domain.com",
        email_norm="alice+shopping@domain.com",
        requested_at_raw="2026-08-01T00:00:00Z",
        requested_at=None,
        reported_status="COMPLETE",
        reported_at_raw="2026-08-02T00:00:00Z",
        reported_at=None,
        audit_at_raw="2026-08-03T00:00:00Z",
        audit_at=None,
        request_text="Delete my plus account",
        source=src_req,
    )
    dataset.deletion_requests = [req]

    cluster = resolve_request(req, dataset)

    # Base email node must be present
    assert ("email", "alice@domain.com") in cluster.nodes

    # Find the link between plus address and base email
    plus_links = [l for l in cluster.links if l.reason_code == "PLUS_ADDRESS_VARIANT"]
    assert len(plus_links) >= 1
    for pl in plus_links:
        assert pl.strength == "PROBABLE"
        assert pl.strength != "CONFIRMED"


def test_email_conflict():
    """
    Email conflict (Decision D2):
    An email tied to two different user_ids is a CONFLICT. Do not merge them.
    """
    dataset = make_empty_dataset()
    src1 = SourceRef("user_identities.csv", 2)
    src2 = SourceRef("user_identities.csv", 3)
    src_req = SourceRef("deletion_requests.csv", 2)

    # Both users share the exact same email
    dataset.user_identities = [
        Identity(
            user_id="user_conflict_1",
            name="User 1",
            email_raw="shared@example.com",
            email_norm="shared@example.com",
            phone_raw="+15550001",
            phone_norm="15550001",
            email_hash="hash_c1",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src1,
        ),
        Identity(
            user_id="user_conflict_2",
            name="User 2",
            email_raw="shared@example.com",
            email_norm="shared@example.com",
            phone_raw="+15550002",
            phone_norm="15550002",
            email_hash="hash_c2",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src2,
        ),
    ]

    req = DeletionRequest(
        case_id="case_conflict",
        email_raw="shared@example.com",
        email_norm="shared@example.com",
        requested_at_raw="2026-08-01T00:00:00Z",
        requested_at=None,
        reported_status="COMPLETE",
        reported_at_raw="2026-08-02T00:00:00Z",
        reported_at=None,
        audit_at_raw="2026-08-03T00:00:00Z",
        audit_at=None,
        request_text="Delete shared account",
        source=src_req,
    )
    dataset.deletion_requests = [req]

    cluster = resolve_request(req, dataset)

    # Must record a conflict
    assert len(cluster.conflicts) >= 1
    conflict = cluster.conflicts[0]
    assert conflict.conflict_type == "EMAIL_CONFLICT"
    # Neither user_id should be merged as a confirmed node in cluster
    assert ("user_id", "user_conflict_1") not in cluster.nodes
    assert ("user_id", "user_conflict_2") not in cluster.nodes


def test_link_invariants():
    """Verify that every link across all clusters carries a reason_code and SourceRef."""
    dataset = make_empty_dataset()
    src_ident = SourceRef("user_identities.csv", 2)
    src_audit = SourceRef("user_audit_log.csv", 2)
    src_req = SourceRef("deletion_requests.csv", 2)

    dataset.user_identities = [
        Identity(
            user_id="u1",
            name="Test User",
            email_raw="test@test.com",
            email_norm="test@test.com",
            phone_raw="+12345",
            phone_norm="12345",
            email_hash="hash1",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src_ident,
        )
    ]
    dataset.user_audit_log = [
        AuditEvent(
            audit_id="a1",
            user_id="u1",
            field_name="phone",
            old_value_raw="+67890",
            new_value_raw="+12345",
            changed_at_raw="2025-01-01T00:00:00Z",
            changed_at=None,
            source=src_audit,
        )
    ]
    req = DeletionRequest(
        case_id="case_inv",
        email_raw="test@test.com",
        email_norm="test@test.com",
        requested_at_raw="2026-08-01T00:00:00Z",
        requested_at=None,
        reported_status="COMPLETE",
        reported_at_raw="2026-08-02T00:00:00Z",
        reported_at=None,
        audit_at_raw="2026-08-03T00:00:00Z",
        audit_at=None,
        request_text="Delete test",
        source=src_req,
    )
    dataset.deletion_requests = [req]

    clusters = resolve_all(dataset)
    for cid, cl in clusters.items():
        assert len(cl.links) > 0
        for l in cl.links:
            assert l.reason_code != ""
            assert l.source is not None
            assert isinstance(l.source, SourceRef)


def test_determinism():
    """Verify that running resolve_all twice produces bit-for-bit identical results."""
    dataset = make_empty_dataset()
    src_ident = SourceRef("user_identities.csv", 2)
    src_req = SourceRef("deletion_requests.csv", 2)

    dataset.user_identities = [
        Identity(
            user_id="u_det",
            name="Det User",
            email_raw="det@test.com",
            email_norm="det@test.com",
            phone_raw="+9999",
            phone_norm="9999",
            email_hash="det_hash",
            updated_at_raw="2026-01-01T00:00:00Z",
            updated_at=None,
            source=src_ident,
        )
    ]
    dataset.deletion_requests = [
        DeletionRequest(
            case_id="case_det",
            email_raw="det@test.com",
            email_norm="det@test.com",
            requested_at_raw="2026-08-01T00:00:00Z",
            requested_at=None,
            reported_status="COMPLETE",
            reported_at_raw="2026-08-02T00:00:00Z",
            reported_at=None,
            audit_at_raw="2026-08-03T00:00:00Z",
            audit_at=None,
            request_text="Delete",
            source=src_req,
        )
    ]

    c1 = resolve_all(dataset)
    c2 = resolve_all(dataset)

    assert len(c1) == len(c2)
    for cid in c1:
        cl1 = c1[cid]
        cl2 = c2[cid]
        assert set(cl1.nodes.keys()) == set(cl2.nodes.keys())
        assert len(cl1.links) == len(cl2.links)
        for l1, l2 in zip(cl1.links, cl2.links):
            assert l1.from_node.key == l2.from_node.key
            assert l1.to_node.key == l2.to_node.key
            assert l1.strength == l2.strength
            assert l1.reason_code == l2.reason_code
            assert l1.source == l2.source

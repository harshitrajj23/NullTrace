"""
code/tests/test_sql_join_scan.py

Unit tests for SQL schema inventory, join graph inference, path search,
and strict answer-key isolation.
"""

import os
import sqlite3
import tempfile
import pytest

from code.evaluation.sql_join_scan import (
    parse_sql_file,
    build_join_graph,
    search_join_paths,
    is_path_excluded,
    TableInfo
)


def test_synthetic_fixture_two_hop_path():
    """
    Synthetic SQL file with three tables:
    - accounts (user_id, account_id PK)
    - orders (order_id PK, account_id FK -> accounts)
    - resources (resource_id PK, order_id FK -> orders)
    Expects a two-hop path from accounts (holding user_id) to resources (holding resource_id).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sql_path = os.path.join(tmpdir, "synthetic_ecommerce.sql")
        sql_content = """
        PRAGMA foreign_keys=ON;
        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        );
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );
        CREATE TABLE resources (
            resource_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        INSERT INTO accounts VALUES ('acc_01', 'user_100');
        INSERT INTO orders VALUES ('ord_01', 'acc_01');
        INSERT INTO resources VALUES ('account_item_01', 'ord_01');
        """
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)

        table_infos = parse_sql_file(sql_path)
        assert len(table_infos) == 3

        # Prepare table_data
        table_data = {
            "accounts": {"account_id": {"acc_01"}, "user_id": {"user_100"}},
            "orders": {"order_id": {"ord_01"}, "account_id": {"acc_01"}},
            "resources": {"resource_id": {"account_item_01"}, "order_id": {"ord_01"}},
        }

        edges, components = build_join_graph(table_infos, table_data)
        assert len(edges) >= 2

        # Check declared edges (2 forward + 2 reverse navigable join edges)
        declared_edges = [e for e in edges if e.edge_type == "DECLARED"]
        assert len([e for e in declared_edges if e.rule_used == "DECLARED_FOREIGN_KEY"]) == 2
        assert len(declared_edges) == 4

        paths, cap_cut_off = search_join_paths(table_infos, edges, max_length=4)
        assert not cap_cut_off

        # Find 2-hop path: accounts -> orders -> resources
        two_hop_paths = [p for p in paths if len(p) == 2]
        assert len(two_hop_paths) == 1
        p = two_hop_paths[0]
        assert p[0].from_table == "orders" or p[0].to_table == "orders"
        assert p[1].to_table == "resources" or p[1].from_table == "resources"


def test_synthetic_fixture_inferred_edge_without_declared_fk():
    """
    Synthetic SQL file with an inferred edge where no foreign key is declared,
    flagged as INFERRED with its overlap count.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sql_path = os.path.join(tmpdir, "inferred_schema.sql")
        sql_content = """
        CREATE TABLE customer_nodes (
            customer_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL
        );
        CREATE TABLE audit_nodes (
            resource_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL
        );
        INSERT INTO customer_nodes VALUES ('c_01', 'user_01');
        INSERT INTO customer_nodes VALUES ('c_02', 'user_02');
        INSERT INTO customer_nodes VALUES ('c_03', 'user_03');

        INSERT INTO audit_nodes VALUES ('audit_01', 'c_01');
        INSERT INTO audit_nodes VALUES ('audit_02', 'c_02');
        INSERT INTO audit_nodes VALUES ('audit_03', 'c_03');
        """
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)

        table_infos = parse_sql_file(sql_path)
        table_data = {
            "customer_nodes": {"customer_id": {"c_01", "c_02", "c_03"}, "user_id": {"user_01", "user_02", "user_03"}},
            "audit_nodes": {"resource_id": {"audit_01", "audit_02", "audit_03"}, "customer_id": {"c_01", "c_02", "c_03"}},
        }

        edges, components = build_join_graph(table_infos, table_data)
        inferred = [e for e in edges if e.edge_type == "INFERRED" and e.from_table == "audit_nodes" and e.to_table == "customer_nodes"]
        assert len(inferred) == 1
        edge = inferred[0]
        assert edge.from_col == "customer_id"
        assert edge.to_col == "customer_id"
        assert edge.overlap_count == 3
        assert edge.rule_used == "EXACT_NAME_EQUALS_PK"


def test_scanner_excludes_answer_key_and_eval_paths():
    """
    Asserts strict Answer-Key Isolation:
    - sample_output.csv is excluded
    - output.csv is excluded
    - any path under code/evaluation/ or code/docs/ is excluded
    - allowed dataset files are NOT excluded
    """
    assert is_path_excluded("dataset/sample_output.csv")
    assert is_path_excluded("dataset/output.csv")
    assert is_path_excluded("output.csv")
    assert is_path_excluded("code/evaluation/sql_schema_inventory.md")
    assert is_path_excluded("code/evaluation/sql_join_report.md")
    assert is_path_excluded("code/evaluation/subject_resource_report.md")
    assert is_path_excluded("code/docs/SPEC_EXTRACTED.md")
    assert is_path_excluded("code/docs/JUDGE_NOTES.md")

    # Allowed dataset files
    assert not is_path_excluded("dataset/evidence/databases/customer_data_inventory_20260524.sql")
    assert not is_path_excluded("dataset/evidence/databases/customer_accounts_failover_replica_20260902.sql")
    assert not is_path_excluded("dataset/user_identities.csv")
    assert not is_path_excluded("dataset/user_audit_log.csv")

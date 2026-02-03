#!/usr/bin/env python3
"""Migration script to add governance fields to existing ODIN nodes in FalkorDB.

The ODIN schema was extended with classification, retention_period, access_control,
 encryption_required, data_quality_score on Table and Column, and a new Policy node type.
This script iterates over all existing Table and Column nodes and ensures the new
properties exist (with sensible defaults). It also creates a placeholder Policy
node for demonstration.
"""

import os
from src.infrastructure.falkor_backend import FalkorBackend
from src.domain.odin_models import Table, Column, Policy, PolicyType


def ensure_governance_fields(backend: FalkorBackend):
    # Update Table nodes
    tables = backend.query("MATCH (t:Table) RETURN t")
    if isinstance(tables, dict) and "nodes" in tables:
        for node in tables["nodes"]:
            props = node.get("properties", {})
            updated = {
                "classification": props.get("classification", None),
                "retention_period": props.get("retention_period", None),
                "access_control": props.get("access_control", []),
                "encryption_required": props.get("encryption_required", False),
                "data_quality_score": props.get("data_quality_score", None),
            }
            backend.add_entity(node["id"], updated)

    # Update Column nodes
    columns = backend.query("MATCH (c:Column) RETURN c")
    if isinstance(columns, dict) and "nodes" in columns:
        for node in columns["nodes"]:
            props = node.get("properties", {})
            updated = {
                "classification": props.get("classification", None),
                "retention_period": props.get("retention_period", None),
                "access_control": props.get("access_control", []),
                "encryption_required": props.get("encryption_required", False),
                "data_quality_score": props.get("data_quality_score", None),
            }
            backend.add_entity(node["id"], updated)

    # Create a sample Policy node (optional placeholder)
    sample_policy = Policy(
        policy_id="policy:sample_retention",
        name="Sample Retention Policy",
        description="Retain data for 2 years",
        policy_type=PolicyType.DATA_RETENTION,
        applies_to=[],
        properties={"retention_period": "P2Y"},
    )
    backend.add_entity(sample_policy.policy_id, sample_policy.model_dump())


def main():
    # Load environment variables for FalkorDB connection
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    backend = FalkorBackend(host=host, port=port)
    ensure_governance_fields(backend)
    print("✅ Migration completed: governance fields added to existing nodes.")


if __name__ == "__main__":
    main()

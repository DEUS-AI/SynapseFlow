#!/usr/bin/env python3
"""Generate a compliance data‑map from the ODIN graph.

This script:
1. Connects to FalkorDB and pulls all Table, Column, and Policy nodes.
2. Runs the governance engine to collect any policy violations.
3. Builds a Pandas DataFrame with governance fields, linked policies, and a violation flag.
4. Exports CSV, Excel, and an HTML report (violations highlighted).

Usage:
    uv run python scripts/generate_data_map.py
"""

import asyncio
import os
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from src.infrastructure.falkor_backend import FalkorBackend
from src.services.governance_engine import load_rules, run_governance_checks


async def fetch_nodes(backend: FalkorBackend, label: str):
    """Return a list of node dicts for the given label."""
    result = await backend.query(f"MATCH (n:{label}) RETURN n")
    if isinstance(result, dict) and "nodes" in result:
        return result["nodes"]
    return []


def build_dataframe(tables, columns, policies, violations):
    rows = []
    # Helper to collect policy IDs that apply to a node
    def policies_for(node_id):
        ids = []
        for p in policies:
            applies = p.get("properties", {}).get("applies_to", [])
            if node_id in applies:
                ids.append(p.get("id"))
        return ",".join(ids)

    for t in tables:
        props = t.get("properties", {})
        rows.append({
            "entity_type": "Table",
            "entity_id": t.get("id"),
            "name": props.get("name"),
            "classification": props.get("classification"),
            "retention": props.get("retention_period"),
            "encryption": props.get("encryption_required"),
            "quality": props.get("data_quality_score"),
            "policies": policies_for(t.get("id")),
            "violation": any(v["node_id"] == t.get("id") for v in violations),
        })
    for c in columns:
        props = c.get("properties", {})
        rows.append({
            "entity_type": "Column",
            "entity_id": c.get("id"),
            "name": props.get("name"),
            "classification": props.get("classification"),
            "retention": props.get("retention_period"),
            "encryption": props.get("encryption_required"),
            "quality": props.get("data_quality_score"),
            "policies": policies_for(c.get("id")),
            "violation": any(v["node_id"] == c.get("id") for v in violations),
        })
    return pd.DataFrame(rows)


def render_html(df: pd.DataFrame, out_path: str):
    env = Environment(loader=FileSystemLoader(searchpath=os.path.dirname(__file__)))
    template = env.from_string("""
<!doctype html>
<html><head><title>ODIN Data‑Map</title>
<style>
  table {border-collapse: collapse; width: 100%;}
  th, td {border: 1px solid #ddd; padding: 8px;}
  tr.violation {background-color: #ffe6e6;}
</style>
</head><body>
<h1>ODIN Data‑Map</h1>
{{ table|safe }}
</body></html>
""")
    # Mark rows with violations for CSS class
    def row_class(row):
        return "violation" if row["violation"] else ""
    df_html = df.to_html(index=False, classes="", border=0, escape=False)
    # Simple replacement to add class to <tr> tags
    df_html = df_html.replace("<tr>", "<tr class='" + "{{row_class}}" + "'>")
    html = template.render(table=df_html)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


async def main():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    backend = FalkorBackend(host=host, port=port)

    tables = await fetch_nodes(backend, "table")
    columns = await fetch_nodes(backend, "column")
    policies = await fetch_nodes(backend, "policy")

    # Run governance checks
    rules = load_rules()
    violations = await run_governance_checks(backend, rules)

    df = build_dataframe(tables, columns, policies, violations)

    # Export files
    df.to_csv("data_map.csv", index=False)
    df.to_excel("data_map.xlsx", index=False)
    render_html(df, "data_map.html")

    print("✅ Data‑map generated: data_map.csv, data_map.xlsx, data_map.html")
    if violations:
        print(f"⚠️ {len(violations)} governance violations detected.")
    else:
        print("✅ No governance violations found.")

if __name__ == "__main__":
    asyncio.run(main())

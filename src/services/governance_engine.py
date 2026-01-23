#!/usr/bin/env python3
"""Governance engine wrapper.

Loads policy rules from a YAML file (scripts/rules.yaml) and evaluates them against
ODIN nodes stored in FalkorDB. Returns a list of violation dictionaries.

The rule format (YAML) is simple:

- name: "PII Encryption Required"
  description: "Columns classified as PII must have encryption_required=True"
  target: "Column"  # Node type to evaluate
  condition: "node.get('classification') == 'PII' and not node.get('encryption_required')"
  violation_message: "PII column without encryption"

The engine loads all nodes of the specified type, evaluates the Python expression
in a safe sandbox, and records any violations.
"""

import os
import yaml
from typing import List, Dict, Any
from infrastructure.falkor_backend import FalkorBackend

# Path to the rules file – can be overridden via env var
RULES_PATH = os.getenv("RULES_PATH", "scripts/rules.yaml")


def load_rules(path: str = RULES_PATH) -> List[Dict[str, Any]]:
    """Load governance rules from a YAML file.

    Returns a list of rule dictionaries.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Rules file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or []


import asyncio

def evaluate_node(node: Dict[str, Any], condition: str) -> bool:
    """Safely evaluate a condition expression against a node.

    The expression can reference the variable ``node`` which is a dict of the
    node's properties. Only a restricted set of built‑ins is allowed.
    """
    safe_globals = {
        "__builtins__": {},
    }
    try:
        return bool(eval(condition, safe_globals, {"node": node.get("properties", {})}))
    except Exception as e:
        # If the condition crashes, treat it as non‑matching and log.
        print(f"⚠️ Condition evaluation error: {e}")
        return False


async def run_governance_checks(backend: FalkorBackend, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run all rules against the graph and collect violations.

    Returns a list of dicts:
    {
        "rule": <rule name>,
        "node_id": <node id>,
        "node_type": <type>,
        "message": <violation_message>
    }
    """
    violations: List[Dict[str, Any]] = []
    for rule in rules:
        target_type = rule.get("target")
        condition = rule.get("condition")
        message = rule.get("violation_message", "Policy violation")
        if not target_type or not condition:
            continue
        # Query all nodes of the target type
        query = f"MATCH (n:{target_type}) RETURN n"
        result = await backend.query(query)
        if not isinstance(result, dict) or "nodes" not in result:
            continue
        for node in result["nodes"]:
            if evaluate_node(node, condition):
                violations.append({
                    "rule": rule.get("name", "Unnamed rule"),
                    "node_id": node.get("id"),
                    "node_type": target_type,
                    "message": message,
                })
    return violations


async def main():
    # Initialise FalkorDB backend from env vars
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    backend = FalkorBackend(host=host, port=port)

    rules = load_rules()
    violations = await run_governance_checks(backend, rules)
    if violations:
        print("⚠️ Governance violations detected:")
        for v in violations:
            print(f"- [{v['node_type']}] {v['node_id']}: {v['rule']} – {v['message']}")
    else:
        print("✅ No governance violations found.")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Metadata enrichment service.

Reads a DDA markdown file, extracts semantic tags using a LLM (Graphiti/OpenAI) or simple heuristics,
and returns a dictionary that can be merged into ODIN nodes.

Usage:
    python -m src.services.metadata_enrichment <path/to/dda.md>
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List

# Attempt to import Graphiti if available; otherwise fall back to heuristic parser
try:
    from graphiti_core import Graphiti  # type: ignore
    _graphiti_available = True
except Exception:
    _graphiti_available = False

# Simple heuristic keywords for demonstration
PII_KEYWORDS = [
    "email", "phone", "address", "date of birth", "ssn", "social security", "patient id",
]

def _heuristic_tags(text: str) -> List[str]:
    tags = []
    lowered = text.lower()
    for kw in PII_KEYWORDS:
        if kw in lowered:
            tags.append("PII")
            break
    # Add generic domain tags based on common words
    if "patient" in lowered:
        tags.append("HEALTH")
    if "customer" in lowered:
        tags.append("CUSTOMER")
    return tags

def enrich_metadata(dda_path: str) -> Dict[str, List[str]]:
    """Extract semantic tags from a DDA file.

    Returns a dict mapping entity names (or "global") to a list of tags.
    """
    path = Path(dda_path)
    if not path.is_file():
        raise FileNotFoundError(f"DDA file not found: {dda_path}")

    content = path.read_text(encoding="utf-8")

    if _graphiti_available:
        # Use Graphiti LLM to infer tags – placeholder implementation
        # In a real system you would call Graphiti's inference API.
        # Here we simulate by returning an empty list.
        return {"global": []}
    else:
        tags = _heuristic_tags(content)
        return {"global": tags}

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m src.services.metadata_enrichment <dda_path>")
        sys.exit(1)
    dda_path = sys.argv[1]
    tags = enrich_metadata(dda_path)
    print(json.dumps(tags, indent=2))

if __name__ == "__main__":
    main()

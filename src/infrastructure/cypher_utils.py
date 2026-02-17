"""Utilities for safe Cypher query construction.

Provides validation functions to prevent Cypher injection when
dynamic identifiers (relationship types, labels) must be interpolated
into query strings. Neo4j does not support parameterization for
relationship types or labels, so input validation is required.
"""

import re

# Valid Cypher identifier: starts with letter or underscore, then alphanumeric/underscore
_CYPHER_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Cypher reserved words that should not be used as identifiers
_CYPHER_RESERVED_WORDS = frozenset({
    "MATCH", "WHERE", "RETURN", "CREATE", "DELETE", "DETACH", "SET",
    "REMOVE", "MERGE", "WITH", "UNWIND", "CALL", "YIELD", "DROP",
    "ORDER", "SKIP", "LIMIT", "UNION", "OPTIONAL", "EXISTS", "CASE",
    "WHEN", "THEN", "ELSE", "END", "AND", "OR", "NOT", "IN", "AS",
    "NULL", "TRUE", "FALSE", "IS", "STARTS", "ENDS", "CONTAINS",
    "FOREACH", "LOAD", "CSV", "INDEX", "CONSTRAINT", "ASSERT",
})


def validate_cypher_identifier(value: str, label: str = "identifier") -> str:
    """Validate that a string is safe to use as a Cypher identifier.

    Neo4j does not support parameterized relationship types or labels,
    so this function validates the input before string interpolation.

    Args:
        value: The string to validate.
        label: Descriptive label for error messages (e.g., "relationship_type").

    Returns:
        The validated string (unchanged).

    Raises:
        ValueError: If the value is empty, contains invalid characters,
            or is a reserved Cypher keyword.
    """
    if not value:
        raise ValueError(f"Cypher {label} must not be empty")

    if not _CYPHER_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid Cypher {label}: {value!r}. "
            f"Must match pattern [A-Za-z_][A-Za-z0-9_]*"
        )

    if value.upper() in _CYPHER_RESERVED_WORDS:
        raise ValueError(
            f"Cypher {label} must not be a reserved keyword: {value!r}"
        )

    return value

"""Startup validation for required environment variables.

Import this module early in application bootstrap to fail fast
if required configuration is missing.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    "NEO4J_URI",
    "NEO4J_PASSWORD",
    "OPENAI_API_KEY",
]

OPTIONAL_VARS = [
    "REDIS_HOST",
    "QDRANT_URL",
    "FALKORDB_HOST",
]


def validate_config() -> None:
    """Validate that all required environment variables are set.

    Exits the process with a clear error if any required variables
    are missing or empty. Logs warnings for missing optional variables.
    """
    missing = [var for var in REQUIRED_VARS if not os.environ.get(var)]

    if missing:
        print(
            f"FATAL: Missing required environment variables: {', '.join(missing)}\n"
            f"Set them in your .env file or environment. See .env.example for reference.",
            file=sys.stderr,
        )
        sys.exit(1)

    for var in OPTIONAL_VARS:
        if not os.environ.get(var):
            logger.warning("Optional environment variable %s is not set", var)

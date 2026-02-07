"""Database Infrastructure Module.

Provides PostgreSQL connectivity using SQLAlchemy with async support.
"""

from .config import DatabaseConfig, get_database_url
from .session import get_db_session, init_database, close_database
from .models import (
    Base,
    Session,
    Message,
    Feedback,
    Document,
    DocumentQuality,
    OntologyQuality,
    AuditLog,
    QueryAnalytics,
    FeatureFlag,
)

__all__ = [
    "DatabaseConfig",
    "get_database_url",
    "get_db_session",
    "init_database",
    "close_database",
    "Base",
    "Session",
    "Message",
    "Feedback",
    "Document",
    "DocumentQuality",
    "OntologyQuality",
    "AuditLog",
    "QueryAnalytics",
    "FeatureFlag",
]

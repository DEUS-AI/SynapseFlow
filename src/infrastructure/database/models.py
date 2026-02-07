"""SQLAlchemy Models for PostgreSQL.

Defines ORM models for relational data:
- Sessions & Messages (Chat History)
- Feedback & RLHF Data
- Documents & Quality Metrics
- Audit Logs
- Query Analytics
- Feature Flags
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ============================================
# Sessions & Messages
# ============================================

class Session(Base):
    """Chat session with a patient."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500))
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    message_count = Column(Integer, default=0)
    extra_data = Column("metadata", JSONB, default=dict)  # 'metadata' is reserved in SQLAlchemy

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    feedback_items = relationship("Feedback", back_populates="session")

    __table_args__ = (
        Index("idx_sessions_patient_activity", "patient_id", "last_activity"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "patient_id": self.patient_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "message_count": self.message_count,
            "metadata": self.extra_data,
        }


class Message(Base):
    """Chat message within a session."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    response_id = Column(String(255), index=True)  # For feedback attribution
    extra_data = Column("metadata", JSONB, default=dict)  # 'metadata' is reserved in SQLAlchemy
    patient_id = Column(String(255), nullable=False, index=True)  # Denormalized

    # Relationships
    session = relationship("Session", back_populates="messages")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "response_id": self.response_id,
            "metadata": self.extra_data,
        }


# ============================================
# Feedback & RLHF Data
# ============================================

class Feedback(Base):
    """User feedback for RLHF training."""

    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    response_id = Column(String(255), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"))
    patient_id = Column(String(255))

    # Feedback data
    rating = Column(Integer)
    thumbs_up = Column(Boolean)
    feedback_type = Column(String(50), index=True)
    correction_text = Column(Text)
    severity = Column(String(20))

    # Context
    query_text = Column(Text)
    response_text = Column(Text)
    entities_involved = Column(JSONB, default=list)
    layers_traversed = Column(JSONB, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Training data flags
    used_for_training = Column(Boolean, default=False, index=True)
    training_batch_id = Column(String(255))

    # Relationships
    session = relationship("Session", back_populates="feedback_items")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "response_id": self.response_id,
            "session_id": str(self.session_id) if self.session_id else None,
            "rating": self.rating,
            "thumbs_up": self.thumbs_up,
            "feedback_type": self.feedback_type,
            "correction_text": self.correction_text,
            "severity": self.severity,
            "query_text": self.query_text,
            "response_text": self.response_text,
            "entities_involved": self.entities_involved,
            "layers_traversed": self.layers_traversed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "used_for_training": self.used_for_training,
        }


# ============================================
# Documents & Quality Metrics
# ============================================

class Document(Base):
    """Document metadata and ingestion status."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id = Column(String(255), unique=True, index=True)
    filename = Column(String(500), nullable=False)
    source_path = Column(Text)
    category = Column(String(100), index=True)

    # Status
    status = Column(String(50), default="pending", index=True)
    error_message = Column(Text)

    # Metrics
    size_bytes = Column(BigInteger)
    chunk_count = Column(Integer, default=0)
    entity_count = Column(Integer, default=0)
    relationship_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ingested_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Paths
    markdown_path = Column(Text)

    # Metadata
    extra_data = Column("metadata", JSONB, default=dict)  # 'metadata' is reserved in SQLAlchemy

    # Relationships
    quality_reports = relationship("DocumentQuality", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "external_id": self.external_id,
            "filename": self.filename,
            "source_path": self.source_path,
            "category": self.category,
            "status": self.status,
            "error_message": self.error_message,
            "size_bytes": self.size_bytes,
            "chunk_count": self.chunk_count,
            "entity_count": self.entity_count,
            "relationship_count": self.relationship_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "markdown_path": self.markdown_path,
        }


class DocumentQuality(Base):
    """Document quality assessment results."""

    __tablename__ = "document_quality"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    # Overall
    overall_score = Column(Numeric(5, 4))
    quality_level = Column(String(20), index=True)

    # Contextual Relevancy
    context_precision = Column(Numeric(5, 4))
    context_recall = Column(Numeric(5, 4))
    context_f1 = Column(Numeric(5, 4))

    # Sufficiency
    topic_coverage = Column(Numeric(5, 4))
    completeness = Column(Numeric(5, 4))

    # Density
    facts_per_chunk = Column(Numeric(8, 4))
    redundancy_ratio = Column(Numeric(5, 4))
    signal_to_noise = Column(Numeric(5, 4))

    # Structure
    heading_hierarchy_score = Column(Numeric(5, 4))
    section_coherence = Column(Numeric(5, 4))

    # Entity
    entity_extraction_rate = Column(Numeric(5, 4))
    entity_consistency = Column(Numeric(5, 4))

    # Chunking
    boundary_coherence = Column(Numeric(5, 4))
    retrieval_quality = Column(Numeric(5, 4))

    # Recommendations
    recommendations = Column(JSONB, default=list)

    # Timestamps
    assessed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="quality_reports")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "quality_level": self.quality_level,
            "context_precision": float(self.context_precision) if self.context_precision else None,
            "context_recall": float(self.context_recall) if self.context_recall else None,
            "context_f1": float(self.context_f1) if self.context_f1 else None,
            "topic_coverage": float(self.topic_coverage) if self.topic_coverage else None,
            "completeness": float(self.completeness) if self.completeness else None,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
            "recommendations": self.recommendations,
        }


# ============================================
# Ontology Quality
# ============================================

class OntologyQuality(Base):
    """Ontology quality assessment results."""

    __tablename__ = "ontology_quality"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assessment_id = Column(String(50), nullable=False)
    ontology_name = Column(String(100), nullable=False, index=True)

    # Overall
    overall_score = Column(Numeric(5, 4))
    quality_level = Column(String(20))

    # Coverage
    coverage_ratio = Column(Numeric(5, 4))
    odin_coverage = Column(Numeric(5, 4))
    schema_org_coverage = Column(Numeric(5, 4))

    # Compliance
    compliance_ratio = Column(Numeric(5, 4))
    fully_compliant = Column(Integer)
    non_compliant = Column(Integer)

    # Taxonomy
    coherence_ratio = Column(Numeric(5, 4))
    orphan_nodes = Column(Integer)

    # Consistency
    consistency_ratio = Column(Numeric(5, 4))

    # Metadata
    entity_count = Column(Integer)
    relationship_count = Column(Integer)

    # Issues
    critical_issues = Column(JSONB, default=list)
    recommendations = Column(JSONB, default=list)

    # Timestamps
    assessed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ============================================
# Audit Logs
# ============================================

class AuditLog(Base):
    """Audit trail for important system events."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Event info
    event_type = Column(String(100), nullable=False, index=True)
    event_source = Column(String(100))

    # Entity info
    entity_id = Column(String(255), index=True)
    entity_type = Column(String(100))

    # Change details
    action = Column(String(50), nullable=False, index=True)
    old_values = Column(JSONB)
    new_values = Column(JSONB)

    # Context
    user_id = Column(String(255))
    session_id = Column(UUID(as_uuid=True))
    agent_name = Column(String(100))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "event_source": self.event_source,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "action": self.action,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "user_id": self.user_id,
            "session_id": str(self.session_id) if self.session_id else None,
            "agent_name": self.agent_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================
# Query Analytics
# ============================================

class QueryAnalytics(Base):
    """Query pattern analytics for optimization."""

    __tablename__ = "query_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Query info
    query_hash = Column(String(64), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), index=True)

    # Execution stats
    execution_count = Column(Integer, default=1, index=True)
    total_execution_time_ms = Column(BigInteger, default=0)
    avg_execution_time_ms = Column(Numeric(10, 2))

    # Layer usage
    layers_used = Column(JSONB, default=list)
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)

    # Quality
    avg_confidence = Column(Numeric(5, 4))
    feedback_score = Column(Numeric(5, 4))

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ============================================
# Feature Flags
# ============================================

class FeatureFlag(Base):
    """Feature flags for migration control."""

    __tablename__ = "feature_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    description = Column(Text)

    # Rollout control
    rollout_percentage = Column(Integer, default=0)

    # Metadata
    extra_data = Column("metadata", JSONB, default=dict)  # 'metadata' is reserved in SQLAlchemy

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "rollout_percentage >= 0 AND rollout_percentage <= 100",
            name="check_rollout_percentage"
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "enabled": self.enabled,
            "description": self.description,
            "rollout_percentage": self.rollout_percentage,
            "metadata": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

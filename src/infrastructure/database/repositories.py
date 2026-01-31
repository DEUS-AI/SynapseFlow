"""PostgreSQL Repositories.

Repository pattern for database operations, providing a clean abstraction
over SQLAlchemy for CRUD operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, TypeVar, Generic
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

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

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """Delete an entity."""
        await self.session.delete(entity)

    async def delete_by_id(self, id: UUID) -> bool:
        """Delete entity by ID."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0

    async def count(self) -> int:
        """Count all entities."""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar() or 0


class SessionRepository(BaseRepository[Session]):
    """Repository for chat sessions."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Session)

    async def get_by_patient(
        self,
        patient_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Session]:
        """Get sessions for a patient."""
        query = select(Session).where(Session.patient_id == patient_id)

        if status:
            query = query.where(Session.status == status)

        query = query.order_by(Session.last_activity.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_session(self, patient_id: str) -> Optional[Session]:
        """Get the most recent active session for a patient."""
        result = await self.session.execute(
            select(Session)
            .where(and_(
                Session.patient_id == patient_id,
                Session.status == "active"
            ))
            .order_by(Session.last_activity.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_sessions_grouped_by_time(
        self,
        patient_id: str,
        limit: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get sessions grouped by time period (today, yesterday, this week, older)."""
        sessions = await self.get_by_patient(patient_id, limit=limit)

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)

        grouped = {
            "today": [],
            "yesterday": [],
            "this_week": [],
            "older": [],
        }

        for s in sessions:
            session_dict = s.to_dict()
            if s.last_activity >= today_start:
                grouped["today"].append(session_dict)
            elif s.last_activity >= yesterday_start:
                grouped["yesterday"].append(session_dict)
            elif s.last_activity >= week_start:
                grouped["this_week"].append(session_dict)
            else:
                grouped["older"].append(session_dict)

        return grouped

    async def update_activity(self, session_id: UUID) -> None:
        """Update session's last activity timestamp."""
        await self.session.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(last_activity=datetime.now())
        )

    async def increment_message_count(self, session_id: UUID) -> None:
        """Increment session's message count."""
        await self.session.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                message_count=Session.message_count + 1,
                last_activity=datetime.now()
            )
        )


class MessageRepository(BaseRepository[Message]):
    """Repository for chat messages."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)

    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """Get messages for a session."""
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_response_id(self, response_id: str) -> Optional[Message]:
        """Get message by response ID (for feedback attribution)."""
        result = await self.session.execute(
            select(Message).where(Message.response_id == response_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_by_patient(
        self,
        patient_id: str,
        limit: int = 10,
    ) -> List[Message]:
        """Get recent messages for a patient across all sessions."""
        result = await self.session.execute(
            select(Message)
            .where(Message.patient_id == patient_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class FeedbackRepository(BaseRepository[Feedback]):
    """Repository for user feedback."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Feedback)

    async def get_by_response_id(self, response_id: str) -> Optional[Feedback]:
        """Get feedback for a specific response."""
        result = await self.session.execute(
            select(Feedback).where(Feedback.response_id == response_id)
        )
        return result.scalar_one_or_none()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        # Total counts
        total = await self.count()

        # Positive/negative counts
        positive_result = await self.session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.thumbs_up == True)
        )
        positive = positive_result.scalar() or 0

        negative_result = await self.session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.thumbs_up == False)
        )
        negative = negative_result.scalar() or 0

        # Corrections count
        corrections_result = await self.session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.correction_text.isnot(None))
        )
        corrections = corrections_result.scalar() or 0

        # Average rating
        avg_rating_result = await self.session.execute(
            select(func.avg(Feedback.rating)).where(Feedback.rating.isnot(None))
        )
        avg_rating = avg_rating_result.scalar() or 0

        return {
            "total_feedback": total,
            "positive_count": positive,
            "negative_count": negative,
            "correction_count": corrections,
            "avg_rating": float(avg_rating) if avg_rating else None,
        }

    async def get_preference_pairs(
        self,
        min_rating_gap: int = 2,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get preference pairs for DPO training."""
        # Get feedback with ratings
        result = await self.session.execute(
            select(Feedback)
            .where(and_(
                Feedback.rating.isnot(None),
                Feedback.query_text.isnot(None),
                Feedback.response_text.isnot(None)
            ))
            .order_by(Feedback.created_at.desc())
            .limit(limit * 2)  # Get more to find pairs
        )
        all_feedback = list(result.scalars().all())

        # Group by similar queries and find pairs
        pairs = []
        # Simplified: just return high/low rated examples
        high_rated = [f for f in all_feedback if f.rating and f.rating >= 4]
        low_rated = [f for f in all_feedback if f.rating and f.rating <= 2]

        for high in high_rated[:limit]:
            for low in low_rated:
                if high.rating - low.rating >= min_rating_gap:
                    pairs.append({
                        "prompt": high.query_text,
                        "chosen": high.response_text,
                        "rejected": low.response_text,
                        "chosen_rating": high.rating,
                        "rejected_rating": low.rating,
                    })
                    break  # One pair per high-rated

        return pairs[:limit]

    async def get_for_training(
        self,
        limit: int = 500,
    ) -> List[Feedback]:
        """Get feedback not yet used for training."""
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.used_for_training == False)
            .order_by(Feedback.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_as_trained(self, feedback_ids: List[UUID], batch_id: str) -> int:
        """Mark feedback as used for training."""
        result = await self.session.execute(
            update(Feedback)
            .where(Feedback.id.in_(feedback_ids))
            .values(used_for_training=True, training_batch_id=batch_id)
        )
        return result.rowcount


class DocumentRepository(BaseRepository[Document]):
    """Repository for documents."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Document)

    async def get_by_external_id(self, external_id: str) -> Optional[Document]:
        """Get document by external ID."""
        result = await self.session.execute(
            select(Document).where(Document.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> List[Document]:
        """Get documents by status."""
        result = await self.session.execute(
            select(Document)
            .where(Document.status == status)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics."""
        total = await self.count()

        # Status counts
        status_result = await self.session.execute(
            select(Document.status, func.count())
            .group_by(Document.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}

        # Category counts
        category_result = await self.session.execute(
            select(Document.category, func.count())
            .where(Document.category.isnot(None))
            .group_by(Document.category)
        )
        category_counts = {row[0]: row[1] for row in category_result.all()}

        return {
            "total_documents": total,
            "by_status": status_counts,
            "by_category": category_counts,
        }


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    """Repository for feature flags."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, FeatureFlag)

    async def get_by_name(self, name: str) -> Optional[FeatureFlag]:
        """Get feature flag by name."""
        result = await self.session.execute(
            select(FeatureFlag).where(FeatureFlag.name == name)
        )
        return result.scalar_one_or_none()

    async def is_enabled(self, name: str) -> bool:
        """Check if a feature flag is enabled."""
        flag = await self.get_by_name(name)
        return flag.enabled if flag else False

    async def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a feature flag."""
        result = await self.session.execute(
            update(FeatureFlag)
            .where(FeatureFlag.name == name)
            .values(enabled=enabled)
        )
        return result.rowcount > 0

    async def get_all_flags(self) -> Dict[str, bool]:
        """Get all feature flags as a dictionary."""
        result = await self.session.execute(select(FeatureFlag))
        flags = result.scalars().all()
        return {f.name: f.enabled for f in flags}


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for audit logs."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditLog)

    async def log_event(
        self,
        event_type: str,
        action: str,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        event_source: str = "system",
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> AuditLog:
        """Log an audit event."""
        log = AuditLog(
            event_type=event_type,
            action=action,
            entity_id=entity_id,
            entity_type=entity_type,
            old_values=old_values,
            new_values=new_values,
            event_source=event_source,
            user_id=user_id,
            agent_name=agent_name,
        )
        return await self.create(log)

    async def get_by_entity(
        self,
        entity_id: str,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get audit logs for an entity."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent audit logs."""
        query = select(AuditLog)

        if event_type:
            query = query.where(AuditLog.event_type == event_type)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class DocumentQualityRepository(BaseRepository[DocumentQuality]):
    """Repository for document quality assessments."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, DocumentQuality)

    async def get_by_document(
        self,
        document_id: UUID,
        limit: int = 10,
    ) -> List[DocumentQuality]:
        """Get quality assessments for a document (most recent first)."""
        result = await self.session.execute(
            select(DocumentQuality)
            .where(DocumentQuality.document_id == document_id)
            .order_by(DocumentQuality.assessed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_by_document(self, document_id: UUID) -> Optional[DocumentQuality]:
        """Get the most recent quality assessment for a document."""
        result = await self.session.execute(
            select(DocumentQuality)
            .where(DocumentQuality.document_id == document_id)
            .order_by(DocumentQuality.assessed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_latest(self, limit: int = 100) -> List[DocumentQuality]:
        """Get the latest quality assessment for each document."""
        # Subquery to get max assessed_at per document
        subquery = (
            select(
                DocumentQuality.document_id,
                func.max(DocumentQuality.assessed_at).label("max_assessed")
            )
            .group_by(DocumentQuality.document_id)
            .subquery()
        )

        result = await self.session.execute(
            select(DocumentQuality)
            .join(
                subquery,
                and_(
                    DocumentQuality.document_id == subquery.c.document_id,
                    DocumentQuality.assessed_at == subquery.c.max_assessed
                )
            )
            .order_by(DocumentQuality.assessed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_quality_level(
        self,
        quality_level: str,
        limit: int = 100,
    ) -> List[DocumentQuality]:
        """Get documents by quality level (EXCELLENT, GOOD, ACCEPTABLE, POOR, CRITICAL)."""
        result = await self.session.execute(
            select(DocumentQuality)
            .where(DocumentQuality.quality_level == quality_level)
            .order_by(DocumentQuality.assessed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_statistics(self) -> Dict[str, Any]:
        """Get quality statistics across all documents."""
        # Count by quality level
        level_result = await self.session.execute(
            select(DocumentQuality.quality_level, func.count())
            .group_by(DocumentQuality.quality_level)
        )
        level_counts = {row[0]: row[1] for row in level_result.all() if row[0]}

        # Average scores
        avg_result = await self.session.execute(
            select(
                func.avg(DocumentQuality.overall_score),
                func.avg(DocumentQuality.context_precision),
                func.avg(DocumentQuality.context_recall),
                func.avg(DocumentQuality.topic_coverage),
                func.avg(DocumentQuality.signal_to_noise),
                func.avg(DocumentQuality.entity_extraction_rate),
                func.avg(DocumentQuality.retrieval_quality),
            )
        )
        avg_row = avg_result.first()

        # Total assessed documents
        total_result = await self.session.execute(
            select(func.count(func.distinct(DocumentQuality.document_id)))
        )
        total_assessed = total_result.scalar() or 0

        return {
            "total_assessed": total_assessed,
            "by_quality_level": level_counts,
            "averages": {
                "overall_score": float(avg_row[0]) if avg_row and avg_row[0] else 0,
                "context_precision": float(avg_row[1]) if avg_row and avg_row[1] else 0,
                "context_recall": float(avg_row[2]) if avg_row and avg_row[2] else 0,
                "topic_coverage": float(avg_row[3]) if avg_row and avg_row[3] else 0,
                "signal_to_noise": float(avg_row[4]) if avg_row and avg_row[4] else 0,
                "entity_extraction_rate": float(avg_row[5]) if avg_row and avg_row[5] else 0,
                "retrieval_quality": float(avg_row[6]) if avg_row and avg_row[6] else 0,
            },
        }

    async def get_documents_needing_assessment(
        self,
        limit: int = 50,
    ) -> List[UUID]:
        """Get document IDs that haven't been assessed yet."""
        # Get documents with 'completed' status that have no quality assessment
        result = await self.session.execute(
            select(Document.id)
            .outerjoin(DocumentQuality, Document.id == DocumentQuality.document_id)
            .where(
                and_(
                    Document.status == "completed",
                    DocumentQuality.id.is_(None)
                )
            )
            .limit(limit)
        )
        return [row[0] for row in result.all()]


class OntologyQualityRepository(BaseRepository[OntologyQuality]):
    """Repository for ontology quality assessments."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OntologyQuality)

    async def get_by_ontology(
        self,
        ontology_name: str,
        limit: int = 10,
    ) -> List[OntologyQuality]:
        """Get quality assessments for an ontology (most recent first)."""
        result = await self.session.execute(
            select(OntologyQuality)
            .where(OntologyQuality.ontology_name == ontology_name)
            .order_by(OntologyQuality.assessed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest(self, ontology_name: str = "default") -> Optional[OntologyQuality]:
        """Get the most recent quality assessment for an ontology."""
        result = await self.session.execute(
            select(OntologyQuality)
            .where(OntologyQuality.ontology_name == ontology_name)
            .order_by(OntologyQuality.assessed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        ontology_name: str = "default",
        days: int = 30,
        limit: int = 100,
    ) -> List[OntologyQuality]:
        """Get quality assessment history for trend analysis."""
        cutoff = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(OntologyQuality)
            .where(
                and_(
                    OntologyQuality.ontology_name == ontology_name,
                    OntologyQuality.assessed_at >= cutoff
                )
            )
            .order_by(OntologyQuality.assessed_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_statistics(self) -> Dict[str, Any]:
        """Get ontology quality statistics."""
        # Get latest assessment
        latest = await self.get_latest()

        if not latest:
            return {
                "has_assessment": False,
                "latest": None,
            }

        # Count by quality level across all assessments
        level_result = await self.session.execute(
            select(OntologyQuality.quality_level, func.count())
            .group_by(OntologyQuality.quality_level)
        )
        level_counts = {row[0]: row[1] for row in level_result.all() if row[0]}

        # Total assessments
        total = await self.count()

        return {
            "has_assessment": True,
            "total_assessments": total,
            "latest": {
                "assessment_id": latest.assessment_id,
                "overall_score": float(latest.overall_score) if latest.overall_score else 0,
                "quality_level": latest.quality_level,
                "coverage_ratio": float(latest.coverage_ratio) if latest.coverage_ratio else 0,
                "compliance_ratio": float(latest.compliance_ratio) if latest.compliance_ratio else 0,
                "coherence_ratio": float(latest.coherence_ratio) if latest.coherence_ratio else 0,
                "consistency_ratio": float(latest.consistency_ratio) if latest.consistency_ratio else 0,
                "entity_count": latest.entity_count,
                "relationship_count": latest.relationship_count,
                "orphan_nodes": latest.orphan_nodes,
                "critical_issues": latest.critical_issues or [],
                "recommendations": latest.recommendations or [],
                "assessed_at": latest.assessed_at.isoformat() if latest.assessed_at else None,
            },
            "by_quality_level": level_counts,
        }

    async def save_assessment(
        self,
        assessment_id: str,
        ontology_name: str,
        overall_score: float,
        quality_level: str,
        coverage_ratio: float,
        odin_coverage: float,
        schema_org_coverage: float,
        compliance_ratio: float,
        fully_compliant: int,
        non_compliant: int,
        coherence_ratio: float,
        orphan_nodes: int,
        consistency_ratio: float,
        entity_count: int,
        relationship_count: int,
        critical_issues: List[str],
        recommendations: List[str],
    ) -> OntologyQuality:
        """Save a new ontology quality assessment."""
        assessment = OntologyQuality(
            assessment_id=assessment_id,
            ontology_name=ontology_name,
            overall_score=overall_score,
            quality_level=quality_level,
            coverage_ratio=coverage_ratio,
            odin_coverage=odin_coverage,
            schema_org_coverage=schema_org_coverage,
            compliance_ratio=compliance_ratio,
            fully_compliant=fully_compliant,
            non_compliant=non_compliant,
            coherence_ratio=coherence_ratio,
            orphan_nodes=orphan_nodes,
            consistency_ratio=consistency_ratio,
            entity_count=entity_count,
            relationship_count=relationship_count,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )
        return await self.create(assessment)

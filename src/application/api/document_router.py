"""Document Management API Router.

Provides endpoints for managing PDF documents and their ingestion.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks
from pathlib import Path
from typing import List, Optional
import asyncio
import uuid
import os
from datetime import datetime
import logging

from application.services.document_tracker import DocumentTracker
from application.services.document_quality_service import DocumentQualityService, quick_quality_check
from domain.quality_models import QualityLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/documents", tags=["Document Management"])

# Configuration
PDF_DIRECTORY = Path("PDFs")
MARKDOWN_DIRECTORY = Path("markdown_output")
TRACKING_FILE = Path("data/document_tracking.json")

# Global instances — legacy tracker kept as fallback until full migration
document_tracker = DocumentTracker(
    tracking_file=TRACKING_FILE,
    pdf_directory=PDF_DIRECTORY,
    markdown_directory=MARKDOWN_DIRECTORY
)

# PostgreSQL session factory (set during app startup)
_db_session_factory = None

# Document storage backend (set during app startup)
_document_storage = None


def configure_postgres(db_session_factory):
    """Configure PostgreSQL access for the document router."""
    global _db_session_factory
    _db_session_factory = db_session_factory
    logger.info("Document router configured with PostgreSQL support")


def configure_storage(storage):
    """Configure document storage backend for the document router."""
    global _document_storage
    _document_storage = storage
    logger.info(f"Document router configured with {type(storage).__name__}")


def _has_postgres() -> bool:
    return _db_session_factory is not None


def _has_storage() -> bool:
    return _document_storage is not None


async def _read_markdown(markdown_key: str) -> Optional[str]:
    """Read markdown content from storage or filesystem. Returns None if not available."""
    if not markdown_key:
        return None
    try:
        if _has_storage() and await _document_storage.exists("markdown", markdown_key):
            md_bytes = await _document_storage.download("markdown", markdown_key)
            return md_bytes.decode("utf-8")
        elif Path(markdown_key).exists():
            return Path(markdown_key).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read markdown {markdown_key}: {e}")
    return None


async def _resolve_document(doc_id: str):
    """Resolve a document ID to metadata dict with filename, storage_key, markdown_key, category.

    Returns None if not found.
    """
    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            pg_doc = await repo.get_by_external_id(doc_id)
            if not pg_doc:
                return None
            return {
                "filename": pg_doc.filename,
                "storage_key": pg_doc.source_path,
                "markdown_key": pg_doc.markdown_path,
                "category": pg_doc.category or "general",
                "status": pg_doc.status,
            }
    else:
        doc = document_tracker.get_document(doc_id)
        if not doc:
            return None
        return {
            "filename": doc.filename,
            "storage_key": doc.path,
            "markdown_key": doc.markdown_path,
            "category": getattr(doc, "category", "general"),
            "status": doc.status,
        }


# Active ingestion jobs
active_jobs: dict = {}


def _pg_doc_to_tracker_dict(pg_doc) -> dict:
    """Map a PostgreSQL Document model to the DocumentTracker response shape."""
    return {
        "id": pg_doc.external_id or str(pg_doc.id),
        "filename": pg_doc.filename,
        "path": pg_doc.source_path or "",
        "category": pg_doc.category or "general",
        "size_bytes": pg_doc.size_bytes or 0,
        "status": pg_doc.status or "not_started",
        "ingested_at": pg_doc.ingested_at.isoformat() if pg_doc.ingested_at else None,
        "entity_count": pg_doc.entity_count or 0,
        "relationship_count": pg_doc.relationship_count or 0,
        "error_message": pg_doc.error_message,
        "markdown_path": pg_doc.markdown_path,
        "created_at": pg_doc.created_at.isoformat() if pg_doc.created_at else None,
        "updated_at": pg_doc.updated_at.isoformat() if pg_doc.updated_at else None,
        "quality_score": None,
        "quality_level": None,
        "quality_assessed_at": None,
    }


@router.get("")
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by filename")
):
    """List all documents with their ingestion status."""
    try:
        if _has_postgres():
            from infrastructure.database.repositories import DocumentRepository

            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                pg_docs = await repo.list_filtered(
                    status=status, category=category, search=search
                )
            return [_pg_doc_to_tracker_dict(d) for d in pg_docs]

        documents = document_tracker.list_documents(
            status=status,
            category=category,
            search=search
        )
        return [doc.to_dict() for doc in documents]
    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories():
    """Get all document categories."""
    try:
        if _has_postgres():
            from infrastructure.database.repositories import DocumentRepository

            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                categories = await repo.get_categories()
            return {"categories": categories}

        categories = document_tracker.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """Get document statistics."""
    try:
        if _has_postgres():
            from infrastructure.database.repositories import DocumentRepository

            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                stats = await repo.get_full_statistics()
            return stats

        stats = document_tracker.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def get_active_jobs():
    """Get all active ingestion jobs."""
    return list(active_jobs.values())


@router.get("/{doc_id}")
async def get_document_details(doc_id: str):
    """Get detailed information about a document."""
    try:
        if _has_postgres():
            from infrastructure.database.repositories import DocumentRepository

            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                pg_doc = await repo.get_by_external_id(doc_id)

            if not pg_doc:
                raise HTTPException(status_code=404, detail="Document not found")

            result = _pg_doc_to_tracker_dict(pg_doc)
            result["processed_at"] = result.get("ingested_at")

            # Add markdown preview from storage
            md_key = pg_doc.markdown_path
            if md_key:
                try:
                    if _has_storage() and await _document_storage.exists("markdown", md_key):
                        md_bytes = await _document_storage.download("markdown", md_key)
                        content = md_bytes.decode("utf-8")
                    elif Path(md_key).exists():
                        content = Path(md_key).read_text(encoding="utf-8")
                    else:
                        content = None

                    if content:
                        result["markdown_preview"] = content[:2000]
                        result["markdown_length"] = len(content)
                except Exception as e:
                    logger.warning(f"Could not read markdown: {e}")
                    result["markdown_preview"] = None

            return result

        doc = document_tracker.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        result = doc.to_dict()

        # Add processed_at alias for frontend compatibility (backend uses ingested_at)
        result["processed_at"] = result.get("ingested_at")

        # Add markdown preview if available
        if doc.markdown_path and Path(doc.markdown_path).exists():
            try:
                content = Path(doc.markdown_path).read_text(encoding='utf-8')
                result["markdown_preview"] = content[:2000]
                result["markdown_length"] = len(content)
            except Exception as e:
                logger.warning(f"Could not read markdown: {e}")
                result["markdown_preview"] = None

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    category: str = Query(default="general", description="Category folder"),
    auto_ingest: bool = Query(default=False, description="Auto-start ingestion")
):
    """Upload PDF files."""
    uploaded = []
    failed = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            failed.append({"filename": file.filename or "unknown", "error": "Not a PDF file"})
            continue

        try:
            content = await file.read()
            external_id = str(uuid.uuid4())[:8]
            storage_key = f"{category}/{external_id}/{file.filename}" if category != "general" else f"{external_id}/{file.filename}"

            if _has_storage():
                # Store in DocumentStorage (blob or local abstraction)
                await _document_storage.upload(
                    "documents", storage_key, content, "application/pdf"
                )
            else:
                # Fallback: write to local filesystem directly
                target_dir = PDF_DIRECTORY / category if category != "general" else PDF_DIRECTORY
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / file.filename).write_bytes(content)

            if _has_postgres():
                from infrastructure.database.repositories import DocumentRepository

                async with _db_session_factory() as session:
                    repo = DocumentRepository(session)
                    pg_doc = await repo.register_document(
                        filename=file.filename,
                        category=category,
                        size_bytes=len(content),
                        storage_key=storage_key,
                        external_id=external_id,
                    )
                    await session.commit()
                    doc_id = pg_doc.external_id or str(pg_doc.id)

                uploaded.append({
                    "id": doc_id,
                    "filename": file.filename,
                    "size_bytes": len(content),
                })
            else:
                # Legacy fallback
                target_dir = PDF_DIRECTORY / category if category != "general" else PDF_DIRECTORY
                target_dir.mkdir(parents=True, exist_ok=True)
                file_path = target_dir / file.filename
                if not file_path.exists():
                    file_path.write_bytes(content)
                record = document_tracker.register_document(file_path, category)
                uploaded.append({
                    "id": record.id,
                    "filename": record.filename,
                    "size_bytes": record.size_bytes,
                })

            logger.info(f"Uploaded: {file.filename} (storage_key={storage_key})")

        except Exception as e:
            logger.error(f"Upload failed for {file.filename}: {e}")
            failed.append({"filename": file.filename, "error": str(e)})

    return {
        "uploaded": uploaded,
        "failed": failed,
        "auto_ingestion_started": False,
    }


@router.post("/{doc_id}/ingest")
async def trigger_ingestion(
    doc_id: str,
    background_tasks: BackgroundTasks,
    use_neo4j: bool = Query(default=True, description="Use Neo4j ingestion (recommended for DIKW layer storage)"),
    save_markdown: bool = Query(default=True, description="Save markdown output")
):
    """Trigger ingestion for a single document."""
    filename = None
    storage_key = None
    status = None

    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            pg_doc = await repo.get_by_external_id(doc_id)
            if not pg_doc:
                raise HTTPException(status_code=404, detail="Document not found")
            if pg_doc.status == "processing":
                raise HTTPException(status_code=409, detail="Document is already being processed")
            filename = pg_doc.filename
            storage_key = pg_doc.source_path
            status = pg_doc.status
    else:
        doc = document_tracker.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.status == "processing":
            raise HTTPException(status_code=409, detail="Document is already being processed")
        filename = doc.filename
        storage_key = doc.path
        if not Path(doc.path).exists():
            raise HTTPException(status_code=404, detail="PDF file not found on disk")

    # Verify file exists in storage
    if _has_storage() and storage_key:
        if not await _document_storage.exists("documents", storage_key):
            raise HTTPException(status_code=404, detail="PDF file not found in storage")

    # Create job
    job_id = str(uuid.uuid4())[:8]
    job = {
        "job_id": job_id,
        "document_id": doc_id,
        "filename": filename,
        "status": "queued",
        "started_at": None,
        "progress": 0.0,
        "message": "Queued for processing"
    }
    active_jobs[job_id] = job

    # Queue background task
    background_tasks.add_task(
        run_ingestion,
        job_id=job_id,
        doc_id=doc_id,
        use_neo4j=use_neo4j,
        save_markdown=save_markdown
    )

    logger.info(f"Queued ingestion job {job_id} for document {doc_id}")

    return job


@router.post("/ingest/batch")
async def trigger_batch_ingestion(
    background_tasks: BackgroundTasks,
    document_ids: Optional[List[str]] = Query(None, description="Document IDs to ingest (None = all pending)"),
    use_neo4j: bool = Query(default=True, description="Use Neo4j ingestion (recommended)"),
    save_markdown: bool = Query(default=True)
):
    """Trigger batch ingestion for multiple documents."""
    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            if document_ids:
                documents = []
                for did in document_ids:
                    pg_doc = await repo.get_by_external_id(did)
                    if pg_doc:
                        documents.append(pg_doc)
            else:
                documents = await repo.get_by_status("not_started")
    else:
        if document_ids:
            documents = [document_tracker.get_document(doc_id) for doc_id in document_ids]
            documents = [d for d in documents if d is not None]
        else:
            documents = document_tracker.list_documents(status="not_started")

    if not documents:
        return {"message": "No documents to process", "jobs": []}

    jobs = []
    for doc in documents:
        if doc.status == "processing":
            continue

        # Use external_id for PG documents, .id for legacy tracker
        doc_id = getattr(doc, "external_id", None) or doc.id

        job_id = str(uuid.uuid4())[:8]
        job = {
            "job_id": job_id,
            "document_id": doc_id,
            "filename": doc.filename,
            "status": "queued",
            "started_at": None,
            "progress": 0.0,
            "message": "Queued for batch processing"
        }
        active_jobs[job_id] = job
        jobs.append(job)

        background_tasks.add_task(
            run_ingestion,
            job_id=job_id,
            doc_id=doc_id,
            use_neo4j=use_neo4j,
            save_markdown=save_markdown
        )

    logger.info(f"Queued batch ingestion: {len(jobs)} jobs")

    return {
        "message": f"Queued {len(jobs)} documents for ingestion",
        "jobs": jobs
    }


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    delete_pdf: bool = Query(default=True, description="Delete PDF file"),
    delete_markdown: bool = Query(default=True, description="Delete markdown file"),
    delete_graph_data: bool = Query(default=True, description="Delete graph data")
):
    """Delete a document and its associated data."""
    storage_key = None
    markdown_key = None
    filename = None

    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            pg_doc = await repo.get_by_external_id(doc_id)
            if not pg_doc:
                raise HTTPException(status_code=404, detail="Document not found")
            storage_key = pg_doc.source_path
            markdown_key = pg_doc.markdown_path
            filename = pg_doc.filename
            await session.delete(pg_doc)
            await session.commit()
    else:
        doc = document_tracker.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        storage_key = doc.path
        markdown_key = doc.markdown_path
        filename = doc.filename

    result = {
        "success": True,
        "pdf_deleted": False,
        "markdown_deleted": False,
        "graph_nodes_deleted": 0
    }

    # Delete PDF from storage
    if delete_pdf and storage_key:
        try:
            if _has_storage():
                await _document_storage.delete("documents", storage_key)
            elif Path(storage_key).exists():
                Path(storage_key).unlink()
            result["pdf_deleted"] = True
        except Exception as e:
            logger.error(f"Failed to delete PDF: {e}")

    # Delete markdown from storage
    if delete_markdown and markdown_key:
        try:
            if _has_storage():
                await _document_storage.delete("markdown", markdown_key)
            elif Path(markdown_key).exists():
                Path(markdown_key).unlink()
            result["markdown_deleted"] = True
        except Exception as e:
            logger.error(f"Failed to delete markdown: {e}")

    if delete_graph_data and filename:
        logger.info(f"Graph data deletion requested for: {filename}")

    # Remove from legacy tracker if not using Postgres
    if not _has_postgres():
        document_tracker.remove_document(doc_id)

    return result


# --- Quality Assessment Endpoints ---

@router.get("/{doc_id}/content")
async def get_document_content(doc_id: str):
    """Get the full markdown content of a document for preview."""
    markdown_key = None

    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            pg_doc = await repo.get_by_external_id(doc_id)
            if not pg_doc:
                raise HTTPException(status_code=404, detail="Document not found")
            markdown_key = pg_doc.markdown_path
    else:
        doc = document_tracker.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        markdown_key = doc.markdown_path

    if not markdown_key:
        raise HTTPException(status_code=404, detail="Document content not found")

    try:
        # Read from storage or filesystem
        if _has_storage() and await _document_storage.exists("markdown", markdown_key):
            md_bytes = await _document_storage.download("markdown", markdown_key)
            content = md_bytes.decode("utf-8")
        elif Path(markdown_key).exists():
            content = Path(markdown_key).read_text(encoding="utf-8")
        else:
            raise HTTPException(status_code=404, detail="Document content not found")

        return {
            "content": content,
            "content_type": "text/markdown",
            "size_bytes": len(content.encode("utf-8")),
            "word_count": len(content.split()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading document content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}/entities")
async def get_document_entities(
    doc_id: str,
    layer: Optional[str] = Query(None, description="Filter by layer (PERCEPTION, SEMANTIC, REASONING, APPLICATION)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, description="Maximum entities to return"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get entities extracted from this document."""
    doc_meta = await _resolve_document(doc_id)
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        from infrastructure.neo4j_backend import Neo4jBackend
        import os

        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")

        backend = Neo4jBackend(uri=neo4j_uri, username=neo4j_user, password=neo4j_password)

        params = {"doc_name": doc_meta["filename"], "limit": limit, "offset": offset}
        logger.info(f"Fetching entities for document: '{doc_meta['filename']}' (doc_id: {doc_id})")

        # Build optional WHERE clause for filters
        entity_filters = []
        if layer:
            entity_filters.append("e.layer = $layer")
            params["layer"] = layer.upper()
        if entity_type:
            entity_filters.append("$entity_type IN labels(e)")
            params["entity_type"] = entity_type

        entity_where = f"WHERE {' AND '.join(entity_filters)}" if entity_filters else ""

        # Query entities via relationship path
        query = f"""
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:ExtractedEntity)
            WHERE d.name = $doc_name
            WITH DISTINCT e
            {entity_where}
            RETURN e, labels(e) as labels
            ORDER BY e.name
            SKIP $offset LIMIT $limit
        """

        count_query = f"""
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:ExtractedEntity)
            WHERE d.name = $doc_name
            WITH DISTINCT e
            {entity_where}
            RETURN count(e) as total
        """

        driver = await backend._get_driver()
        async with driver.session() as session:
            # Get total count
            count_result = await session.run(count_query, params)
            count_record = await count_result.single()
            total = count_record["total"] if count_record else 0

            # Get entities
            result = await session.run(query, params)
            records = await result.data()

        logger.info(f"Query returned {len(records)} entity records for '{doc_meta['filename']}'")

        entities = []
        for record in records:
            node = record["e"]
            labels = record["labels"]
            # Filter out base labels to get the specific entity type
            entity_type_label = next(
                (label for label in labels if label not in ["Entity", "ExtractedEntity"]),
                labels[0] if labels else "Unknown"
            )

            entities.append({
                "id": node.get("id") or node.get("name"),
                "name": node.get("name", "Unnamed"),
                "type": entity_type_label,
                "layer": node.get("layer", "PERCEPTION"),
                "confidence": node.get("confidence") or node.get("extraction_confidence", 0.7),
                "properties": {k: v for k, v in node.items() if k not in ["id", "name", "layer", "confidence", "extraction_confidence", "source_document"]},
            })

        await backend._close_driver()

        return {
            "document_id": doc_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "entities": entities,
        }

    except ImportError:
        # Neo4j not available, return mock data
        logger.warning("Neo4j backend not available, returning empty entities")
        return {
            "document_id": doc_id,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "entities": [],
        }
    except Exception as e:
        logger.error(f"Error fetching document entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}/graph")
async def get_document_graph(
    doc_id: str,
    limit: int = Query(100, description="Maximum nodes to return"),
):
    """Get knowledge graph subgraph created by this document."""
    doc_meta = await _resolve_document(doc_id)
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        from infrastructure.neo4j_backend import Neo4jBackend
        import os

        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "password")

        backend = Neo4jBackend(uri=neo4j_uri, username=neo4j_user, password=neo4j_password)

        query = """
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:ExtractedEntity)
            WHERE d.name = $doc_name
            WITH DISTINCT e
            LIMIT $limit
            OPTIONAL MATCH (e)-[r:LINKS_TO]-(other:ExtractedEntity)
            RETURN e, labels(e) as labels, collect(DISTINCT {rel: r, target: other}) as connections
        """

        driver = await backend._get_driver()
        async with driver.session() as session:
            result = await session.run(query, {"doc_name": doc_meta["filename"], "limit": limit})
            records = await result.data()

        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()

        for record in records:
            node = record["e"]
            labels = record["labels"]
            node_id = node.get("id") or node.get("name")

            if node_id and node_id not in seen_nodes:
                seen_nodes.add(node_id)
                entity_type = next(
                    (label for label in labels if label not in ["Entity", "ExtractedEntity"]),
                    labels[0] if labels else "Unknown"
                )
                nodes.append({
                    "id": node_id,
                    "label": node.get("name", node_id),
                    "name": node.get("name", node_id),
                    "type": entity_type,
                    "layer": node.get("layer", "PERCEPTION"),
                    "confidence": node.get("confidence") or node.get("extraction_confidence", 0.7),
                })

            # Process connections (LINKS_TO relationships between entities)
            for conn in record.get("connections", []):
                rel = conn.get("rel")
                target = conn.get("target")

                if rel and target:
                    target_id = target.get("id") or target.get("name")
                    if target_id and target_id not in seen_nodes:
                        seen_nodes.add(target_id)
                        # Get target labels from the node dict
                        target_type = target.get("type", "Unknown")
                        nodes.append({
                            "id": target_id,
                            "label": target.get("name", target_id),
                            "name": target.get("name", target_id),
                            "type": target_type,
                            "layer": target.get("layer", "PERCEPTION"),
                            "confidence": target.get("confidence") or target.get("extraction_confidence", 0.7),
                        })

                    # Create edge
                    edge_key = tuple(sorted([node_id, target_id]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        rel_type = rel.type if hasattr(rel, 'type') else "LINKS_TO"
                        edges.append({
                            "source": node_id,
                            "target": target_id,
                            "type": rel_type,
                            "label": rel_type,
                        })

        await backend._close_driver()

        return {
            "document_id": doc_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    except ImportError:
        logger.warning("Neo4j backend not available, returning empty graph")
        return {
            "document_id": doc_id,
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
        }
    except Exception as e:
        logger.error(f"Error fetching document graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}/quality")
async def get_document_quality(doc_id: str):
    """Get quality metrics for a document."""
    doc_meta = await _resolve_document(doc_id)
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    markdown_content = await _read_markdown(doc_meta["markdown_key"])
    if not markdown_content:
        raise HTTPException(
            status_code=400,
            detail="Document must be ingested before quality assessment"
        )

    try:
        result = await quick_quality_check(
            markdown_text=markdown_content,
            document_name=doc_meta["filename"]
        )

        return {
            "document_id": doc_id,
            "filename": doc_meta["filename"],
            **result
        }

    except Exception as e:
        logger.error(f"Quality assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{doc_id}/quality/assess")
async def assess_document_quality(
    doc_id: str,
    expected_topics: Optional[List[str]] = Query(None, description="Expected topics to verify")
):
    """Run full quality assessment on a document."""
    doc_meta = await _resolve_document(doc_id)
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    markdown_content = await _read_markdown(doc_meta["markdown_key"])
    if not markdown_content:
        raise HTTPException(
            status_code=400,
            detail="Document must be ingested before quality assessment"
        )

    try:
        from application.services.text_chunker import TextChunker
        import hashlib

        chunker = TextChunker()
        content_hash = hashlib.sha256(markdown_content.encode()).hexdigest()[:16]
        chunks = chunker.chunk_text(markdown_content, doc_id=content_hash)

        quality_service = DocumentQualityService()
        report = await quality_service.assess_document(
            document_id=doc_id,
            document_name=doc_meta["filename"],
            markdown_text=markdown_content,
            chunks=chunks,
            expected_topics=expected_topics,
        )

        return report.to_dict()

    except Exception as e:
        logger.error(f"Full quality assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality/summary")
async def get_quality_summary():
    """Get quality summary across all ingested documents.

    Returns data in the format expected by the QualityDashboard frontend component.
    """
    try:
        empty_response = {
            "total_assessed": 0,
            "by_quality_level": {},
            "averages": {
                "overall_score": 0,
                "context_precision": 0,
                "context_recall": 0,
                "topic_coverage": 0,
                "signal_to_noise": 0,
                "entity_extraction_rate": 0,
                "retrieval_quality": 0,
            },
        }

        if _has_postgres():
            from infrastructure.database.repositories import DocumentRepository

            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                documents = await repo.get_by_status("completed")
        else:
            documents = document_tracker.list_documents(status="completed")

        if not documents:
            return empty_response

        quality_results = []
        quality_levels = {level.value: 0 for level in QualityLevel}
        score_sums = {
            "overall_score": 0,
            "context_precision": 0,
            "context_recall": 0,
            "topic_coverage": 0,
            "signal_to_noise": 0,
            "entity_extraction_rate": 0,
            "retrieval_quality": 0,
        }

        for doc in documents:
            md_key = doc.markdown_path
            if not md_key:
                continue

            try:
                markdown_content = await _read_markdown(md_key)
                if not markdown_content:
                    continue

                doc_filename = doc.filename
                doc_id = getattr(doc, "external_id", None) or doc.id
                result = await quick_quality_check(markdown_content, doc_filename)

                quality_results.append({
                    "document_id": doc_id,
                    "filename": doc_filename,
                    "quality_level": result["quality_level"],
                    "overall_score": result["overall_score"],
                })

                quality_levels[result["quality_level"]] += 1

                score_sums["overall_score"] += result["overall_score"]
                scores = result.get("scores", {})
                if scores:
                    score_sums["context_precision"] += scores.get("context_precision", 0)
                    score_sums["context_recall"] += scores.get("context_recall", 0)
                    score_sums["topic_coverage"] += scores.get("topic_coverage", 0)
                    score_sums["signal_to_noise"] += scores.get("signal_to_noise", 0)
                    score_sums["entity_extraction_rate"] += scores.get("entity_extraction_rate", 0)
                    score_sums["retrieval_quality"] += scores.get("retrieval_quality", 0)

            except Exception as e:
                logger.warning(f"Could not assess {doc.filename}: {e}")

        n = len(quality_results)
        averages = {k: v / n if n > 0 else 0 for k, v in score_sums.items()}

        return {
            "total_assessed": n,
            "by_quality_level": quality_levels,
            "averages": averages,
            "documents": quality_results[:20],  # Top 20 for display
        }

    except Exception as e:
        logger.error(f"Quality summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def run_ingestion(
    job_id: str,
    doc_id: str,
    use_neo4j: bool,
    save_markdown: bool
):
    """Background task for running document ingestion.

    Reads PDF from DocumentStorage, runs KG ingestion, writes markdown
    to DocumentStorage, and updates Postgres with results.
    """
    import tempfile

    job = active_jobs.get(job_id)
    if not job:
        return

    # Resolve document metadata
    filename = None
    storage_key = None
    category = "general"
    size_bytes = 0

    if _has_postgres():
        from infrastructure.database.repositories import DocumentRepository

        async with _db_session_factory() as session:
            repo = DocumentRepository(session)
            pg_doc = await repo.get_by_external_id(doc_id)
            if not pg_doc:
                job["status"] = "failed"
                job["error"] = "Document not found"
                return
            filename = pg_doc.filename
            storage_key = pg_doc.source_path
            category = pg_doc.category or "general"
            size_bytes = pg_doc.size_bytes or 0
            await repo.update_status(pg_doc.id, "processing")
            await session.commit()
    else:
        doc = document_tracker.get_document(doc_id)
        if not doc:
            job["status"] = "failed"
            job["error"] = "Document not found"
            return
        filename = doc.filename
        storage_key = doc.path
        category = doc.category
        size_bytes = getattr(doc, "size_bytes", 0)
        document_tracker.update_document(doc_id, status="processing")

    try:
        job["status"] = "processing"
        job["started_at"] = datetime.now().isoformat()
        job["message"] = "Starting ingestion..."

        # Get PDF bytes — from storage or local filesystem
        if _has_storage() and storage_key:
            pdf_bytes = await _document_storage.download("documents", storage_key)
        else:
            pdf_bytes = Path(storage_key).read_bytes()

        # Write PDF to a temp file for the ingestion service
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_pdf_path = Path(tmp.name)

        try:
            result = await _run_kg_ingestion(
                job, tmp_pdf_path, filename, category, size_bytes,
                use_neo4j, save_markdown
            )
        finally:
            tmp_pdf_path.unlink(missing_ok=True)

        job["progress"] = 0.8
        job["message"] = "Ingestion complete, saving results..."

        entities_added = result.get("entities_added", 0)
        relationships_added = result.get("relationships_added", 0)

        # Save markdown to storage and get storage key
        markdown_key = None
        markdown_content = None
        if save_markdown:
            local_md_path = MARKDOWN_DIRECTORY / f"{Path(filename).stem}.md"
            if local_md_path.exists():
                markdown_content = local_md_path.read_text(encoding="utf-8")
                markdown_key = f"{Path(filename).stem}.md"
                if _has_storage():
                    await _document_storage.upload(
                        "markdown", markdown_key,
                        markdown_content.encode("utf-8"), "text/markdown"
                    )

        # Update tracking
        if _has_postgres():
            async with _db_session_factory() as session:
                repo = DocumentRepository(session)
                pg_doc = await repo.get_by_external_id(doc_id)
                if pg_doc:
                    await repo.update_status(pg_doc.id, "completed")
                    await repo.update_ingestion_results(
                        pg_doc.id,
                        entity_count=entities_added,
                        relationship_count=relationships_added,
                        markdown_key=markdown_key,
                    )
                    await session.commit()
        else:
            document_tracker.update_document(
                doc_id,
                status="completed",
                ingested_at=datetime.now().isoformat(),
                entity_count=entities_added,
                relationship_count=relationships_added,
                markdown_path=str(MARKDOWN_DIRECTORY / f"{Path(filename).stem}.md") if save_markdown else None,
                error_message=None,
            )

        # Auto-assess quality
        if markdown_content:
            try:
                quality_result = await quick_quality_check(markdown_content, filename)
                job["quality_score"] = quality_result.get("overall_score")
                job["quality_level"] = quality_result.get("quality_level")
                logger.info(f"Quality assessed for {filename}: {job['quality_level']} ({job['quality_score']:.2f})")
            except Exception as qe:
                logger.warning(f"Quality assessment failed for {filename}: {qe}")

        job["progress"] = 1.0
        job["message"] = "Complete"
        job["status"] = "completed"
        job["entities_added"] = entities_added
        job["relationships_added"] = relationships_added

        logger.info(f"Ingestion completed for {filename}: {entities_added} entities, {relationships_added} relationships")

    except Exception as e:
        logger.error(f"Ingestion failed for {filename}: {e}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"Failed: {str(e)}"

        if _has_postgres():
            try:
                async with _db_session_factory() as session:
                    repo = DocumentRepository(session)
                    pg_doc = await repo.get_by_external_id(doc_id)
                    if pg_doc:
                        await repo.update_status(pg_doc.id, "failed", error_message=str(e))
                        await session.commit()
            except Exception:
                pass
        else:
            document_tracker.update_document(
                doc_id, status="failed", error_message=str(e)
            )

    finally:
        # Clean up job after some time (keep for 5 minutes)
        await asyncio.sleep(300)
        if job_id in active_jobs:
            del active_jobs[job_id]


async def _run_kg_ingestion(job, pdf_path, filename, category, size_bytes, use_neo4j, save_markdown):
    """Run the actual KG ingestion (Neo4j or FalkorDB)."""
    from application.services.neo4j_pdf_ingestion import Neo4jPDFIngestionService, PDFDocument

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    if use_neo4j:
        service = Neo4jPDFIngestionService(
            pdf_directory=PDF_DIRECTORY,
            openai_api_key=openai_api_key,
            model="gpt-4o-mini"
        )
        pdf_doc = PDFDocument(
            path=pdf_path,
            filename=filename,
            category=category,
            size_bytes=size_bytes,
        )
    else:
        from application.services.simple_pdf_ingestion import SimplePDFIngestionService, PDFDocument as FalkorPDFDocument
        service = SimplePDFIngestionService(
            pdf_directory=PDF_DIRECTORY,
            openai_api_key=openai_api_key,
            falkor_host="localhost",
            falkor_port=6379,
            graph_name="medical_knowledge",
            model="gpt-4o-mini"
        )
        pdf_doc = FalkorPDFDocument(
            path=pdf_path,
            filename=filename,
            category=category,
            size_bytes=size_bytes,
        )

    job["message"] = "Converting PDF to markdown..."
    job["progress"] = 0.2

    result = await service.ingest_document(
        pdf_doc,
        save_markdown=save_markdown,
        markdown_output_dir=MARKDOWN_DIRECTORY if save_markdown else None
    )
    return result

"""Document Management API Router.

Provides endpoints for managing PDF documents and their ingestion.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from pathlib import Path
from typing import List, Optional
import asyncio
import uuid
import os
from datetime import datetime
import logging

from application.services.document_tracker import DocumentTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/documents", tags=["Document Management"])

# Configuration
PDF_DIRECTORY = Path("PDFs")
MARKDOWN_DIRECTORY = Path("markdown_output")
TRACKING_FILE = Path("data/document_tracking.json")

# Global instances
document_tracker = DocumentTracker(
    tracking_file=TRACKING_FILE,
    pdf_directory=PDF_DIRECTORY,
    markdown_directory=MARKDOWN_DIRECTORY
)

# Active ingestion jobs
active_jobs: dict = {}


@router.get("")
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by filename")
):
    """List all documents with their ingestion status."""
    try:
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
        categories = document_tracker.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """Get document statistics."""
    try:
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
        doc = document_tracker.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        result = doc.to_dict()

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

    # Determine target directory
    target_dir = PDF_DIRECTORY / category if category != "general" else PDF_DIRECTORY
    target_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            failed.append({"filename": file.filename or "unknown", "error": "Not a PDF file"})
            continue

        try:
            file_path = target_dir / file.filename
            content = await file.read()
            file_path.write_bytes(content)

            # Register in tracker
            record = document_tracker.register_document(file_path, category)
            uploaded.append({
                "id": record.id,
                "filename": record.filename,
                "size_bytes": record.size_bytes
            })

            logger.info(f"Uploaded: {file.filename} -> {file_path}")

        except Exception as e:
            logger.error(f"Upload failed for {file.filename}: {e}")
            failed.append({"filename": file.filename, "error": str(e)})

    return {
        "uploaded": uploaded,
        "failed": failed,
        "auto_ingestion_started": False  # TODO: Implement auto-ingestion
    }


@router.post("/{doc_id}/ingest")
async def trigger_ingestion(
    doc_id: str,
    background_tasks: BackgroundTasks,
    use_falkor: bool = Query(default=True, description="Use FalkorDB ingestion"),
    save_markdown: bool = Query(default=True, description="Save markdown output")
):
    """Trigger ingestion for a single document."""
    doc = document_tracker.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="Document is already being processed")

    # Check if file exists
    if not Path(doc.path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    # Create job
    job_id = str(uuid.uuid4())[:8]
    job = {
        "job_id": job_id,
        "document_id": doc_id,
        "filename": doc.filename,
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
        use_falkor=use_falkor,
        save_markdown=save_markdown
    )

    logger.info(f"Queued ingestion job {job_id} for document {doc_id}")

    return job


@router.post("/ingest/batch")
async def trigger_batch_ingestion(
    background_tasks: BackgroundTasks,
    document_ids: Optional[List[str]] = Query(None, description="Document IDs to ingest (None = all pending)"),
    use_falkor: bool = Query(default=True),
    save_markdown: bool = Query(default=True)
):
    """Trigger batch ingestion for multiple documents."""
    if document_ids:
        documents = [document_tracker.get_document(doc_id) for doc_id in document_ids]
        documents = [d for d in documents if d is not None]
    else:
        # Get all pending documents
        documents = document_tracker.list_documents(status="not_started")

    if not documents:
        return {"message": "No documents to process", "jobs": []}

    jobs = []
    for doc in documents:
        if doc.status == "processing":
            continue

        job_id = str(uuid.uuid4())[:8]
        job = {
            "job_id": job_id,
            "document_id": doc.id,
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
            doc_id=doc.id,
            use_falkor=use_falkor,
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
    doc = document_tracker.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = {
        "success": True,
        "pdf_deleted": False,
        "markdown_deleted": False,
        "graph_nodes_deleted": 0
    }

    # Delete PDF file
    if delete_pdf:
        pdf_path = Path(doc.path)
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                result["pdf_deleted"] = True
                logger.info(f"Deleted PDF: {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to delete PDF: {e}")

    # Delete markdown file
    if delete_markdown and doc.markdown_path:
        md_path = Path(doc.markdown_path)
        if md_path.exists():
            try:
                md_path.unlink()
                result["markdown_deleted"] = True
                logger.info(f"Deleted markdown: {md_path}")
            except Exception as e:
                logger.error(f"Failed to delete markdown: {e}")

    # Delete from graph (requires kg_backend - handled separately if needed)
    if delete_graph_data:
        # Note: Graph deletion would require kg_backend dependency
        # For now, we just log the intent
        logger.info(f"Graph data deletion requested for: {doc.filename}")
        # TODO: Implement graph cleanup when kg_backend is available

    # Remove from tracker
    document_tracker.remove_document(doc_id)

    return result


async def run_ingestion(
    job_id: str,
    doc_id: str,
    use_falkor: bool,
    save_markdown: bool
):
    """Background task for running document ingestion."""
    job = active_jobs.get(job_id)
    if not job:
        return

    doc = document_tracker.get_document(doc_id)
    if not doc:
        job["status"] = "failed"
        job["error"] = "Document not found"
        return

    try:
        job["status"] = "processing"
        job["started_at"] = datetime.now().isoformat()
        job["message"] = "Starting ingestion..."

        # Update document status
        document_tracker.update_document(doc_id, status="processing")

        if use_falkor:
            # Import here to avoid circular imports
            from application.services.simple_pdf_ingestion import SimplePDFIngestionService, PDFDocument

            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")

            service = SimplePDFIngestionService(
                pdf_directory=PDF_DIRECTORY,
                openai_api_key=openai_api_key,
                falkor_host="localhost",
                falkor_port=6379,
                graph_name="medical_knowledge",
                model="gpt-4o-mini"
            )

            # Create PDFDocument
            pdf_path = Path(doc.path)
            pdf_doc = PDFDocument(
                path=pdf_path,
                filename=pdf_path.name,
                category=doc.category,
                size_bytes=pdf_path.stat().st_size
            )

            job["message"] = "Converting PDF to markdown..."
            job["progress"] = 0.2

            # Run ingestion
            result = await service.ingest_document(
                pdf_doc,
                save_markdown=save_markdown,
                markdown_output_dir=MARKDOWN_DIRECTORY if save_markdown else None
            )

            job["progress"] = 1.0
            job["message"] = "Ingestion complete"

            # Update document record
            document_tracker.update_document(
                doc_id,
                status="completed",
                ingested_at=datetime.now().isoformat(),
                entity_count=result.get("entities_added", 0),
                relationship_count=result.get("relationships_added", 0),
                markdown_path=str(MARKDOWN_DIRECTORY / f"{pdf_path.stem}.md") if save_markdown else None,
                error_message=None
            )

            job["status"] = "completed"
            job["entities_added"] = result.get("entities_added", 0)
            job["relationships_added"] = result.get("relationships_added", 0)

            logger.info(f"Ingestion completed for {doc.filename}: {result.get('entities_added', 0)} entities, {result.get('relationships_added', 0)} relationships")

        else:
            # Placeholder for other ingestion methods
            job["status"] = "failed"
            job["error"] = "No ingestion method selected"

    except Exception as e:
        logger.error(f"Ingestion failed for {doc.filename}: {e}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"Failed: {str(e)}"

        document_tracker.update_document(
            doc_id,
            status="failed",
            error_message=str(e)
        )

    finally:
        # Clean up job after some time (keep for 5 minutes)
        await asyncio.sleep(300)
        if job_id in active_jobs:
            del active_jobs[job_id]

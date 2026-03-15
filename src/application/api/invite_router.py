"""Invite Management API Router.

Admin endpoints for creating, listing, and revoking invite tokens.
"""

import secrets
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/invites", tags=["Invite Management"])

# PostgreSQL session factory (set during app startup)
_db_session_factory = None


def configure_invites(db_session_factory):
    """Configure PostgreSQL access for invites."""
    global _db_session_factory
    _db_session_factory = db_session_factory
    logger.info("Invite router configured with PostgreSQL support")


def _has_db() -> bool:
    return _db_session_factory is not None


class CreateInviteRequest(BaseModel):
    patient_id: str
    email: Optional[str] = None
    label: Optional[str] = None


@router.post("")
async def create_invite(request_body: CreateInviteRequest, request: Request):
    """Create a new invite token."""
    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import InviteRepository
    from infrastructure.database.models import Invite

    token = secrets.token_hex(32)

    async with _db_session_factory() as session:
        repo = InviteRepository(session)
        invite = Invite(
            token=token,
            patient_id=request_body.patient_id,
            email=request_body.email,
            label=request_body.label,
            status="pending",
        )
        session.add(invite)
        await session.flush()

        # Build invite URL from request origin
        origin = request.headers.get("origin") or request.headers.get("referer", "")
        if origin:
            # Strip path from referer if present
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            origin = f"{parsed.scheme}://{parsed.netloc}"
        else:
            origin = str(request.base_url).rstrip("/")

        invite_url = f"{origin}/invite/{token}"

        logger.info(f"Created invite for patient_id={request_body.patient_id} email={request_body.email}")

        return {
            "token": token,
            "patient_id": request_body.patient_id,
            "email": request_body.email,
            "label": request_body.label,
            "invite_url": invite_url,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
        }


@router.get("")
async def list_invites():
    """List all invites."""
    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import InviteRepository, UserRepository

    async with _db_session_factory() as session:
        repo = InviteRepository(session)
        invites = await repo.list_all()

        result = []
        for inv in invites:
            item = {
                "token": inv.token,
                "patient_id": inv.patient_id,
                "email": inv.email,
                "label": inv.label,
                "status": inv.status,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "redeemed_at": inv.redeemed_at.isoformat() if inv.redeemed_at else None,
                "redeemed_by": None,
            }
            if inv.redeemed_by_user_id:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_id(inv.redeemed_by_user_id)
                if user:
                    item["redeemed_by"] = user.display_name or user.email
            result.append(item)

        return result


@router.delete("/{token}")
async def revoke_invite(token: str):
    """Revoke an invite and invalidate the associated user session."""
    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import InviteRepository, UserRepository

    async with _db_session_factory() as session:
        invite_repo = InviteRepository(session)
        invite = await invite_repo.get_by_token(token)

        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        invite.status = "revoked"

        # Invalidate associated user session
        if invite.redeemed_by_user_id:
            user_repo = UserRepository(session)
            await user_repo.clear_session_token(invite.redeemed_by_user_id)
            logger.info(f"Revoked invite and invalidated session for user {invite.redeemed_by_user_id}")

        return {"status": "revoked", "token": token}

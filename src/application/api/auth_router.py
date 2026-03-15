"""Authentication API Router.

Provides invite redemption, session verification, and auth middleware.
"""

import secrets
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# PostgreSQL session factory (set during app startup)
_db_session_factory = None


def configure_auth(db_session_factory):
    """Configure PostgreSQL access for auth."""
    global _db_session_factory
    _db_session_factory = db_session_factory
    logger.info("Auth router configured with PostgreSQL support")


def _has_db() -> bool:
    return _db_session_factory is not None


async def get_current_user(authorization: Optional[str] = Header(None)):
    """FastAPI dependency to extract and verify session token.

    Returns the AppUser or raises 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization[7:]  # Strip "Bearer "

    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import UserRepository

    async with _db_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_session_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid session")
        await repo.update_last_active(user.id)
        return user


@router.post("/redeem/{token}")
async def redeem_invite(token: str):
    """Redeem an invite token to create a user session."""
    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import InviteRepository, UserRepository
    from infrastructure.database.models import AppUser

    async with _db_session_factory() as session:
        invite_repo = InviteRepository(session)
        user_repo = UserRepository(session)

        invite = await invite_repo.get_by_token(token)
        if not invite:
            raise HTTPException(status_code=404, detail="Invalid or expired invite")

        if invite.status == "revoked":
            raise HTTPException(status_code=404, detail="Invalid or expired invite")

        # If already redeemed, return the existing user's session (idempotent)
        if invite.status == "redeemed" and invite.redeemed_by_user_id:
            existing_user = await user_repo.get_by_id(invite.redeemed_by_user_id)
            if existing_user and existing_user.session_token:
                return {
                    "session_token": existing_user.session_token,
                    "patient_id": existing_user.patient_id,
                    "display_name": existing_user.display_name,
                    "email": existing_user.email,
                }

        # Create new user
        session_token = secrets.token_hex(32)
        user = AppUser(
            patient_id=invite.patient_id,
            email=invite.email,
            display_name=invite.label or invite.email,
            session_token=session_token,
            invite_id=invite.id,
        )
        session.add(user)
        await session.flush()

        # Mark invite as redeemed
        invite.status = "redeemed"
        invite.redeemed_at = datetime.utcnow()
        invite.redeemed_by_user_id = user.id

        logger.info(f"Invite redeemed: {invite.patient_id} ({invite.email})")

        return {
            "session_token": session_token,
            "patient_id": user.patient_id,
            "display_name": user.display_name,
            "email": user.email,
        }


@router.get("/verify")
async def verify_session(authorization: Optional[str] = Header(None)):
    """Verify a session token and return user info."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization[7:]

    if not _has_db():
        raise HTTPException(status_code=503, detail="Database not available")

    from infrastructure.database.repositories import UserRepository

    async with _db_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_session_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid session")
        await repo.update_last_active(user.id)

        return {
            "patient_id": user.patient_id,
            "display_name": user.display_name,
            "email": user.email,
        }

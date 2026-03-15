"""Tests for auth endpoints: redeem invite and verify session."""

import secrets
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

REPO_PATH = "infrastructure.database.repositories"


@pytest.fixture
def invite_pending():
    inv = MagicMock()
    inv.id = uuid4()
    inv.token = "abc123"
    inv.patient_id = "patient-1"
    inv.email = "test@example.com"
    inv.label = "Test User"
    inv.status = "pending"
    inv.redeemed_by_user_id = None
    return inv


@pytest.fixture
def user_mock():
    u = MagicMock()
    u.id = uuid4()
    u.patient_id = "patient-1"
    u.email = "test@example.com"
    u.display_name = "Test User"
    u.session_token = secrets.token_hex(32)
    return u


@pytest.fixture
def fake_session():
    session = AsyncMock()
    session.added = []

    session.add = lambda obj: session.added.append(obj)
    session.flush = AsyncMock()
    return session


@pytest.fixture
def client(fake_session):
    from application.api.main import app
    import application.api.auth_router as auth_mod
    import application.api.invite_router as invite_mod

    @asynccontextmanager
    async def mock_session_factory():
        yield fake_session

    auth_mod._db_session_factory = mock_session_factory
    invite_mod._db_session_factory = mock_session_factory
    yield TestClient(app, raise_server_exceptions=False)
    auth_mod._db_session_factory = None
    invite_mod._db_session_factory = None


# --- POST /api/auth/redeem/{token} ---


def test_redeem_valid_invite(client, fake_session, invite_pending):
    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo, \
         patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=invite_pending)
        MockUserRepo.return_value.get_by_id = AsyncMock(return_value=None)

        response = client.post("/api/auth/redeem/abc123")

    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient-1"
    assert data["email"] == "test@example.com"
    assert "session_token" in data
    assert len(data["session_token"]) == 64


def test_redeem_invalid_token_returns_404(client):
    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=None)

        response = client.post("/api/auth/redeem/nonexistent")

    assert response.status_code == 404


def test_redeem_revoked_invite_returns_404(client, invite_pending):
    invite_pending.status = "revoked"

    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=invite_pending)

        response = client.post("/api/auth/redeem/abc123")

    assert response.status_code == 404


def test_redeem_already_redeemed_returns_existing_session(client, invite_pending, user_mock):
    invite_pending.status = "redeemed"
    invite_pending.redeemed_by_user_id = user_mock.id

    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo, \
         patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=invite_pending)
        MockUserRepo.return_value.get_by_id = AsyncMock(return_value=user_mock)

        response = client.post("/api/auth/redeem/abc123")

    assert response.status_code == 200
    data = response.json()
    assert data["session_token"] == user_mock.session_token
    assert data["patient_id"] == "patient-1"


# --- GET /api/auth/verify ---


def test_verify_valid_session(client, user_mock):
    with patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockUserRepo.return_value.get_by_session_token = AsyncMock(return_value=user_mock)
        MockUserRepo.return_value.update_last_active = AsyncMock()

        response = client.get(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {user_mock.session_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient-1"
    assert data["display_name"] == "Test User"


def test_verify_missing_header_returns_401(client):
    response = client.get("/api/auth/verify")
    assert response.status_code == 401


def test_verify_invalid_token_returns_401(client):
    with patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockUserRepo.return_value.get_by_session_token = AsyncMock(return_value=None)

        response = client.get(
            "/api/auth/verify",
            headers={"Authorization": "Bearer invalidtoken"},
        )

    assert response.status_code == 401


def test_verify_malformed_header_returns_401(client):
    response = client.get(
        "/api/auth/verify",
        headers={"Authorization": "Token abc"},
    )
    assert response.status_code == 401

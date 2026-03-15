"""Tests for invite management endpoints (admin)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient

REPO_PATH = "infrastructure.database.repositories"


def _make_invite(token="tok1", patient_id="patient-1", status="pending", email=None, label=None):
    inv = MagicMock()
    inv.id = uuid4()
    inv.token = token
    inv.patient_id = patient_id
    inv.email = email
    inv.label = label
    inv.status = status
    inv.created_at = datetime(2026, 3, 6, 12, 0, 0)
    inv.redeemed_at = None
    inv.redeemed_by_user_id = None
    return inv


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
    import application.api.invite_router as invite_mod
    import application.api.auth_router as auth_mod

    @asynccontextmanager
    async def mock_session_factory():
        yield fake_session

    invite_mod._db_session_factory = mock_session_factory
    auth_mod._db_session_factory = mock_session_factory
    yield TestClient(app, raise_server_exceptions=False)
    invite_mod._db_session_factory = None
    auth_mod._db_session_factory = None


# --- POST /api/admin/invites ---


def test_create_invite(client, fake_session):
    with patch(f"{REPO_PATH}.InviteRepository"):
        response = client.post(
            "/api/admin/invites",
            json={"patient_id": "patient-1", "email": "user@test.com", "label": "Dr Smith"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient-1"
    assert data["email"] == "user@test.com"
    assert data["label"] == "Dr Smith"
    assert "token" in data
    assert len(data["token"]) == 64
    assert "invite_url" in data
    assert data["token"] in data["invite_url"]


def test_create_invite_minimal(client, fake_session):
    with patch(f"{REPO_PATH}.InviteRepository"):
        response = client.post(
            "/api/admin/invites",
            json={"patient_id": "patient-2"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "patient-2"
    assert data["email"] is None


def test_create_invite_missing_patient_id_returns_422(client):
    response = client.post("/api/admin/invites", json={})
    assert response.status_code == 422


# --- GET /api/admin/invites ---


def test_list_invites(client):
    invites = [
        _make_invite(token="tok1", patient_id="p1", status="pending"),
        _make_invite(token="tok2", patient_id="p2", status="redeemed", email="a@b.com"),
    ]

    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo, \
         patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockInviteRepo.return_value.list_all = AsyncMock(return_value=invites)
        MockUserRepo.return_value.get_by_id = AsyncMock(return_value=None)

        response = client.get("/api/admin/invites")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["token"] == "tok1"
    assert data[0]["status"] == "pending"
    assert data[1]["token"] == "tok2"


def test_list_invites_empty(client):
    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo:
        MockInviteRepo.return_value.list_all = AsyncMock(return_value=[])

        response = client.get("/api/admin/invites")

    assert response.status_code == 200
    assert response.json() == []


# --- DELETE /api/admin/invites/{token} ---


def test_revoke_invite(client):
    invite = _make_invite(token="tok1", status="redeemed")
    invite.redeemed_by_user_id = uuid4()

    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo, \
         patch(f"{REPO_PATH}.UserRepository") as MockUserRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=invite)
        MockUserRepo.return_value.clear_session_token = AsyncMock()

        response = client.delete("/api/admin/invites/tok1")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "revoked"
    assert invite.status == "revoked"
    MockUserRepo.return_value.clear_session_token.assert_awaited_once_with(invite.redeemed_by_user_id)


def test_revoke_nonexistent_invite_returns_404(client):
    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=None)

        response = client.delete("/api/admin/invites/nonexistent")

    assert response.status_code == 404


def test_revoke_pending_invite_no_user_session(client):
    invite = _make_invite(token="tok1", status="pending")

    with patch(f"{REPO_PATH}.InviteRepository") as MockInviteRepo:
        MockInviteRepo.return_value.get_by_token = AsyncMock(return_value=invite)

        response = client.delete("/api/admin/invites/tok1")

    assert response.status_code == 200
    assert invite.status == "revoked"

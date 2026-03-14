# Session Auth

## Purpose

Backend authentication: redeem invites to create user sessions, verify session tokens on API requests, and protect routes with auth middleware.

## Requirements

### Data Model

- `User` SQLAlchemy model in `src/infrastructure/database/models.py`
- Table `users` with columns: id (UUID PK), patient_id (String(255) NOT NULL), email (String(255) NULLABLE), display_name (String(255) NULLABLE), session_token (String(64) UNIQUE), invite_id (UUID FK to invites.id), created_at, last_active_at
- Index on `session_token` for fast auth lookups

### API Endpoints

**POST /api/auth/redeem/{token}**
- Looks up invite by token
- If not found or status != "pending": returns 404 `{ detail: "Invalid or expired invite" }`
- Creates `User` record with: patient_id from invite, email from invite, session_token = new random 32-byte hex, invite_id = invite.id
- Updates invite: status = "redeemed", redeemed_at = now, redeemed_by_user_id = user.id
- If invite was already redeemed by a user: return that user's session (idempotent — allows re-clicking the link)
- Returns: `{ session_token, patient_id, display_name, email }`

**GET /api/auth/verify**
- Requires `Authorization: Bearer {session_token}` header
- Looks up user by session_token
- If not found: returns 401 `{ detail: "Invalid session" }`
- Updates `last_active_at` to now
- Returns: `{ patient_id, display_name, email }`

### Auth Middleware

- FastAPI dependency function `get_current_user()`
- Extracts token from `Authorization: Bearer {token}` header
- Queries `users` table by session_token
- Returns user object or raises `HTTPException(401)`
- Applied to routes via dependency injection, NOT as global middleware
- **Protected routes**: all `/api/*` except `/api/auth/*`, `/health`
- **Unprotected routes**: `/api/auth/*`, `/api/admin/*`, `/health`

### Auth Router

- New `src/application/api/auth_router.py` with `APIRouter(prefix="/api/auth")`
- Registered in `main.py` alongside existing routers

## Boundary

- Does not manage invites (see `invite-management`)
- Does not handle frontend auth state (see `auth-frontend-gate`)
- Does not implement role-based access — all authenticated users have equal access

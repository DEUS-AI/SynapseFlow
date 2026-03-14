## Architecture

### Overview

Lightweight invite-based auth using session tokens stored in PostgreSQL. No external auth providers. Two roles: admin (unprotected, internal-only) and patient (invite-gated).

```
Browser → [Auth Check] → Landing Page (if no session)
                       → App Pages (if valid session)

Admin creates invite → UUID token → /invite/{token} URL
User opens link → POST /api/auth/redeem/{token} → session token returned
Browser stores token in localStorage → sent as Bearer header on all requests
```

### Data Model

Two new tables in the existing PostgreSQL database:

```
invites
├── id: UUID (PK)
├── token: String(64) UNIQUE — the invite URL token
├── patient_id: String(255) — maps to sessions.patient_id
├── email: String(255) NULLABLE — optional, for display
├── label: String(255) NULLABLE — admin note (e.g., "Tester Pablo")
├── status: String(50) — pending | redeemed | revoked
├── created_at: DateTime
├── redeemed_at: DateTime NULLABLE
└── redeemed_by_user_id: UUID FK → users.id NULLABLE

users
├── id: UUID (PK)
├── patient_id: String(255) — their patient identity for chat
├── email: String(255) NULLABLE
├── display_name: String(255) NULLABLE
├── session_token: String(64) UNIQUE — active session token
├── invite_id: UUID FK → invites.id
├── created_at: DateTime
└── last_active_at: DateTime
```

### API Design

**Auth endpoints (unprotected):**
- `POST /api/auth/redeem/{token}` — redeem invite, create user + session token. Returns `{ session_token, patient_id, display_name }`
- `GET /api/auth/verify` — verify Bearer token, returns user info or 401

**Admin invite endpoints (unprotected — admin is internal-only):**
- `POST /api/admin/invites` — create invite `{ patient_id, email?, label? }` → returns `{ token, invite_url }`
- `GET /api/admin/invites` — list all invites with status
- `DELETE /api/admin/invites/{token}` — revoke invite (also invalidates associated user session)

**Auth middleware:**
- FastAPI dependency `get_current_user()` — extracts Bearer token from `Authorization` header, looks up user, returns user object or raises 401
- Applied to all `/api/*` routes EXCEPT: `/api/auth/*`, `/health`, `/api/admin/*`
- Admin routes remain unprotected (admin is internal/ops access only)

### Frontend Architecture

**Auth context provider** (`AuthProvider`):
- React context wrapping all pages
- On mount: checks localStorage for `session_token`, calls `GET /api/auth/verify`
- If valid: stores user info (patient_id, display_name) in context
- If invalid/missing: redirects to landing page
- Provides `logout()` function (clears localStorage)

**Pages:**
- `/` — Landing page: "Welcome to SynapseFlow" with brief description. No links to app. Shows "Enter invite code" if user has one.
- `/invite/{token}` — Redemption page: calls redeem API, stores token, redirects to `/chat`
- `/chat` — Single dynamic page (replaces `/chat/[patientId].astro`). Gets `patient_id` from auth context.
- All other pages (`/admin/*`, `/graph`, `/dda/*`) — wrapped in auth check but accessible to any authenticated user

**API calls**: All `fetch()` calls include `Authorization: Bearer {token}` header. Updated in `api.ts`.

## Key Decisions

- **Session tokens, not JWTs**: Simple opaque tokens stored in DB. Easy to revoke, no expiry complexity. Good enough for a small tester pool.
- **No password**: Users only need the invite link. One invite = one user. Re-inviting creates a new token.
- **Admin unprotected**: Admin routes (`/api/admin/*`) stay open. They're only accessible from internal network / ops. Adding admin auth is a separate concern.
- **localStorage over cookies**: Simpler for SPA, no CSRF concerns. Token sent explicitly in headers.
- **Invite = one-time use**: Once redeemed, the invite is consumed. Admin can create new invites for the same patient_id if needed.

## Constraints

- No external auth dependencies (no OAuth, no Firebase, no Auth0)
- Must work with existing PostgreSQL setup (Azure Flexible Server)
- Session tokens never expire automatically (admin can revoke manually)
- Maximum ~50 concurrent users (tester scale, not production auth)

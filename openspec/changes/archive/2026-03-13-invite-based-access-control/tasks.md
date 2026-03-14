# Tasks

## 1. Database models and migration

- [x] 1.1 Add Invite and User models — `src/infrastructure/database/models.py` — Add Invite model (invites table: id, token, patient_id, email, label, status, created_at, redeemed_at, redeemed_by_user_id) and User model (users table: id, patient_id, email, display_name, session_token, invite_id, created_at, last_active_at) with indexes and constraints
- [x] 1.2 Add repository methods — `src/infrastructure/database/repositories.py` — InviteRepository (create, list_all, get_by_token, revoke) and UserRepository (create, get_by_session_token, update_last_active)
- [x] 1.3 Create database tables on startup — `src/application/api/main.py` — Ensure new tables are created via existing startup logic

## 2. Backend auth endpoints

- [x] 2.1 Auth router — `src/application/api/auth_router.py` (new), `src/application/api/main.py` — Create auth_router with POST /api/auth/redeem/{token} and GET /api/auth/verify, register in main.py
- [x] 2.2 Auth middleware dependency — `src/application/api/auth_router.py` — Create get_current_user() FastAPI dependency that extracts Bearer token and looks up user
- [x] 2.3 Protect existing API routes — `src/application/api/main.py` and routers — Add get_current_user dependency to chat, patient, feedback endpoints. Keep /api/auth/*, /api/admin/*, /health unprotected. WebSocket: verify token from query param

## 3. Admin invite management

- [x] 3.1 Invite router — `src/application/api/invite_router.py` (new), `src/application/api/main.py` — CRUD endpoints for invites at /api/admin/invites
- [x] 3.2 Admin invite UI — `frontend/src/components/admin/InviteManagement.tsx` (new), `frontend/src/pages/admin/index.astro` — Create form, invite list table, copy-to-clipboard, status badges, revoke

## 4. Frontend auth gate

- [x] 4.1 Auth context and provider — `frontend/src/contexts/AuthContext.tsx` (new) — AuthContext with user state, isLoading, isAuthenticated, logout; AuthProvider; useAuth() hook
- [x] 4.2 Auth gate component — `frontend/src/components/auth/AuthGate.tsx` (new) — Loading spinner, redirect if unauthenticated, render children if authenticated
- [x] 4.3 Update API client with auth headers — `frontend/src/lib/api.ts` — Add session_token from localStorage to Authorization header, handle 401 redirect
- [x] 4.4 Landing page update — `frontend/src/pages/index.astro` — If authenticated redirect to /chat, else show welcome message with invite link guidance
- [x] 4.5 Invite redemption page — `frontend/src/pages/invite/[token].astro` (new), `frontend/src/components/auth/InviteRedeem.tsx` (new) — Redeem invite, store token, redirect to /chat
- [x] 4.6 Chat page refactor — `frontend/src/pages/chat/index.astro` (new), delete `frontend/src/pages/chat/[patientId].astro` — Single /chat page, gets patient_id from AuthContext
- [x] 4.7 Wrap all pages in AuthGate — All page .astro files — Add AuthProvider + AuthGate wrapper, add user indicator with logout to header

## 5. Tests

- [x] 5.1 Backend auth tests — `tests/application/api/test_auth.py` (new) — Test redeem, verify, protected endpoints
- [x] 5.2 Backend invite management tests — `tests/application/api/test_invites.py` (new) — Test create, list, revoke invites

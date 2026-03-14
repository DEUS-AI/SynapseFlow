## Why

The platform is currently open — anyone with the URL can access all pages including patient chat, admin dashboard, knowledge graph, and DDA management. As we onboard testers, we need a way to restrict access to invited users only, tie each user to a patient identity for chat, and keep the admin area separate. This is not full RBAC — just a lightweight invite gate so testers can use the platform privately.

## What Changes

- Add invite-based access control: admin issues invite links, users redeem them to get access
- All pages require a valid session — unauthenticated users see only a welcome/landing page
- Each invite is tied to a `patient_id`, so the user's chat sessions are scoped to their patient
- Admin panel gets an "Invites" section to create, list, and revoke invite tokens
- Backend gets auth endpoints (redeem invite, verify session) and middleware to protect API routes
- Frontend gets an auth wrapper that checks session on every page load
- New PostgreSQL tables: `invites` and `users`
- **BREAKING**: Chat route changes from `/chat/patient:demo` (static) to `/chat` (dynamic, session-based)

## Capabilities

### New Capabilities
- `invite-management`: Backend API and admin UI for creating, listing, and revoking invite tokens tied to patient identities
- `session-auth`: Session-based authentication — redeem invite to create session, verify session on API calls, protect all routes with auth middleware
- `auth-frontend-gate`: Frontend auth wrapper that redirects unauthenticated users to a landing page, handles invite redemption, and scopes chat to the authenticated user's patient

### Modified Capabilities
_(none — no existing specs have requirement-level changes)_

## Impact

- **Database**: Two new PostgreSQL tables (`invites`, `users`) via SQLAlchemy models + Alembic migration
- **Backend API**: New `/api/auth/*` endpoints, new `/api/admin/invites/*` endpoints, auth middleware on all existing `/api/*` routes (except `/api/auth/*` and `/health`)
- **Frontend**: New landing page, invite redemption page, auth context provider wrapping all pages, removal of hardcoded `getStaticPaths` patient IDs in chat route
- **Deployment**: No new infrastructure — uses existing PostgreSQL. Admin access remains unprotected (internal network only for now)

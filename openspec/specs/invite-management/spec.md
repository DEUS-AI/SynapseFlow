# Invite Management

## Purpose

Admin-facing capability to create, list, and revoke invite tokens that grant access to the platform. Each invite is tied to a patient_id.

## Requirements

### Data Model

- `Invite` SQLAlchemy model in `src/infrastructure/database/models.py`
- Table `invites` with columns: id (UUID PK), token (String(64) UNIQUE), patient_id (String(255) NOT NULL), email (String(255) NULLABLE), label (String(255) NULLABLE), status (String(50) default "pending"), created_at, redeemed_at, redeemed_by_user_id (FK to users.id)
- Index on `token` column for fast lookups
- CheckConstraint on status: `pending`, `redeemed`, `revoked`

### API Endpoints

**POST /api/admin/invites**
- Body: `{ patient_id: string, email?: string, label?: string }`
- Generates a cryptographically random 32-byte hex token (64 chars)
- Creates invite record with status "pending"
- Returns: `{ token, patient_id, email, label, invite_url, created_at }`
- `invite_url` format: `{origin}/invite/{token}` (origin from request or config)

**GET /api/admin/invites**
- Returns all invites ordered by created_at desc
- Each invite includes: token, patient_id, email, label, status, created_at, redeemed_at, redeemed_by (user display_name if redeemed)

**DELETE /api/admin/invites/{token}**
- Sets invite status to "revoked"
- If invite was redeemed: also clears the associated user's session_token (forces logout)
- Returns 404 if token not found

### Admin UI

- New "Invites" tab/section in the admin panel at `/admin`
- Form to create invite: patient_id input (required), email input (optional), label input (optional)
- Table listing all invites with columns: patient_id, email/label, status badge, created date, actions
- Copy-to-clipboard button for invite URL
- Revoke button with confirmation
- Status badges: pending (yellow), redeemed (green), revoked (red)

## Boundary

- Does not handle invite redemption (see `session-auth`)
- Does not handle frontend auth checks (see `auth-frontend-gate`)
- Admin endpoints are unprotected (admin access is internal-only)

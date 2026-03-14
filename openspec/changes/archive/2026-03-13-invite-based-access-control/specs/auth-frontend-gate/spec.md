# Auth Frontend Gate

## Purpose

Frontend authentication wrapper that protects all pages, handles invite redemption flow, and provides user context (patient_id) to components.

## Requirements

### Auth Context Provider

- React context `AuthContext` providing: `{ user, isLoading, isAuthenticated, logout }`
- `user` shape: `{ patient_id: string, display_name?: string, email?: string }`
- On mount: reads `session_token` from localStorage, calls `GET /api/auth/verify`
  - If valid: sets user in context
  - If invalid or missing: clears localStorage, sets user to null
- `logout()`: clears localStorage, sets user to null
- Wrapper component `AuthProvider` used in the base layout

### Auth Gate Component

- `AuthGate` component wraps page content
- If `isLoading`: shows loading spinner
- If `!isAuthenticated`: redirects to `/` (landing page)
- If `isAuthenticated`: renders children
- Used in all page layouts except landing page and invite page

### API Client Update

- Update `frontend/src/lib/api.ts` to include auth token in all requests
- Read `session_token` from localStorage
- Add `Authorization: Bearer {token}` header to all fetch calls
- On 401 response: clear localStorage, redirect to landing page

### Pages

**Landing Page `/` (updated)**
- If authenticated: redirect to `/chat`
- If not authenticated: show welcome message — "Welcome to SynapseFlow", brief platform description, "If you have an invite link, click it to get started."
- No navigation links to app pages
- Clean, minimal design consistent with existing dark theme

**Invite Redemption `/invite/[token]`**
- New Astro page with React component
- On mount: calls `POST /api/auth/redeem/{token}`
  - If success: stores `session_token` in localStorage, redirects to `/chat`
  - If error: shows "Invalid or expired invite link" message with link back to landing
- Uses `getStaticPaths` returning empty array (SSR-rendered or catch-all)

**Chat `/chat` (replaces `/chat/[patientId]`)**
- Single page, no more static patient ID paths
- Gets `patient_id` from `AuthContext`
- Passes `patient_id` to `ChatInterface` component
- Protected by `AuthGate`

**All other pages** (`/admin/*`, `/graph`, `/dda/*`)
- Wrapped in `AuthGate` — accessible to any authenticated user
- No changes to page content, just auth wrapper added

### Navigation

- Add user indicator in the header/nav: display_name or email, with logout button
- Visible on all authenticated pages

## Boundary

- Does not implement backend auth (see `session-auth`)
- Does not manage invites (see `invite-management`)
- Admin pages are auth-gated on the frontend but admin API endpoints remain unprotected on the backend

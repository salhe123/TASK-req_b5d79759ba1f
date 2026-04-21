# Field Service Membership & Data Governance System - API Specification

All endpoints are HTMX-driven. HTML partials are returned for `HX-Request` calls,
full pages for direct navigation. Write operations accept `application/x-www-form-urlencoded`
form payloads with a CSRF token (`csrf_token`). Responses use standard HTTP
status codes; business-rule violations return `409`, re-auth required returns
`423` (redirect to `/auth/reauth`), and validation errors return `400`.

Roles used below: `admin`, `manager`, `operator`, `viewer`.

---

## Main (`/`)

### GET `/`
Home / dashboard shell. Publicly reachable; redirects to login when session
expired.

### GET `/health`
Returns `{"status": "ok", "offline_mode": true}`. No auth required.

---

## Authentication (`/auth`)

### GET `/auth/login`
Renders the login form.

### POST `/auth/login`
Form fields: `username`, `password`, `remember` (optional).
- Success: sets session, records a trusted-device fingerprint, redirects to `/`.
- 5 failed attempts within the lockout window locks the account for 15 minutes.

### GET `/auth/reauth`
Renders the re-authentication form (required for sensitive actions after
30 minutes of inactivity).

### POST `/auth/reauth`
Form fields: `password`. Refreshes the `last_reauth_at` session timestamp.

### GET `/auth/logout` &nbsp; · &nbsp; POST `/auth/logout`
Invalidates the session and redirects to `/auth/login`.

### GET `/auth/devices`
Lists the current user's trusted devices (max 5 per user).

### POST `/auth/devices/<device_id>/remove`
Revokes a device from the current user's trusted list.

---

## Admin (`/admin`) &nbsp; — `admin` only

### GET `/admin/`
Admin dashboard: totals, open anomalies, SLA snapshot.

### GET `/admin/users`
User directory with filters (`role`, `status`, `q`).

### POST `/admin/users/<user_id>/activate`
### POST `/admin/users/<user_id>/deactivate`
### POST `/admin/users/<user_id>/freeze`
### POST `/admin/users/<user_id>/unfreeze`
### POST `/admin/users/<user_id>/change-role`
Account-control mutations. All require re-auth for sensitive actions.

### GET `/admin/search-config` &nbsp; · &nbsp; POST `/admin/search-config`
Configure trending-search panels and no-result recommendation rules.

### GET `/admin/users/<user_id>/devices`
List a user's trusted devices.

### POST `/admin/devices/<device_id>/revoke`
### POST `/admin/users/<user_id>/devices/revoke-all`
Admin device revocation.

---

## Members (`/members`) &nbsp; — `admin`, `manager`, `operator`

### GET `/members/`
List + filter (`search`, `status`, `membership_type`, `tag`, `archived`, `page`).

### GET `/members/new` &nbsp; · &nbsp; POST `/members/new`
Create a new member profile.

### GET `/members/<id>`
Member detail, timeline, linked addresses.

### GET `/members/<id>/edit` &nbsp; · &nbsp; POST `/members/<id>/edit`
Edit member. Uses optimistic concurrency: hidden `version` field is validated
server-side; mismatch returns `409` with an edit-lock warning. A 60-second
client-side edit lock is advertised in the UI.

### POST `/members/<id>/delete`
Soft-delete (archive).

### POST `/members/<id>/restore`
Restore a soft-deleted record.

### POST `/members/validate-field`
Inline HTMX field validator used by the member form.

### POST `/members/<id>/tags`
Add a tag to a member.

### POST `/members/<id>/tags/<tag_name>/remove`
Remove a tag from a member.

---

## Member Workflow (`/members/<id>/...`)

### GET `/members/<id>/workflow`
Renders the guided workflow panel (available transitions).

### POST `/members/<id>/workflow/execute`
Form fields: `action` (`join`, `renew`, `upgrade`, `downgrade`, `deactivate`, `cancel`).
Applies the state-machine transition, records the timeline entry, and writes an
audit log. `400` on invalid transition, `409` on version mismatch.

### GET `/members/<id>/timeline`
Returns the member timeline partial (MM/DD/YYYY hh:mm AM/PM format).

---

## Dispatch (`/dispatch`)

### GET `/dispatch/members/<member_id>/addresses`
List a member's addresses.

### GET `/dispatch/members/<member_id>/addresses/new` &nbsp; · &nbsp; POST …/new
Create a member address. Coordinates can be entered manually or via the offline
floorplan-grid pin picker.

### GET `/dispatch/addresses/<address_id>/edit` &nbsp; · &nbsp; POST …/edit
Edit an address.

### POST `/dispatch/addresses/<address_id>/delete`
Delete an address.

### GET `/dispatch/eligibility`
Eligibility check page.

### GET `/dispatch/members/<member_id>/eligibility` &nbsp; · &nbsp; POST …/eligibility
Run an eligibility check for a member. Form fields: `latitude`, `longitude`, or
`address_id`. Returns `{eligible, distance_miles, max_radius_miles, region_match}`
as an HTMX partial. Default radius is 25 miles. Every check is logged to
`EligibilityLog`.

### GET `/dispatch/service-areas`
List admin-defined service areas.

### GET/POST `/dispatch/service-areas/new`
### GET/POST `/dispatch/service-areas/<area_id>/edit`
### POST `/dispatch/service-areas/<area_id>/delete`
Service-area CRUD (admin only).

### GET `/dispatch/site-addresses`
### GET/POST `/dispatch/site-addresses/new`
### GET/POST `/dispatch/site-addresses/<site_id>/edit`
### POST `/dispatch/site-addresses/<site_id>/delete`
Site address book (dispatch facilities, not tied to a member).

---

## Search (`/search`)

### GET `/search/`
Full-text search. Query params: `q`, `status`, `membership_type`, `tag`,
`category`, `date_from`, `date_to`, `page`. Returns highlighted matches;
records every query to `SearchLog` and tracks latency against the 2-second SLA.
On no-result queries, returns trending panels and nearby-tag/recent-member
recommendations.

### GET `/search/logs`
Admin-only search-log viewer.

---

## Audit (`/audit`) &nbsp; — `admin` only

### GET `/audit/`
Audit log viewer. Filters: `q`, `category`, `action`, `user_id`, `date_from`,
`date_to`, `page`.

### GET `/audit/alerts`
Open anomaly alerts (e.g. `READ_BURST`: >50 reads in 10 min).

### POST `/audit/alerts/<alert_id>/resolve`
Acknowledge/resolve an anomaly.

### GET `/audit/export`
Streams a CSV export of filtered audit logs
(`Content-Type: text/csv`). Export itself is audit-logged with the acting
user's identity.

---

## SLA (`/sla`) &nbsp; — `admin` only

### GET `/sla/`
SLA dashboard (rolling search latency, anomaly counters).

### GET `/sla/violations`
Paginated violation list.

### POST `/sla/violations/<violation_id>/acknowledge`
Acknowledge an SLA violation.

---

## Cleansing (`/cleansing`) &nbsp; — `admin` only

### GET `/cleansing/`
Cleansing console: templates + recent jobs.

### GET/POST `/cleansing/templates/new`
Create a new template (field mapping, missing-value rules, dedup threshold,
outlier flags, unit/date normalization, place-name standardization).

### GET `/cleansing/templates/<template_id>`
Template detail + versions.

### GET/POST `/cleansing/templates/<template_id>/edit`
Edits create a new version atomically (prior versions retained).

### POST `/cleansing/templates/<template_id>/delete`
Soft-delete a template.

### GET/POST `/cleansing/upload`
Upload a CSV; select a template; dispatch a cleansing job. Runs fully offline.

### GET `/cleansing/jobs/<job_id>`
Job detail: processed rows, duplicates removed, outliers flagged, masked
preview of sensitive fields.

---

## Error Envelope

| Code | Description |
|------|-------------|
| 400 | Validation error |
| 401 | Unauthorized (not logged in) |
| 403 | RBAC — role not permitted |
| 404 | Resource not found |
| 409 | Business-rule violation / optimistic-lock conflict |
| 423 | Re-authentication required for sensitive action |
| 500 | Internal error |

HTMX partials include an `HX-Trigger` header carrying flash-message events
(`flash:success`, `flash:danger`) which the client wires to the toast region.

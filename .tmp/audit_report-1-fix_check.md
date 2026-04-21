# Follow-Up Review of `audit_report-1.md` Issues

Date: 2026-04-21

## Scope and Boundary

- Re-verifies the 9 issues raised in `.tmp/audit_report-1.md` section 5 against the current Flask/HTMX/SQLite repository under `repo/`.
- Static analysis only. Did not start the app, Docker, or run tests.
- Every claim below cites a current file/line in this repo (not any prior project).

## Summary

- Fixed: 9
- Partially Fixed: 0
- Not Fixed: 0

## Issue-by-Issue Verification

### 1. Cleansing encryption is fail-open, allowing plaintext at rest
- Status: **Fixed**
- Rationale: Both the raw-data ingest path and the processed-output path now fail closed when `SQLCIPHER_ENABLED=True` (production). If `EncryptionService.encrypt()` raises, job creation returns an error and `execute_job` raises a `RuntimeError` rather than storing plaintext. Dev/test deployments fall back to plaintext only with an explicit log warning.
- Evidence:
  - `repo/app/services/cleansing_service.py:228-238` — `create_job` aborts with `'Encryption failed — cannot store sensitive data unencrypted: …'` when SQLCipher is required.
  - `repo/app/services/cleansing_service.py:315-329` — `execute_job` re-raises as `RuntimeError('Encryption failed — refusing to store results unencrypted: …')` when SQLCipher is required, so the outer `try/except` marks the job `failed` and no unencrypted output is committed.

### 2. SQLCipher key handling is inconsistent and likely incorrect
- Status: **Fixed**
- Rationale: DB-level and field-level keys are now fully separated. `_read_db_key` generates/reads a 32-byte random value serialized as hex and injects it into SQLCipher via `PRAGMA key = "x'...'"` (valid hex-bytes form) for every ORM connection. Fernet is used only for field-level encryption under its own key path.
- Evidence:
  - `repo/app/__init__.py:15-27` — `_read_db_key` writes `os.urandom(32).hex()` with `0o600` perms.
  - `repo/app/__init__.py:30-94` — `_setup_db_encryption` attaches the key on every SQLAlchemy `connect` event (`PRAGMA key`, `cipher_page_size`, `cipher_compatibility`) and self-tests `PRAGMA cipher_version` on the real engine. Production (`SQLCIPHER_ENABLED=True`) hard-fails if SQLCipher is not active.
  - `repo/app/config.py:21-29` — distinct `DB_ENCRYPTION_KEY_PATH` (hex) vs `FIELD_ENCRYPTION_KEY_PATH` (Fernet) configs.
  - `repo/app/services/encryption_service.py:19-36` — `EncryptionService` validates the Fernet key from `FIELD_ENCRYPTION_KEY_PATH` only.

### 3. Audit identity traceability is incomplete for required operations
- Status: **Fixed**
- Rationale: `AuditService.log` now resolves `username` from `user_id` automatically when callers omit it, so every persisted row carries the acting user identity. The admin CSV export includes both `User ID` and `Username` columns.
- Evidence:
  - `repo/app/services/audit_service.py:26-34` — lookup `User` by `user_id` and back-fill `username` when missing.
  - `repo/app/routes/audit.py:128-142` — CSV writer emits `User ID` and `Username` on every row; export is itself audited (`action='export'`).

### 4. “All CRUD/read” audit requirement is not fully implemented
- Status: **Fixed**
- Rationale: Restore now emits an audit event, and dispatch read paths log reads with acting user identity.
- Evidence:
  - `repo/app/services/member_service.py:159-171` — `restore` calls `MemberService._audit('restore', member, restored_by)`.
  - `repo/app/routes/dispatch.py:22-31` — `member_addresses` emits `AuditService.log(action='read', category='member', entity_type='address', …)` with `user_id`/`username`.
  - `repo/app/services/audit_service.py:55-68` — read anomaly detector counts `read`/`list`/`search`/`view` actions, which now see coverage across member, dispatch, search, and audit routes.

### 5. Prompt-specified dispatch “member and site address books” not fully modeled
- Status: **Fixed**
- Rationale: A separate `SiteAddress` entity, service, and full route set now exist alongside the member-bound `Address` model. Eligibility flows reference member addresses; site addresses are listed/managed via their own dispatch pages.
- Evidence:
  - `repo/app/models/address.py:31-55` — `SiteAddress` model with `name`, coords, `region`, `is_active`, `version`, `created_by`.
  - `repo/app/services/address_service.py:150-235` — `SiteAddressService` (create/update/delete/list) with optimistic locking and audit hooks.
  - `repo/app/routes/dispatch.py:283-360` — `/dispatch/site-addresses` (+ `/new`, `/<id>/edit`, `/<id>/delete`) routes registered on `dispatch_bp`.

### 6. Sensitive admin mutations are only partially re-auth gated
- Status: **Fixed**
- Rationale: All privileged admin mutations now carry `@sensitive_action_reauth`, including the previously-missed `activate`, `unfreeze`, `change-role`, `search-config`, `revoke-device`, and `revoke-all-devices`.
- Evidence:
  - `repo/app/routes/admin.py:28-32` (deactivate), `:50-53` (activate), `:68-71` (freeze), `:90-93` (unfreeze), `:108-111` (change-role), `:131-134` (search-config), `:187-190` (revoke-device), `:200-203` (revoke-all-devices).
  - `repo/app/routes/audit.py:89-92` — `/audit/export` is also reauth-gated.

### 7. Trusted-device fingerprint is weak/spoofable (Medium)
- Status: **Fixed**
- Rationale: The device identifier is now an HMAC-SHA256 of request header parts keyed by the server `SECRET_KEY`, so a replayed header set alone cannot forge a fingerprint without the server secret.
- Evidence:
  - `repo/app/services/device_service.py:135-153` — `generate_device_identifier` uses `hmac.new(secret.encode('utf-8'), raw.encode('utf-8'), hashlib.sha256).hexdigest()[:64]`.

### 8. Service area validation is permissive for invalid configs (Medium)
- Status: **Fixed**
- Rationale: `ServiceAreaService._validate_area` now enforces `area_type ∈ {region, radius}`, required `name`, required `region` for region-type, required `center_latitude`/`center_longitude` for radius-type, and radius bounds (`0 < radius ≤ 10000`). Both `create` and `update` call the validator before any commit.
- Evidence:
  - `repo/app/services/address_service.py:240-258` — `VALID_AREA_TYPES` whitelist and `_validate_area` implementation.
  - `repo/app/services/address_service.py:261-264` (create), `:313-316` (update) — validation gate before DB writes.

### 9. Template version update is not atomic (Medium)
- Status: **Fixed**
- Rationale: `update_template` now deactivates the old version but defers `commit` to `create_template`, so both operations land in a single transaction. A crash between the two steps leaves the session uncommitted rather than with an orphaned inactive-only state.
- Evidence:
  - `repo/app/services/cleansing_service.py:166-185` — comment `# Do NOT commit yet — let create_template commit both in one transaction`; `create_template` performs the single `db.session.commit()` at line 161.

## Final Assessment

All 9 previously reported issues from `audit_report-1.md` are addressed by code present in the current repository. File paths, line numbers, and semantics above match the Flask/HTMX/SQLite project under `repo/` (no Java/Spring paths). The static boundary still applies: runtime verification of SQLCipher on a production engine and browser-level UX polish remain manual checks per the original audit’s own scope note.

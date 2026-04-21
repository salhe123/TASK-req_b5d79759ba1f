# Test Coverage & README Audit Report

Stack under audit: Flask + HTMX + SQLite (Python 3.11, pytest). All tests run
inside Docker via `run_tests.sh` → `Dockerfile.test` with a 90% coverage gate.

---

## 1. Endpoint Inventory (method + path)

Generated from `repo/app/routes/*.py`. All paths are full (blueprint prefix
already included).

### Main (`main_bp`, no prefix)
| Method | Path | File:Line |
|---|---|---|
| GET | `/` | `repo/app/routes/main.py:6` |
| GET | `/health` | `repo/app/routes/main.py:11` |

### Authentication (`auth_bp`, prefix `/auth`)
| Method | Path | File:Line |
|---|---|---|
| GET, POST | `/auth/login` | `repo/app/routes/auth.py:12` |
| GET, POST | `/auth/reauth` | `repo/app/routes/auth.py:66` |
| GET, POST | `/auth/logout` | `repo/app/routes/auth.py:91` |
| GET | `/auth/devices` | `repo/app/routes/auth.py:100` |
| POST | `/auth/devices/<device_id>/remove` | `repo/app/routes/auth.py:114` |

### Members (`members_bp`, prefix `/members`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/members/` | `repo/app/routes/members.py:10` |
| GET, POST | `/members/new` | `repo/app/routes/members.py:57` |
| GET | `/members/<id>` | `repo/app/routes/members.py:93` |
| GET, POST | `/members/<id>/edit` | `repo/app/routes/members.py:121` |
| POST | `/members/<id>/delete` | `repo/app/routes/members.py:181` |
| POST | `/members/<id>/restore` | `repo/app/routes/members.py:198` |
| POST | `/members/validate-field` | `repo/app/routes/members.py:212` |
| POST | `/members/<id>/tags` | `repo/app/routes/members.py:248` |
| POST | `/members/<id>/tags/<tag_name>/remove` | `repo/app/routes/members.py:267` |

### Workflow (`workflow_bp`, prefix `/members`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/members/<id>/workflow` | `repo/app/routes/workflow.py:11` |
| POST | `/members/<id>/workflow/execute` | `repo/app/routes/workflow.py:42` |
| GET | `/members/<id>/timeline` | `repo/app/routes/workflow.py:78` |

### Dispatch (`dispatch_bp`, prefix `/dispatch`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/dispatch/members/<member_id>/addresses` | `repo/app/routes/dispatch.py:13` |
| GET, POST | `/dispatch/members/<member_id>/addresses/new` | `repo/app/routes/dispatch.py:41` |
| GET, POST | `/dispatch/addresses/<address_id>/edit` | `repo/app/routes/dispatch.py:69` |
| POST | `/dispatch/addresses/<address_id>/delete` | `repo/app/routes/dispatch.py:113` |
| GET | `/dispatch/eligibility` | `repo/app/routes/dispatch.py:143` |
| GET, POST | `/dispatch/members/<member_id>/eligibility` | `repo/app/routes/dispatch.py:153` |
| GET | `/dispatch/service-areas` | `repo/app/routes/dispatch.py:193` |
| GET, POST | `/dispatch/service-areas/new` | `repo/app/routes/dispatch.py:208` |
| GET, POST | `/dispatch/service-areas/<area_id>/edit` | `repo/app/routes/dispatch.py:228` |
| POST | `/dispatch/service-areas/<area_id>/delete` | `repo/app/routes/dispatch.py:266` |
| GET | `/dispatch/site-addresses` | `repo/app/routes/dispatch.py:283` |
| GET, POST | `/dispatch/site-addresses/new` | `repo/app/routes/dispatch.py:298` |
| GET, POST | `/dispatch/site-addresses/<site_id>/edit` | `repo/app/routes/dispatch.py:316` |
| POST | `/dispatch/site-addresses/<site_id>/delete` | `repo/app/routes/dispatch.py:356` |

### Search (`search_bp`, prefix `/search`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/search/` | `repo/app/routes/search.py:13` |
| GET | `/search/logs` | `repo/app/routes/search.py:83` |

### Audit (`audit_bp`, prefix `/audit`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/audit/` | `repo/app/routes/audit.py:14` |
| GET | `/audit/alerts` | `repo/app/routes/audit.py:60` |
| POST | `/audit/alerts/<alert_id>/resolve` | `repo/app/routes/audit.py:72` |
| GET | `/audit/export` | `repo/app/routes/audit.py:89` |

### SLA (`sla_bp`, prefix `/sla`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/sla/` | `repo/app/routes/sla.py:10` |
| GET | `/sla/violations` | `repo/app/routes/sla.py:19` |
| POST | `/sla/violations/<violation_id>/acknowledge` | `repo/app/routes/sla.py:38` |

### Cleansing (`cleansing_bp`, prefix `/cleansing`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/cleansing/` | `repo/app/routes/cleansing.py:12` |
| GET, POST | `/cleansing/templates/new` | `repo/app/routes/cleansing.py:32` |
| GET | `/cleansing/templates/<template_id>` | `repo/app/routes/cleansing.py:49` |
| GET, POST | `/cleansing/templates/<template_id>/edit` | `repo/app/routes/cleansing.py:64` |
| POST | `/cleansing/templates/<template_id>/delete` | `repo/app/routes/cleansing.py:97` |
| GET, POST | `/cleansing/upload` | `repo/app/routes/cleansing.py:111` |
| GET | `/cleansing/jobs/<job_id>` | `repo/app/routes/cleansing.py:157` |

### Admin (`admin_bp`, prefix `/admin`)
| Method | Path | File:Line |
|---|---|---|
| GET | `/admin/` | `repo/app/routes/admin.py:12` |
| GET | `/admin/users` | `repo/app/routes/admin.py:20` |
| POST | `/admin/users/<user_id>/deactivate` | `repo/app/routes/admin.py:28` |
| POST | `/admin/users/<user_id>/activate` | `repo/app/routes/admin.py:50` |
| POST | `/admin/users/<user_id>/freeze` | `repo/app/routes/admin.py:68` |
| POST | `/admin/users/<user_id>/unfreeze` | `repo/app/routes/admin.py:90` |
| POST | `/admin/users/<user_id>/change-role` | `repo/app/routes/admin.py:108` |
| GET, POST | `/admin/search-config` | `repo/app/routes/admin.py:131` |
| GET | `/admin/users/<user_id>/devices` | `repo/app/routes/admin.py:174` |
| POST | `/admin/devices/<device_id>/revoke` | `repo/app/routes/admin.py:187` |
| POST | `/admin/users/<user_id>/devices/revoke-all` | `repo/app/routes/admin.py:200` |

**Total endpoints: 53** (counting each `GET/POST` combined route once per path).

---

## 2. Per-Endpoint Test Coverage Mapping

`auth_client` is a pytest fixture in `tests/conftest.py` that logs in as
`admin`/`admin123` via `POST /auth/login`. Coverage tiers: **Covered** (direct
call + assertion), **Partially Covered** (RBAC/redirect assertion only, no
behavior assertion), **Indirect** (exercised transitively via the service-layer
unit test), **Not Covered** (no test hits this path).

### Main
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/` | Covered | `tests/integration/test_rbac_matrix.py` (all login flows land on `/`) |
| GET `/health` | Covered | `tests/integration/test_api.py:108` |

### Auth
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET/POST `/auth/login` | Covered | `tests/integration/test_api.py:34-101`, `tests/integration/test_failure_paths.py:34-53` (lockout after 5 attempts), `tests/frontend/test_htmx.py:20,39` |
| GET/POST `/auth/reauth` | Covered | `tests/integration/test_auth_reauth.py:9-31` (empty-password, wrong-password, success, `next=` redirect) |
| GET/POST `/auth/logout` | Covered | `tests/integration/test_auth_reauth.py:56`, `tests/integration/test_api.py:103` |
| GET `/auth/devices` | Covered | `tests/integration/test_auth_reauth.py:36` |
| POST `/auth/devices/<id>/remove` | Indirect | Device removal covered in `tests/unit/test_auth_service.py` / `test_new_services.py` at the service layer |

### Members
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/members/` | Covered | `tests/integration/test_api.py:216`, RBAC at `tests/integration/test_rbac_matrix.py:65-78` |
| GET/POST `/members/new` | Covered | `tests/integration/test_api.py:131,159,181`, validation-error paths `tests/integration/test_failure_paths.py:88-101`, `tests/integration/test_coverage_final.py:187-201` |
| GET `/members/<id>` | Covered | `tests/integration/test_api.py:222`, 404 path at `test_coverage_final.py:209` |
| GET/POST `/members/<id>/edit` | Covered | `tests/integration/test_failure_paths.py:106-121` (optimistic-lock conflict), `tests/integration/test_api.py:226`, 404 path `test_coverage_final.py:224` |
| POST `/members/<id>/delete` | Covered | RBAC allow/deny at `tests/integration/test_rbac_matrix.py:94-108`, 404 path `test_coverage_final.py:261` |
| POST `/members/<id>/restore` | Covered | `tests/integration/test_coverage_final.py:274` |
| POST `/members/validate-field` | Covered | `tests/unit/test_new_services.py:189-201`, `tests/integration/test_coverage_final.py:279-295` |
| POST `/members/<id>/tags` | Indirect | `tests/unit/test_member_service.py` covers `add_tag`/`remove_tag` at the service layer |
| POST `/members/<id>/tags/<tag>/remove` | Indirect | same |

### Workflow
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/members/<id>/workflow` | Covered | `tests/integration/test_rbac_matrix.py:114-118`, 404 path `tests/integration/test_coverage_90.py:196` |
| POST `/members/<id>/workflow/execute` | Covered | `tests/integration/test_api.py:240`, full lifecycle in `tests/e2e/test_full_workflow.py`, unit-level transitions in `tests/unit/test_workflow_service.py:16-100` |
| GET `/members/<id>/timeline` | Covered | `tests/integration/test_coverage_90.py:200` |

### Dispatch
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/dispatch/members/<id>/addresses` | Covered | `tests/integration/test_rbac_matrix.py:140-144`, 404 path `test_coverage_90.py:100` |
| GET/POST `/dispatch/members/<id>/addresses/new` | Covered | `tests/integration/test_coverage_90.py:68` |
| GET/POST `/dispatch/addresses/<id>/edit` | Covered | `tests/integration/test_coverage_90.py:81` |
| POST `/dispatch/addresses/<id>/delete` | Covered | `tests/integration/test_coverage_90.py:96` |
| GET `/dispatch/eligibility` | Covered | `tests/integration/test_coverage_boost.py:52`, RBAC `test_rbac_matrix.py:124-136` |
| GET/POST `/dispatch/members/<id>/eligibility` | Covered | `tests/integration/test_coverage_90.py:104`, region+radius logic in `tests/unit/test_eligibility_service.py:16-46` |
| GET `/dispatch/service-areas` | Covered | `tests/integration/test_coverage_boost.py:90` |
| GET/POST `/dispatch/service-areas/new` | Covered | `tests/integration/test_api.py:399`, `tests/integration/test_coverage_boost.py:94-98`, RBAC `test_rbac_matrix.py:235-239` |
| GET/POST `/dispatch/service-areas/<id>/edit` | Covered | `tests/integration/test_coverage_90.py:114` |
| POST `/dispatch/service-areas/<id>/delete` | Covered | `tests/integration/test_coverage_90.py:127`, RBAC `test_rbac_matrix.py:243` |
| GET `/dispatch/site-addresses` | Covered | `tests/integration/test_site_addresses.py:9` |
| GET/POST `/dispatch/site-addresses/new` | Covered | `tests/integration/test_site_addresses.py:14-27` (success + missing-name validation) |
| GET/POST `/dispatch/site-addresses/<id>/edit` | Covered | `tests/integration/test_coverage_90.py:131` |
| POST `/dispatch/site-addresses/<id>/delete` | Covered | `tests/integration/test_coverage_90.py:135` |

### Search
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/search/` | Covered | `tests/integration/test_api.py:441-466` (tag, keyword, HTMX partial), `tests/integration/test_coverage_boost.py:159-163` (date-range filters), `tests/frontend/test_htmx.py:204-222` (highlight + no-result recs), `tests/unit/test_search_service.py:23-83` |
| GET `/search/logs` | Covered | `tests/integration/test_coverage_boost.py:167`, `tests/e2e/test_full_workflow.py:175` |

### Audit
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/audit/` | Covered | `tests/integration/test_api.py:562-578` (query, category, date-range, anomalies filters), `tests/integration/test_coverage_boost.py:41-45`, RBAC `test_rbac_matrix.py:189-203`, `tests/frontend/test_htmx.py:230` |
| GET `/audit/alerts` | Covered | `tests/integration/test_coverage_boost.py:32-36` (both `resolved=0` and `resolved=1`) |
| POST `/audit/alerts/<id>/resolve` | Covered | `tests/integration/test_api.py:609` |
| GET `/audit/export` | **Covered** | `tests/integration/test_coverage_boost.py:16-29` — asserts `text/csv` MIME, attachment disposition, and date-filtered export |
| Anomaly rule (>50 reads/10 min) | Covered | `tests/unit/test_audit_service.py:22-49`, `tests/integration/test_failure_paths.py:332-354` |

### SLA
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/sla/` | Covered | `tests/integration/test_api.py:598`, RBAC `test_rbac_matrix.py:210-214` |
| GET `/sla/violations` | Covered | `tests/integration/test_api.py:605` |
| POST `/sla/violations/<id>/acknowledge` | Indirect | `tests/unit/test_sla_service.py` covers `acknowledge_violation` service method |
| 2-second @ 50k records target | Runtime-only | `tests/integration/test_performance.py:46-84` asserts ≤2000 ms on test hardware (hardware-dependent) |

### Cleansing
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/cleansing/` | Covered | `tests/integration/test_cleansing_routes.py:12`, RBAC `test_rbac_matrix.py:221-229` |
| GET/POST `/cleansing/templates/new` | Covered | `tests/integration/test_cleansing_routes.py:17-35`, `tests/integration/test_coverage_90.py:23`, `tests/integration/test_api.py:506` |
| GET `/cleansing/templates/<id>` | Covered | `tests/integration/test_coverage_boost.py:190` (404) |
| GET/POST `/cleansing/templates/<id>/edit` | Covered | `tests/integration/test_coverage_90.py:56` (404 path) |
| POST `/cleansing/templates/<id>/delete` | Covered | `tests/integration/test_coverage_90.py:60` |
| GET/POST `/cleansing/upload` | Covered | `tests/integration/test_cleansing_routes.py:62-71`, `tests/integration/test_api.py:487-527`, `tests/integration/test_coverage_90.py:35-49`, `tests/integration/test_coverage_boost.py:174-180` |
| GET `/cleansing/jobs/<id>` | Covered | `tests/integration/test_coverage_boost.py:186` (404) |
| Pipeline (dedup / outlier / unit / date / place normalization) | Covered | `tests/unit/test_cleansing_service.py:39-94`, `tests/e2e/test_full_workflow.py:182-234` |

### Admin
| Endpoint | Status | Test Reference(s) |
|---|---|---|
| GET `/admin/` | Covered | `tests/integration/test_api.py:547`, `tests/e2e/test_full_workflow.py:318`, RBAC `test_rbac_matrix.py:168-182` |
| GET `/admin/users` | Covered | `tests/integration/test_admin_routes.py:16` |
| POST `/admin/users/<id>/deactivate` | Covered | `tests/integration/test_admin_routes.py:60`, `tests/integration/test_coverage_90.py:153` |
| POST `/admin/users/<id>/activate` | Covered | `tests/integration/test_coverage_90.py:157` |
| POST `/admin/users/<id>/freeze` | Covered | `tests/integration/test_coverage_90.py:161-165` |
| POST `/admin/users/<id>/unfreeze` | Covered | `tests/integration/test_coverage_90.py:169` |
| POST `/admin/users/<id>/change-role` | Covered | `tests/integration/test_admin_routes.py:64`, `tests/integration/test_coverage_90.py:173` |
| GET/POST `/admin/search-config` | Covered | `tests/integration/test_admin_routes.py:105-115`, `tests/integration/test_coverage_final.py:20-30` |
| GET `/admin/users/<id>/devices` | Covered | `tests/integration/test_coverage_90.py:184` |
| POST `/admin/devices/<id>/revoke` | Covered | `tests/integration/test_coverage_90.py:188` |
| POST `/admin/users/<id>/devices/revoke-all` | Indirect | `tests/unit/test_new_services.py` covers `admin_revoke_all_devices` at the service layer |

---

## 3. Cross-Cutting Coverage

| Concern | Tests |
|---|---|
| RBAC matrix (4 roles × core routes) | `tests/integration/test_rbac_matrix.py` (entire file, 257 lines) |
| Session timeout + re-auth gate | `tests/integration/test_auth_reauth.py`, `tests/unit/test_auth_service.py:70-80` |
| Account lockout (5 attempts / 15 min) | `tests/integration/test_failure_paths.py:34-53`, `tests/unit/test_auth_service.py:34-41` |
| Optimistic concurrency | `tests/unit/test_member_service.py:42-49`, `tests/integration/test_failure_paths.py:106-121` |
| Eligibility region + radius | `tests/unit/test_eligibility_service.py` |
| FTS5 highlights + trending + no-result recs | `tests/unit/test_search_service.py`, `tests/frontend/test_htmx.py:196-222` |
| Audit anomaly (>50 reads/10 min) | `tests/unit/test_audit_service.py:22-49`, `tests/integration/test_failure_paths.py:332-354` |
| Cleansing fail-closed encryption | `tests/unit/test_cleansing_service.py` (covered via the explicit `SQLCIPHER_ENABLED` fallback branch) |
| Search SLA (≤2 s target) | `tests/integration/test_performance.py` |

---

## 4. Coverage Verdict

- Branch/line coverage target: **≥ 90%**, enforced by `run_tests.sh` inside Docker.
- Test totals (from `README.md` and directory count): **75 unit + 131 integration + 16 frontend + 6 e2e = 228 tests**.
- Endpoint-level: **50/53 endpoints have direct HTTP-level tests** (RBAC or behavior). The 3 endpoints classified **Indirect** (`/auth/devices/<id>/remove`, `/members/<id>/tags`, `/members/<id>/tags/<tag>/remove`, `/admin/users/<id>/devices/revoke-all`) are exercised through their service-layer methods in unit tests but not via direct HTTP calls.
- Score: **92 / 100** — high confidence on functional paths; minor deduction for the Indirect-only endpoints and the hardware-dependent search-SLA benchmark.

## 5. Identified Gaps / Suggested Additions

1. Add direct HTTP tests for the 3 Indirect endpoints above (one `client.post(...)` each; assert 200 + RBAC).
2. `tests/integration/test_performance.py` asserts a 2 s bound on the CI hardware — add metadata noting the reference environment so a regression on slower runners is interpretable, not a mystery failure.
3. The fail-closed encryption branch is verifiable unit-style but has no integration test that toggles `SQLCIPHER_ENABLED=True` in a test app and asserts the failure envelope bubbles to a 500/409. Worth a single integration test.
4. Cleansing template *versioning* atomicity (issue #9 in `audit_report-1.md`) has no dedicated test asserting that a failure between deactivation and new-version commit leaves the session rollback-clean.
5. The HTMX frontend suite asserts partial-response content but not `HX-Trigger` headers that the UI relies on for toasts — worth adding one regression test per flash category.

---

## 6. README Audit

File under review: `repo/README.md`

### Required elements
| Element | Present | Notes |
|---|---|---|
| Project title & brief description | ✅ | Top of file — domain described in first sentence. |
| Architecture & tech stack | ✅ | HTMX, Flask 3.0, SQLAlchemy 2.0, SQLite (FTS5), bcrypt, Docker. |
| Project structure tree | ✅ | Reflects `app/`, `tests/`, `docker-compose.yml`, `run_tests.sh`. |
| Prerequisites | ✅ (Docker) / ❌ (manual `pip install`) | See finding below. |
| Run instructions (Docker) | ✅ | `docker-compose up --build -d`. |
| Test instructions | ✅ | `chmod +x run_tests.sh && ./run_tests.sh`. |
| Seeded credentials | ✅ | 4 roles (admin/manager/operator/viewer). |
| `.env.example` reference | N/A | Project does not require one (offline, key files are generated on first run into `instance/`). |

### Findings

- **FINDING R-1 — forbidden manual dependency-install instruction.**
  - Location: `repo/README.md:82` — `pip install -r requirements.txt` in the "Local development (alternative)" block.
  - Rule: Dockerized projects must not instruct users to install deps locally.
  - Fix: Drop the "Local development" alternative block entirely; keep only the Docker path.
- **FINDING R-2 — README does not match the project template expected by the verification harness.**
  - Template (provided by the user) expects sections: Architecture & Tech Stack (Docker mandatory), Project Structure (sample tree with MANDATORY markers), Prerequisites (Docker only), Running the Application (build → `.env` copy note → access URLs → stop), Testing, Seeded Credentials (email / password columns).
  - Current README uses `username` instead of `email` columns and omits the `.env` copy note under "Running the Application".
  - Fix: Rewrite `README.md` to the template structure; keep the domain-specific credentials realistic to `seed.py` (which seeds by username, not email, so the row label should stay honest — this is one deliberate deviation worth flagging).
- **FINDING R-3 — Test counts should match actual test discovery.**
  - Current README claims 228 tests total. Matches line count and `repo/README.md:129`. If that ever drifts, the coverage report above is the source of truth.

### README verdict: **Partial Pass** — addresses nearly all required content but contains a forbidden `pip install` line and does not match the required template layout. Both are fixed by the README rewrite tracked separately.

---

## 7. Notes

- Static review only. `run_tests.sh` was not executed as part of this audit.
- Docker assets verified present: `repo/docker-compose.yml`, `repo/Dockerfile`, `repo/Dockerfile.test`, `repo/run_tests.sh` (with `set -euo pipefail`).

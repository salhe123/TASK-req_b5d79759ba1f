# Test Coverage & README Audit Report

Static inspection only. No tests, containers, scripts, or build commands were executed.

---

## Tests Check

The project is a **fullstack Flask + HTMX + SQLite** application. Materially relevant categories:

- **Unit tests** — appropriate for the service layer (auth, workflow, eligibility, search, audit, SLA, cleansing).
- **Integration / API tests** — required; the Flask routes are the primary surface and they return HTMX partials + CSV/HTML, not a pure JSON API.
- **Frontend (HTMX) tests** — appropriate since partials are the UI contract.
- **E2E tests** — required for a fullstack app; should exercise multi-module workflows without mocking the FE/BE boundary.

Present and non-trivial:

| Category | Files | Volume | Verdict |
|---|---|---|---|
| Unit | `tests/unit/*.py` (8 files, 771 lines) | 75 tests | Real assertions on service methods (password lockout, workflow transitions, FTS, dedup, anomaly rules). Not boilerplate. |
| Integration | `tests/integration/*.py` (10 files, ~2,370 lines) | 131 tests | Real `client.get/post` into the Flask app via the werkzeug test client. Asserts on body content, redirects, flash classes, CSV MIME, RBAC 403/redirects, optimistic-lock 409. Not mocked-away. |
| Frontend / HTMX | `tests/frontend/test_htmx.py` (293 lines) | 16 tests | Sends `HX-Request: true` and asserts partial HTML (highlighting, no-result recs, live update swaps). |
| E2E | `tests/e2e/test_full_workflow.py` (320 lines) | 6 tests | Cross-module flows: login → member lifecycle → timeline → dispatch eligibility → search → audit → cleansing. No transport mocks — uses the real Flask app. |

**`run_tests.sh` verification:** Exists at `repo/run_tests.sh`, uses `set -euo pipefail`, runs `docker build -f Dockerfile.test` then `docker run --rm fieldservice-tests`. No local Python, Node, or host deps required for the main flow. Primary test execution is Docker-first.

**Prompt-requirement traceability (spot check):**

| Prompt requirement | Tested by |
|---|---|
| 5-attempt / 15-min account lockout | `tests/integration/test_failure_paths.py:34-53`, `tests/unit/test_auth_service.py:34-41` |
| 30-min reauth for sensitive actions | `tests/integration/test_auth_reauth.py` |
| Optimistic concurrency (60-s edit lock) | `tests/unit/test_member_service.py:42-49`, `tests/integration/test_failure_paths.py:106-121` |
| Eligibility region + 25-mi radius | `tests/unit/test_eligibility_service.py:16-46` |
| FTS5 highlights + trending + no-result recs | `tests/unit/test_search_service.py`, `tests/frontend/test_htmx.py:196-222` |
| Audit anomaly (>50 reads / 10 min) | `tests/unit/test_audit_service.py:22-49`, `tests/integration/test_failure_paths.py:332-354` |
| Search SLA (≤2 s @ 50k) | `tests/integration/test_performance.py:46-84` (hardware-dependent) |
| RBAC across 4 roles × core routes | `tests/integration/test_rbac_matrix.py` (257 lines) |
| CSV audit export with identity columns | `tests/integration/test_coverage_boost.py:16-29` (asserts `text/csv` + date filter) |
| Cleansing dedup / outlier / units / place-name | `tests/unit/test_cleansing_service.py`, `tests/e2e/test_full_workflow.py:182-234` |

**Sufficiency:** Integration and E2E suites hit real routes through the Flask test client (no transport mocks). API-equivalent tests assert body content and headers, not just status codes. The suite gives genuine confidence on the shipped behavior rather than just shape.

---

## Test Coverage Score

**92 / 100**

---

## Score Rationale

The suite is broad (unit + integration + HTMX + E2E) and deep (228 tests, ~3,900 lines, 90% coverage gate enforced in `run_tests.sh`). Integration tests exercise real HTTP requests through the Flask test client and assert on meaningful response content, not shallow status codes. E2E tests chain 5+ modules with no mocks. `run_tests.sh` is Docker-first with no host-Python dependency. Points deducted for (a) a handful of endpoints covered only at the service layer, not via direct HTTP tests; (b) the search-SLA assertion being runtime/hardware-dependent; (c) no integration test that forces the fail-closed encryption branch.

---

## Key Gaps

1. **Direct HTTP tests missing for a few endpoints:** `POST /auth/devices/<id>/remove`, `POST /members/<id>/tags`, `POST /members/<id>/tags/<tag>/remove`, `POST /admin/users/<id>/devices/revoke-all` — exercised via service-layer unit tests only.
2. **Fail-closed encryption path not integration-tested:** The production branch that refuses to persist cleansing data when `SQLCIPHER_ENABLED=True` and Fernet init fails is covered only via the fallback-log branch in unit tests; no test toggles `SQLCIPHER_ENABLED` at app-create time to verify the 500/error envelope.
3. **Search SLA benchmark is hardware-dependent:** `test_performance.py` asserts ≤2000 ms, but the reference environment isn't documented, making regressions hard to diagnose on slower CI runners.
4. **HTMX `HX-Trigger` headers not asserted:** Frontend tests validate partial HTML but not the `HX-Trigger` events the client uses for flash toasts — a regression here would silently break UI feedback.
5. **Template-version atomicity is not dedicated-tested:** Audit issue A9 (cleansing template deactivation + new-version commit being one transaction) has no explicit rollback-on-failure test.

---

## README Audit

File: `repo/README.md`

- **Required template elements present:** title + brief description, Architecture & Tech Stack (Docker marked Required), Project Structure tree (with MANDATORY markers on `docker-compose.yml`, `run_tests.sh`, `README.md`), Prerequisites (Docker only), Running the Application (build → seed → access → stop), Testing (`chmod +x && ./run_tests.sh`), Seeded Credentials table.
- **No forbidden manual dependency-install instructions** — the earlier `pip install -r requirements.txt` under a "Local development" block has been removed. `pip install` still appears in `Dockerfile` / `Dockerfile.test`, which is expected and permitted (image build, not a user instruction).
- **One deliberate deviation from the sample template:** Seeded Credentials uses a `Username` column instead of `Email`, because authentication in this app is offline username/password (see `repo/seed.py:15-45` and `POST /auth/login`). The email column would misrepresent the login identity.

**README verdict: Pass.**

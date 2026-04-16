# Field Service Membership & Data Governance System

A fully offline, production-grade web application for managing field service memberships, service eligibility, and data governance. The system supports secure authentication with RBAC, member lifecycle management, address-based dispatch eligibility, full-text search, comprehensive audit logging, SLA monitoring, and offline CSV data cleansing with versioned templates.

## Architecture & Tech Stack

- **Frontend:** HTMX 1.9.12, Jinja2 Templates, Custom CSS
- **Backend:** Python 3.11, Flask 3.0, Flask-Login, Flask-WTF
- **Database:** SQLite (with FTS5 full-text search)
- **ORM:** SQLAlchemy 2.0
- **Authentication:** bcrypt password hashing, session-based auth
- **Containerization:** Docker & Docker Compose (Required)

## Project Structure

```
.
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Dev/Test/Production configuration
│   ├── extensions.py            # SQLAlchemy, Flask-Login initialization
│   ├── middleware.py             # RBAC decorators, session timeout
│   ├── models/                  # Database models
│   │   ├── user.py              # User, Role, TrustedDevice
│   │   ├── member.py            # Member, Tag
│   │   ├── workflow.py          # MemberTimeline
│   │   ├── address.py           # Address, ServiceArea, EligibilityLog
│   │   ├── search.py            # SearchLog, FTS5 setup
│   │   ├── audit.py             # AuditLog, AnomalyAlert
│   │   ├── sla.py               # SLAMetric, SLAViolation
│   │   └── cleansing.py         # CleansingTemplate, CleansingJob
│   ├── services/                # Business logic layer
│   │   ├── auth_service.py      # Authentication, lockout, sessions
│   │   ├── member_service.py    # Member CRUD, tags, optimistic locking
│   │   ├── workflow_service.py  # State machine, lifecycle transitions
│   │   ├── address_service.py   # Addresses, service areas, eligibility
│   │   ├── search_service.py    # FTS5 search, trending, recommendations
│   │   ├── audit_service.py     # Audit logging, anomaly detection
│   │   ├── sla_service.py       # SLA metrics, violation tracking
│   │   ├── cleansing_service.py # CSV pipeline, dedup, formatting
│   │   ├── device_service.py    # Trusted device management
│   │   └── admin_service.py     # Dashboard data aggregation
│   ├── routes/                  # Flask blueprints (API endpoints)
│   │   ├── auth.py              # Login, logout, device management
│   │   ├── members.py           # Member CRUD routes
│   │   ├── workflow.py          # Workflow transitions, timeline
│   │   ├── dispatch.py          # Addresses, eligibility checks
│   │   ├── search.py            # Full-text search
│   │   ├── audit.py             # Audit logs, anomaly alerts
│   │   ├── sla.py               # SLA dashboard, violations
│   │   ├── cleansing.py         # CSV upload, template management
│   │   ├── admin.py             # Admin dashboard
│   │   └── main.py              # Index, health check
│   ├── templates/               # Jinja2 HTML templates (HTMX-enabled)
│   └── static/                  # CSS, HTMX JS (bundled for offline use)
├── tests/
│   ├── conftest.py              # Shared pytest fixtures
│   ├── unit/                    # Service-layer unit tests (75 tests)
│   ├── integration/             # API endpoint tests (131 tests)
│   ├── frontend/                # HTMX partial response tests (16 tests)
│   └── e2e/                     # Full workflow E2E tests (6 tests)
├── docker-compose.yml           # Multi-container orchestration - MANDATORY
├── Dockerfile                   # Production image
├── Dockerfile.test              # Test runner image
├── run_tests.sh                 # Standardized test execution script - MANDATORY
├── run.py                       # Application entry point
├── seed.py                      # Database seeding script
├── requirements.txt             # Python dependencies
└── README.md                    # Project documentation - MANDATORY
```

## Prerequisites

Docker is the **recommended** deployment method for a consistent environment. For local development, you can also run the app directly with Python 3.11+.

**Docker (recommended):**
- **Docker**
- **Docker Compose**

**Local development (alternative):**
- Python 3.11+
- `pip install -r requirements.txt`
- `python run.py` (starts on http://localhost:5000, uses development config)

## Running the Application

**Build and Start Containers:** Use Docker Compose to build the images and spin up the application.

```bash
docker-compose up --build -d
```

**Seed the Database (first run):** The application auto-creates tables on startup. To populate default roles and test users (the seed script automatically uses the `FLASK_CONFIG` environment variable set in docker-compose, so it seeds the correct production database):

```bash
docker exec fieldservice-app python seed.py
```

**Access the App:**

- **Application:** http://localhost:5000
- **Health Check:** http://localhost:5000/health

**Stop the Application:**

```bash
docker-compose down -v
```

## Testing

All unit, integration, frontend, and E2E tests are executed via a single, standardized shell script. This script automatically handles container orchestration for the test environment.

Make sure the script is executable, then run it:

```bash
chmod +x run_tests.sh
./run_tests.sh
```

**Test Summary:**

| Suite | Count | Description |
|-------|-------|-------------|
| Unit Tests | 75 | Service-layer logic: auth, members, workflow, eligibility, search, audit, cleansing, SLA |
| Integration Tests | 131 | Deep DB-state assertions, RBAC permission matrix (4 roles x all routes), failure/edge paths |
| Frontend Tests | 16 | HTMX partial responses, form submissions, live updates |
| E2E Tests | 6 | Full cross-module workflows with audit/timeline/SLA/eligibility log verification |
| **Total** | **228** | **90% code coverage** |

The `run_tests.sh` script outputs a standard exit code (`0` for success, non-zero for failure) to integrate smoothly with CI/CD validators. Coverage threshold is enforced at 90%.

## Seeded Credentials

The database is pre-seeded with the following test users via `seed.py`. Use these credentials to verify authentication and role-based access controls.

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Admin | `admin` | `admin123` | Full access to all system modules including admin dashboard, audit logs, SLA monitoring, and data cleansing. |
| Manager | `manager1` | `pass123` | Can manage members, dispatch, search, and view reports. Cannot access admin-only features. |
| Operator | `operator1` | `pass123` | Can create and manage members, execute workflow transitions. No access to dispatch overview or admin. |
| Viewer | `viewer1` | `pass123` | Can view the dashboard only. Cannot access members, dispatch, or any management features. |



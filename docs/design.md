# Field Service Membership & Data Governance System - System Design Document

## 1. Overview

The Field Service Membership & Data Governance System is a fully offline full-stack platform built with Flask, HTMX, and SQLite to manage secure account access, member lifecycle operations, searchable records, auditable activity tracking, offline data cleansing, and address-based service eligibility workflows.

The system supports three primary roles: Member Desk, Dispatch, and Admin. It is designed for local deployment without internet dependency, with strict auditability, controlled business state transitions, and operational safeguards for sensitive data handling.

Core functionality includes member profile and lifecycle management, offline address and service-area validation, full-text record search with recommendations, trusted-device-aware authentication, anomaly monitoring, SLA tracking, and versioned CSV data cleansing pipelines.

---

## 2. Architecture

### 2.1 Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML, CSS, JavaScript, HTMX |
| Backend | Flask (Python) |
| Database | SQLite |
| Security | Adaptive password hashing + RBAC |
| Deployment | Fully offline local deployment |
| Storage | SQLite + local filesystem |
| Search | SQLite Full-Text Search |

### 2.2 High-Level Architecture

```text
Staff Clients (Member Desk / Dispatch / Admin)
        |
        | HTMX Requests + REST-style Endpoints
        v
Authentication + RBAC Middleware
        |
        v
Flask Route Layer
        |
        v
Service Layer (Business Logic / Validation / Auditing)
        |
        v
Data Access Layer
        |
        v
SQLite Database + Local File Storage





### 2.3 Module Structure

- `auth` – authentication, password hashing, session handling, trusted devices
- `member` – member profiles, lifecycle workflows, tagging
- `dispatch` – address book, coordinates, eligibility checks
- `search` – full-text search, trending, recommendations
- `audit` – activity logs, anomaly detection
- `sla` – performance monitoring and alerts
- `cleansing` – CSV import, templates, data standardization
- `admin` – configuration, service areas, dashboard
- `common` – utilities, validation, error handling

---

## 3. Security Model

### 3.1 Authentication

- Local username/password authentication only
- Adaptive password hashing (e.g., bcrypt)
- Minimum password complexity enforced
- Account lock after 5 failed attempts (15 minutes)
- Session timeout after inactivity (30 minutes)
- Maximum 5 trusted devices per user

### 3.2 Roles and Permissions

| Role | Description |
|------|-------------|
| MEMBER_DESK | Manage members and lifecycle workflows |
| DISPATCH | Manage addresses and service eligibility |
| ADMIN | Full system control, audit, SLA, cleansing, configuration |

### 3.3 Security Rules

- Sensitive fields are masked in UI
- All operations logged in audit system
- Re-authentication required for sensitive actions
- Sensitive data encrypted or hashed locally

---

## 4. Core Modules

### 4.1 Member Module

- Create, update, delete member profiles
- Assign tags and organization links
- Maintain member status

### 4.2 Member Workflow Module

- Join, renew, upgrade, downgrade, deactivate, cancel
- Controlled state transitions
- Timeline tracking for changes

### 4.3 Dispatch Module

- Address book management
- Coordinate-based location entry
- Region-based and radius-based validation

### 4.4 Search Module

- Full-text search across records
- Keyword highlighting
- Trending searches tracking
- Recommendation system

### 4.5 Audit Module

- Log all system activities
- Track CRUD operations
- Detect anomalies (e.g., excessive reads)

### 4.6 SLA Module

- Monitor system performance
- Track search latency
- Trigger alerts on threshold violations

### 4.7 Data Cleansing Module

- Import CSV files offline
- Field mapping and transformation
- Deduplication using thresholds
- Standardize formats (dates, units, currency)
- Template versioning

---

## 5. Data Model

- `User` → authentication and roles
- `Member` → main entity with lifecycle states
- `Address` → linked to members
- `ServiceArea` → eligibility rules (region/radius)
- `AuditLog` → records all operations
- `CleansingTemplate` → reusable rules
- `CleansingJob` → execution tracking

---

## 6. Business Rules Engine

### Member Rules

- Lifecycle must follow valid transitions
- Updates use optimistic locking
- Timeline logs required for all changes

### Dispatch Rules

- Eligibility based on:
  - Region match OR
  - Radius (default 25 miles)
- All checks logged

### Search Rules

- Full-text search with ranking
- Trending based on usage logs
- Recommendations for failed queries

### Cleansing Rules

- Deduplication via configurable threshold
- Missing value handling rules
- Standardized formats enforced

---

## 7. Error Handling

| Code | Description |
|------|-------------|
| 400 | Validation error |
| 401 | Unauthorized |
| 403 | Access denied |
| 404 | Resource not found |
| 409 | Business rule violation |
| 423 | Locked / re-authentication required |
| 500 | Internal system error |

---

## 8. Deployment

- Fully offline deployment
- SQLite as local database
- No external API dependencies
- Local filesystem for storage

---

## 9. Testing Strategy

- Unit tests for service layer
- API integration tests
- Member lifecycle validation tests
- Search performance tests (up to 50k records)
- Audit and anomaly detection tests
- Data cleansing validation tests
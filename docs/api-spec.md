# Field Service Membership & Data Governance System - API Specification

## Authentication (`/api/auth`)

### POST `/login`
Request:
{
  "username": "admin",
  "password": "SecurePass123!"
}

Response:
{
  "accessToken": "jwt-token",
  "expiresIn": 1800,
  "role": "ADMIN"
}

Errors:
- 409 invalid credentials
- 409 account locked (5 attempts → 15 min)

---

### POST `/refresh`
Response:
{
  "accessToken": "new-token",
  "expiresIn": 1800
}

---

### POST `/logout`
Response:
{
  "message": "Logged out"
}

---

### POST `/change-password`
Request:
{
  "oldPassword": "old",
  "newPassword": "new"
}

---

## Users (`/api/admin/users`)

### POST `/`
Create user:
{
  "username": "user1",
  "password": "Temp123!",
  "role": "DISPATCH"
}

---

### GET `/`
List users with filters:
- role
- status
- page
- size

---

### PUT `/{id}/freeze`
### PUT `/{id}/unfreeze`
### PUT `/{id}/unlock`

---

## Members (`/api/members`)

### POST `/`
{
  "fullName": "Amina Yusuf",
  "status": "ACTIVE",
  "tags": ["PRIORITY"]
}

---

### GET `/`
Filters:
- keyword
- status
- tag

---

### GET `/{id}`

---

### PUT `/{id}`
Uses optimistic locking

---

### DELETE `/{id}`

---

### GET `/{id}/timeline`

---

## Member Workflow (`/api/members/{id}/workflow`)

### POST `/join`
### POST `/renew`
### POST `/upgrade`
### POST `/downgrade`
### POST `/deactivate`
### POST `/cancel`

Response:
{
  "memberId": 1,
  "action": "JOIN",
  "statusAfter": "ACTIVE"
}

---

## Dispatch (`/api/dispatch/addresses`)

### POST `/`
{
  "memberId": 1,
  "label": "Main Site",
  "latitude": 40.7,
  "longitude": -74.0
}

---

### GET `/`
Filters:
- memberId
- region

---

### PUT `/{id}`
### DELETE `/{id}`

---

## Eligibility (`/api/dispatch/eligibility`)

### POST `/check`
{
  "latitude": 40.7,
  "longitude": -74.0
}

Response:
{
  "eligible": true,
  "distanceMiles": 10,
  "maxRadiusMiles": 25
}

---

## Search (`/api/search`)

### GET `/`
?q=keyword

Response:
{
  "results": [
    {
      "type": "MEMBER",
      "title": "Amina Yusuf"
    }
  ]
}

---

### GET `/trending`
### GET `/recommendations`

---

## Audit (`/api/admin/audit`)

### GET `/logs`
Filters:
- userId
- action
- date range

---

### GET `/anomalies`
{
  "rule": "READ_BURST",
  "message": "50 reads in 10 min"
}

---

## SLA (`/api/admin/sla`)

### GET `/metrics`
{
  "searchLatencyMs": 180,
  "status": "OK"
}

---

## Cleansing (`/api/admin/cleansing`)

### POST `/import`
Upload CSV

---

### POST `/templates`

---

### POST `/jobs/{id}/run`
{
  "processedRows": 1200,
  "deduplicated": 34
}

---

## Admin Dashboard (`/api/admin/dashboard`)

### GET `/`
{
  "totalUsers": 10,
  "totalMembers": 50000,
  "openAnomalies": 2
}

---

## Export (`/api/admin/exports`)

### POST `/audit`
{
  "dateFrom": "...",
  "dateTo": "..."
}
## Business Logic Questions Log

### 1. How is "offline system" defined?
- **Problem:** It is not fully explicit whether external APIs, cloud sync, or online map services are allowed.
- **My Understanding:** The entire system must run locally without requiring internet access.
- **Solution:** Use only local Flask services, SQLite storage, local reference tables, and offline floorplan/grid-based location tools; do not depend on external APIs or cloud services.

---

### 2. How does member lifecycle state management work?
- **Problem:** The prompt lists join, renew, upgrade, downgrade, deactivate, and cancel, but exact transition rules are not fully defined.
- **My Understanding:** Member records should follow controlled state transitions with validation and auditability.
- **Solution:** Define explicit lifecycle rules, for example active, renewed, upgraded, downgraded, deactivated, and canceled, and validate every transition on the server with timeline logging.

---

### 3. How are conflicting edits prevented?
- **Problem:** The prompt mentions optimistic concurrency and a 60-second edit lock warning, but conflict behavior is not fully specified.
- **My Understanding:** Only one editor should effectively save changes at a time, and stale updates must be rejected.
- **Solution:** Track record version numbers plus edit timestamps, show a 60-second warning when another edit session is active, and reject outdated submissions with a refresh-and-retry message.

---

### 4. How is service eligibility determined?
- **Problem:** Eligibility can depend on administrative region rules or dispatch radius, but precedence and validation details are unclear.
- **My Understanding:** A request is eligible if it matches configured region rules and/or falls within the allowed dispatch radius.
- **Solution:** Implement a deterministic eligibility engine that checks region membership first, then radius rules against stored coordinates, with a default maximum radius of 25 miles unless overridden by admin settings.

---

### 5. How should trusted device management work?
- **Problem:** The prompt says users can have up to 5 trusted devices, but device registration and replacement rules are not described.
- **My Understanding:** Devices should be locally registered per user and capped at 5 active trusted entries.
- **Solution:** Store device fingerprints locally, allow admins to revoke old devices, and block new device trust registration when the limit is reached unless one is removed.

---

### 6. What is the scope of anomaly detection and SLA monitoring?
- **Problem:** The prompt gives examples like more than 50 record reads in 10 minutes and search under 2 seconds for 50,000 records, but does not define a full monitoring model.
- **My Understanding:** The system needs rule-based local monitoring, not advanced ML-based analytics.
- **Solution:** Implement configurable threshold-based checks for audit events and response-time metrics, raise alerts in an on-screen admin console, and store alert history for review.

---

### 7. How complex should the offline CSV cleansing pipeline be?
- **Problem:** The prompt includes mapping, deduplication, missing-value rules, outlier flags, normalization, and reference-table standardization, which could become very broad.
- **My Understanding:** A practical first implementation should cover the required offline cleansing flow without overbuilding.
- **Solution:** Support CSV import, reusable versioned templates, field mapping, configurable deduplication thresholds, missing-value handling, USD and imperial normalization, date-time normalization, and place-name standardization using a local reference table.
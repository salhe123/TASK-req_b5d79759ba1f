# Follow-Up Review of Previously Reported Issues

Date: 2026-04-10

## Scope and Boundary

- Reviewed the previously reported issues from `.tmp/delivery-acceptance-architecture-audit.md`.
- Static analysis only.
- Did not start the project, run tests, run Docker, or perform browser/manual checks.
- Conclusions below are limited to what is provable from the current repository contents.

## Summary

- Fixed: 10
- Partially Fixed: 0
- Not Fixed: 0

## Issue-by-Issue Verification

### 1. Contract workflow states overwritten into derived `ACTIVE` / `EXPIRING_SOON` states
- Status: `Fixed`
- Rationale: The model now has a separate transient `displayStatus`, and the service populates that field without mutating persisted `contractStatus`. User pages and templates use `displayStatus` for presentation while workflow actions still key off `contractStatus`.
- Evidence:
  - `src/main/java/com/reclaim/portal/contracts/entity/ContractInstance.java:15`
  - `src/main/java/com/reclaim/portal/contracts/service/ContractService.java:324`
  - `src/main/java/com/reclaim/portal/contracts/service/ContractService.java:351`
  - `src/main/java/com/reclaim/portal/users/controller/UserPageController.java:137`
  - `src/main/resources/templates/contract/detail.html:30`
  - `src/main/resources/templates/contract/detail.html:140`
  - `src/test/java/com/reclaim/portal/service/ContractDisplayStatusTest.java:108`

### 2. Recommendation logic missing recent-search and review-sentiment signals
- Status: `Fixed`
- Rationale: Ranking now incorporates recent user search terms and a seller review-sentiment signal derived from rating distribution, in addition to the earlier seller and affinity factors.
- Evidence:
  - `src/main/java/com/reclaim/portal/search/service/RankingService.java:93`
  - `src/main/java/com/reclaim/portal/search/service/RankingService.java:146`
  - `src/main/java/com/reclaim/portal/search/service/RankingService.java:175`
  - `src/main/java/com/reclaim/portal/search/service/RankingService.java:203`
  - `src/test/java/com/reclaim/portal/service/RankingSignalsTest.java:99`
  - `src/test/java/com/reclaim/portal/service/RankingSignalsTest.java:141`
  - `README.md:111`

### 3. Project shipped with usable default JWT / refresh / encryption secrets
- Status: `Fixed`
- Rationale: Base config no longer provides fallback secrets, and startup validation now fails outside `dev`/`test` when required secrets are missing. Dedicated `dev` and `test` profile configs isolate non-production secrets.
- Evidence:
  - `src/main/resources/application.yml:32`
  - `src/main/java/com/reclaim/portal/common/config/SecuritySecretsValidator.java:30`
  - `src/main/resources/application-dev.yml:1`
  - `src/main/resources/application-test.yml:19`
  - `src/test/java/com/reclaim/portal/unit/SecuritySecretsValidatorTest.java:18`
  - `README.md:19`
  - `README.md:36`

### 4. Stored signatures not rendered in the printable final contract
- Status: `Fixed`
- Rationale: The printable page still renders the stored signature image and now the application includes a dedicated authenticated `/storage/**` controller that serves stored files through `StorageService`, preserving traversal checks and returning image content types. Web tests cover successful retrieval, auth protection, missing files, and traversal attempts.
- Evidence:
  - `src/main/java/com/reclaim/portal/users/controller/UserPageController.java:173`
  - `src/main/resources/templates/contract/print.html:261`
  - `src/main/java/com/reclaim/portal/storage/controller/StorageFileController.java:18`
  - `src/main/java/com/reclaim/portal/common/config/SecurityConfig.java:56`
  - `src/test/java/com/reclaim/portal/service/ContractSignaturePrintTest.java:106`
  - `src/test/java/com/reclaim/portal/web/StorageFileControllerTest.java:51`

### 5. Search click analytics likely double-counted on the search page
- Status: `Fixed`
- Rationale: The page-level duplicate click handler was removed and the search page now explicitly defers click tracking to the shared global handler in `app.js`. A new test also asserts single-record semantics for one click.
- Evidence:
  - `src/main/resources/templates/user/search.html:190`
  - `src/main/resources/static/js/app.js:448`
  - `src/test/java/com/reclaim/portal/service/AdminAnalyticsEnhancedTest.java:142`

### 6. Operational logging / observability too thin
- Status: `Fixed`
- Rationale: Centralized exception logging is now present in the global exception handler for validation, access-denied, not-found, business-rule, upload-size, and unexpected failures. Unexpected exceptions are logged at error level with the stack trace while the client response remains sanitized.
- Evidence:
  - `src/main/java/com/reclaim/portal/auth/service/AuthService.java:62`
  - `src/main/java/com/reclaim/portal/auth/service/AuthService.java:79`
  - `src/main/java/com/reclaim/portal/auth/service/AuthService.java:116`
  - `src/main/java/com/reclaim/portal/contracts/service/ContractService.java:186`
  - `src/main/java/com/reclaim/portal/orders/service/OrderService.java:115`
  - `src/main/java/com/reclaim/portal/storage/service/StorageService.java:105`
  - `src/main/java/com/reclaim/portal/common/config/SecuritySecretsValidator.java:56`
  - `src/main/java/com/reclaim/portal/common/exception/GlobalExceptionHandler.java:25`
  - `src/main/java/com/reclaim/portal/common/exception/GlobalExceptionHandler.java:70`
  - `src/test/java/com/reclaim/portal/unit/GlobalExceptionHandlerTest.java:54`

### 7. `/contracts/**` page routes returned templates without required model data
- Status: `Fixed`
- Rationale: The bare `/contracts/**` routes now redirect to the user-scoped routes that populate model data and apply authorization.
- Evidence:
  - `src/main/java/com/reclaim/portal/contracts/controller/ContractPageController.java:8`
  - `src/test/java/com/reclaim/portal/web/ContractPageRedirectTest.java:29`

### 8. Contract clause field parsing was naive and broke on commas / colons
- Status: `Fixed`
- Rationale: Parsing now prefers JSON object input and falls back to legacy `key=value` parsing only when needed. Required-field validation was also added for explicit structured inputs.
- Evidence:
  - `src/main/java/com/reclaim/portal/contracts/service/ContractService.java:454`
  - `src/main/java/com/reclaim/portal/contracts/service/ContractService.java:492`
  - `src/test/java/com/reclaim/portal/unit/ClauseFieldParsingTest.java:28`
  - `src/test/java/com/reclaim/portal/unit/ClauseFieldParsingTest.java:78`

### 9. Click analytics lost item names and lacked search-session context
- Status: `Fixed`
- Rationale: Search results are now returned together with a `searchLogId`, the user search page stores that ID on the results grid, and the shared click-tracking script includes it in the click payload. The service no longer depends on mutable “last search” state for correlating clicks, and dedicated tests cover search-session creation and linked click persistence.
- Evidence:
  - `src/main/java/com/reclaim/portal/admin/service/AdminService.java:155`
  - `src/main/java/com/reclaim/portal/admin/service/AdminService.java:178`
  - `src/test/java/com/reclaim/portal/service/AdminAnalyticsEnhancedTest.java:83`
  - `src/main/java/com/reclaim/portal/catalog/service/CatalogService.java:31`
  - `src/main/java/com/reclaim/portal/catalog/controller/CatalogApiController.java:31`
  - `src/main/java/com/reclaim/portal/users/controller/UserPageController.java:82`
  - `src/main/resources/templates/user/search.html:110`
  - `src/main/resources/static/js/app.js:455`
  - `src/main/java/com/reclaim/portal/catalog/controller/CatalogApiController.java:50`
  - `src/test/java/com/reclaim/portal/service/SearchClickContextTest.java:78`

### 10. Contract list exposed a status filter UI that was not implemented server-side
- Status: `Fixed`
- Rationale: The user contracts controller now accepts a `status` parameter and filters by either persisted workflow status or derived display status, matching the filter UI.
- Evidence:
  - `src/main/java/com/reclaim/portal/users/controller/UserPageController.java:130`
  - `src/main/resources/templates/contract/list.html:20`
  - `src/test/java/com/reclaim/portal/web/ContractPageRedirectTest.java:61`

## Final Assessment

All previously reported issues are now addressed by static code evidence in the repository, with new or updated tests covering the three items that were previously only partial.

Static boundary still applies:

- This recheck did not execute the project or tests.
- Browser-level rendering and full runtime integration remain manual verification items in general, but the prior three partial findings are now resolved by code paths and test artifacts present in the repo.
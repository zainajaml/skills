# Verification and completion gates

## Evidence rules

Record each check's command or manual procedure, repository/environment, result and supporting output/artifact without secrets. Use PASS, FAIL, BLOCKED, NOT RUN or NOT APPLICABLE. Explain why a check is not applicable; unused features do not require implementation. Never infer successful runtime behavior from compilation, a text scan, mock-only tests or a missing test command.

Fix actionable failures within scope and rerun affected checks. External credentials, production access and unavailable runtimes can block checks without blocking all useful work. Clearly separate implementation completeness, verification completeness and cutover readiness.

## Required checks

| Gate | Evidence required |
| --- | --- |
| Scope boundary | Every created or modified file is inside `<frontend-repo>` or `<backend-repo>` (or the reused source repo); no extra repositories or workspace-level files; nothing changed outside them (no global installs, system or user config); test containers and temp files removed; out-of-scope findings listed as follow-ups, not implemented |
| Source/canonical roots | Source and target roots match deployment evidence; no accidental duplicate-tree edits; independent repository roots and package/build boundaries |
| Architectural structure | Actual feature modules, thin routes/controllers, backend services/use cases, isolated persistence, frontend feature API/hooks, explicit public exports; no unnecessary empty layers |
| Type/build quality | Independent clean dependency installs, strict type checks, lint/format and production builds; valid framework runtime and route deep links |
| Functional parity | Every inventory workflow mapped and exercised, including forms, empty/error states, redirects, tenant/role changes, imports/exports and accessibility-sensitive interactions |
| Database | Fresh migrations plus realistic upgrade/baseline path, constraints/relations/indexes, transaction rollback and representative query behavior; only one active migration authority |
| Migration structure | Small ordered files (about one table per file; functions, triggers, views and policies separate); no single large dump migration; all apply in order to an empty database and roll back where supported |
| Schema coverage | `schema-coverage.md` lists every source table, constraint, index, sequence, enum, view, function, trigger, extension, cron job, webhook and policy as `done` or `retired` with reason; catalog diff of source vs target explained |
| Runtime API acceptance | Backend started against a fresh isolated test DB; every OpenAPI operation has a passing success case and a denied/error case; frontend smoke journeys pass against it |
| Rows/identities/files | Separate import results or explicit fresh-start decision; count/key/checksum/relationship reconciliation, identity mappings/session transition, imported password hashes verified by a real login for each hash format present (bcrypt, Argon2, Firebase scrypt or other) and the agreed fallback for unsupported formats, and sampled file access |
| Auth-schema detachment | Applies only when the agreed scope moves authentication off Supabase. Then: no remaining FKs to `auth.users`, no `auth.uid()`/`auth.jwt()` in target defaults/functions/policies, signup reproduces any side effects of former `auth.users` triggers (N/A when there were none). If Supabase Auth is explicitly retained, mark N/A with the user decision and instead verify the backend validates Supabase-issued tokens (issuer, audience, signature/JWKS) and maps users correctly |
| Database side effects | Every source `pg_cron` job, `pg_net`/HTTP call, database webhook and Vault secret mapped to a backend job/integration/secret or explicitly retired |
| Authorization | Positive and negative API tests for discovered RLS/policy cases, cross-tenant/ownership checks, list/count/bulk actions, files and privileged endpoints |
| Authentication | Required login/logout/signup/reset/verify/OAuth flows; expired/revoked sessions, refresh races, single-use tokens, multi-instance state, no URL-token leaks or known production secret defaults |
| API contracts | Spec parses, route coverage matches, validation/response/error schemas match live responses, stable operation IDs/security schemes and generated client compatibility |
| Payload format | Every JSON endpoint returns the standard success/error envelope via central interceptors/filters or middleware; documented exceptions only; OpenAPI wrapper schemas match live responses |
| Error handling and retries | Domain errors map to correct status/code; unknown errors return safe 500 with request ID; no empty catches; retries only on transient failures with attempt limit, backoff and idempotency; jobs end in a visible failed/dead-letter state |
| Circular dependencies | Cycle check (for example madge or dependency-cruiser) passes in both repositories and runs in CI; no undocumented `forwardRef` |
| Client behavior | Central transport with request/response interceptors that unwrap envelopes and normalize `ApiError`, timeout/cancel, error mapping, refresh retry bounds, file/no-body handling, cache isolation/invalidation and no raw API calls in presentation code |
| Integrations | Used email, jobs, webhook signatures/retries, AI/RAG, MCP issuer/discovery, realtime reconnect/role filtering and provider test behavior |
| Runtime security | Missing required deployed secrets fail startup; no privileged secrets in browser output/logs; CORS/CSRF/cookies/payload limits/abuse controls verified |
| Logging | Structured JSON logs in production, readable in development; every request logged once with request ID, route template, status and duration; errors logged once with stack and request ID; secrets, tokens, cookies and passwords redacted (tested); no `console.log` in application code |
| Email templates | (N/A if the app sends no email) Every source email inventoried and migrated with its content; all templates use the shared layout and the theme file derived from frontend tokens; email-safe HTML plus plain text; links use the configured frontend URL; render tests pass; each email previewed in Mailpit and visually compared with the frontend |
| Docker spin-up | From a clean state, `docker compose -f docker-compose.dev.yml up --build` starts database, migrations and API (plus worker/mail if used), all healthy; health, Swagger and one authenticated call respond; production image boots, passes healthcheck, runs as non-root and fails fast without required secrets |
| README | Root `README.md` in each repository covers prerequisites, env setup, Docker and non-Docker start, service URLs/ports, scripts, database, tests, logs, API docs, production and troubleshooting; every command was run successfully or marked unverified with a reason |
| Deployment | Actual selected production artifact runs, containers/config validate, readiness/networking/migrations work; no dev services exposed; backup/restore and rollback rehearsed where access permits |
| Cleanup | Classified remaining dependency/name/URL hits, obsolete shims removed, authoritative docs/config/lockfiles and canonical deployment paths |
| Unused code and folders | Unused-file/export/dependency tool clean or every remaining finding justified; no empty or placeholder folders; no scaffold demo code; `.env.example` matches config consumers; build and tests pass after removals |

## Minimum meaningful test suite

Use the selected stack's compatible testing tools. If no tests exist, add risk-based tests rather than skipping the gate. Prioritize:
- service/use-case tests for nontrivial domain rules and denied transitions;
- real isolated PostgreSQL integration tests for tenant filtering, joins, constraints, transactions and migration execution;
- HTTP endpoint tests for malformed payloads, auth, authorization, conflict and documented outputs;
- frontend component/form tests for field errors, pending/error states and permissions;
- browser E2E for login and each critical observed journey, including one failure/denied path;
- contract tests for representative success/error responses and CI route/spec coverage;
- import/reconciliation tests on sanitized fixtures and representative volume when available.

Example adversarial cases: user A reads user B's object; member attempts owner reassignment; tenant A filters for tenant B; anonymous downloads a private file; role downgrade invalidates access/cache/SSE; concurrent refresh produces safe session behavior; duplicate webhook does not duplicate a payment; interrupted import resumes without duplicated rows; multi-row mutation rolls back; production boot without secrets fails. Select cases based on actual features.

## Runtime API acceptance on a test database

Run this after implementation is otherwise complete, and again after any fix it triggers:

1. **Isolate.** Start a dedicated PostgreSQL for testing (for example a `test` service or profile in `docker-compose.dev.yml`, or a Testcontainers instance) with a database name such as `<backend_repo>_test` (the backend repository name in snake_case). Before any destructive step, assert that the connection target is the test database (name/host check); refuse to run if it points at a production or shared host.
2. **Build from zero.** Drop and recreate the test database, run every migration in order from empty, and confirm the run completes with no errors. Optionally run all down migrations and up again where the tool supports it.
3. **Load fixtures.** Seed deterministic, non-sensitive fixtures covering each role and tenant needed by the authorization matrix (for example owner, member, other-tenant user, admin, anonymous). Never use exported production data unless it is sanitized and the user approved it.
4. **Start the backend** in production-like mode (production build, validated config, test secrets) and wait for liveness and readiness. Confirm startup fails when a required secret is removed.
5. **Test every API.** Run the HTTP integration/contract suite against the running server. Generate the list of operations from the OpenAPI spec and require for each one: at least one success case validated against its response schema, and at least one failure case (validation error, unauthenticated, forbidden or cross-tenant as applicable). Exercise database triggers/functions through the APIs that depend on them and assert their effects (for example `updated_at` changes, profile created on signup, counters maintained). Report any operation without both cases as FAIL, unless the operation genuinely has no meaningful failure case (for example a public, parameterless health or version endpoint). In that case record NOT APPLICABLE for the failure test with a one-line reason in the coverage table; this exemption must be rare and never applies to endpoints that take input or require authentication.
6. **Start the frontend** against the running backend and run browser smoke tests for login and each critical journey, including one denied path.
7. **Record and tear down.** Save commands, the operation coverage table and results in `docs/migration/verification.md`, then stop containers and remove test data.

Use this operation coverage table:

| Operation ID | Method and path | Success test | Denied/error test | Result |
| --- | --- | --- | --- | --- |

Add a single script per repository (for example `npm run test:e2e:api` in the backend) that performs steps 1–5 so the check is repeatable in CI. If Docker or another required runtime is unavailable, mark this gate BLOCKED, list the exact commands to run, and do not call the migration complete.

## Scan both code and behavior

Search source, lockfiles, build/config, environment variable consumers, current docs and runtime network activity where available. Classify every remaining `@supabase`, `supabase.`, `.supabase.co`, `SUPABASE_*`, `@lovable.dev`, `lovable-tagger`, `LOVABLE_API_KEY`, `src/integrations/supabase`, `auth.uid()`/`auth.users` references, Deno-only APIs (`Deno.`, `esm.sh`), Lovable email/AI URLs, old issuer, SDK clone, `/api/query`, dynamic RPC, service-role client and legacy schema tool reference as:
- active runtime dependency;
- temporary compatibility path with exit condition;
- explicitly retained provider with user decision;
- historical migration/source evidence;
- test/generated artifact;
- dead code to remove after import/build checks.

Inspect aliases and semantics: SDK absence or renamed variables does not prove decoupling. Inspect frontend server modules for persistence/business logic even if browser code is clean. Inspect build outputs and network requests for secrets and unintended provider URLs without printing sensitive values. Do not delete historical evidence just to achieve zero grep matches.

## Common failure patterns

These patterns recur in partial Lovable/Supabase migrations. Use them as regression checks, not as assertions about the current project:

| Prior failure pattern | Required prevention/check |
| --- | --- |
| SDK removed but SDK-shaped facade and table-query endpoint remain | Domain DTO/API migration; inspect callers and remove adapter at exit gate |
| Business logic left in TanStack/Next frontend server | Inventory and transfer privileged use cases; allow only rendering/thin API adapters |
| Emails sent with default provider styling or old Supabase templates | Shared layout from frontend tokens; every template previewed and compared |
| Auth SMTP migrated but product mail/AI still uses Lovable | Trace each sender/gateway/template; test replacement and disclose retained provider |
| MCP tools use new API but OAuth trusts Supabase issuer | Verify metadata, issuer/audience and complete authorization flow together |
| Target schema exists but rows/files were never imported | Separate schema, rows, identities and objects evidence/reconciliation |
| Only some historical RLS behavior ported | Source policy/actor matrix and positive/negative tests; block affected feature completion |
| localStorage refresh, URL hash tokens, known secret defaults | Session redesign and explicit production security tests |
| OAuth state only in one process | Multi-instance callback/replay behavior test |
| Duplicate source trees and three schema authorities | Canonical root evidence and single active migration tool |
| Edge Function copied but still Deno-shaped or using a service-role client | Node-native handler, validated config, explicit authorization and HTTP tests |
| Signup trigger or `pg_cron` job silently lost | Auth-schema and side-effect inventory mapped and tested |
| Users forced to reset passwords unnecessarily | Hash formats inventoried; supported hashes imported and tested with a login per format; reset only for users whose format the target cannot verify |
| Lovable Vite preset removed before server runtime replaced | Trace build/plugin/server dependencies and prove replacement production runtime |
| Giant query/services/components, row types in UI | Module boundary review, focused files and domain contracts |
| Stale docs, naming, unused env, two lockfiles | Import-aware cleanup, one chosen manager, current setup/deploy docs |
| No timeout, duplicated session gates/headers | Central transport/session source with timeout/refresh/error/cache tests |
| Swagger exists but drifts from implementation | Generated/validated contract, route coverage and response tests |

## Final audit and overview report

When the work ends (complete, partial or blocked), write `docs/migration/report.md` and summarize it in the response. Produce a concise summary plus linked repository evidence:
1. Selected stack/versions, canonical repository destinations and architecture decisions.
2. Domain modules, actual trees, significant created/modified/removed files and boundary review.
3. Ledger: original behavior → endpoint/module/frontend/data change → test evidence → status.
4. API version/contract location, Swagger access, client generation/version update procedure.
5. Schema/migration owner and separate row, identity and storage import/reconciliation results.
6. Auth/session/authorization changes, security checks and any unresolved policy differences.
7. External integrations, frontend-server moves and explicitly retained providers.
8. Environment variable names (no values), dev/prod setup (how to spin up each repository, pointing to its root README), CI and deployment/cutover commands.
9. Tests performed with actual outcomes and blocked/not-run checks.
10. Remaining dependency references, temporary adapters, legacy docs/schema and disposition.
11. Cleanup: every removed file, folder, dependency, script and variable, with reason.
12. Limitations, rollback and exact remaining user/provider actions.

Call the migration complete only for the agreed scope when required evidence passes. If only code/config are prepared, say so. Do not label live data migrated, dependencies removed, or production ready based solely on an implementation plan. Any still-required compatibility facade, incomplete authorization, unimported required data/files or unverified critical auth flow blocks full migration sign-off.

Use this skeleton for `docs/migration/report.md` or the final response; omit sections that are NOT APPLICABLE with a one-line reason:

```markdown
# Migration audit and overview report: <frontend-repo> + <backend-repo>
Status: <complete for agreed scope | implemented, verification blocked | partial>
Date: <date>  Scope: <agreed scope and any retained providers>
Project profile: <origin, hosting mode, runtime, Supabase features used, auth model, tenancy, other clients, size>

## Overview
<3-6 sentences: what the app does, what was migrated, the target architecture, and whether it is ready for cutover.>

## Coverage at a glance
| Area | Total | Done/verified | Blocked | Retired/not applicable |
| --- | --- | --- | --- | --- |
| Workflows (ledger) | | | | |
| API operations (success + denied tests) | | | | |
| Schema objects (schema-coverage.md) | | | | |
| RLS policies → backend policies | | | | |
| Integrations / functions / jobs | | | | |
| Data rows / users / files reconciled | | | | |

## Gate results
| Gate | Result (PASS/FAIL/BLOCKED/NOT RUN/N/A) | Evidence |
| --- | --- | --- |

## Architecture
<repo trees (top two levels), modules per repo, API contract location, Swagger URL>

## Stack and repositories
| Repo | Path/remote | Framework/runtime | Package manager |
## Ledger summary
| ID | Original behavior | Endpoint/module | Frontend change | Tests | Status |
## Data, identity and files
| Workstream | Source/export used | Result | Reconciliation evidence | Status |
## Authorization
| Source policy | Target policy/test | Positive | Negative | Status |
## Integrations and retained providers
| Integration | Replacement | Verified with | Status |
## Environment variables (names only)
| Name | Repo | Public/secret | Required |
## Checks
| Check | Command/procedure | Result | Evidence |
## Remaining references
| Location | Classification | Action |
## Cleanup performed
| Repo | Removed path/package/variable | Kind | Reason | Evidence |
## Security audit
| Check | Result | Notes |
## Remaining risks and next actions
| Item | Owner (agent/user/provider) | Exact action |
## Limitations, rollback and user actions
```

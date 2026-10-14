---
name: lovable-supabase-migration
description: >-
  Analyze and migrate Lovable applications using Supabase into separate frontend
  and backend repositories with feature-based architecture. Support Next.js,
  React.js, or Vue.js frontends and Express.js or NestJS backends. Use for a
  complete migration, migration planning, or repair of a partial migration that
  still has Supabase-shaped clients, generic query endpoints, Lovable services,
  frontend business logic, or incomplete data and authorization migration. Works
  for any Lovable app (Lovable Cloud or own Supabase, Vite SPA or TanStack Start)
  and any Supabase-backed web app, whatever its domain, size or the parts of
  Supabase it uses.
---

# Lovable + Supabase migration

Rebuild the application around its actual domains and behavior. Preserve working user journeys, visual behavior, data integrity, and access rules while replacing platform coupling. Treat a source review as evidence to investigate, not proof about a different project.

## Portable execution

Use ordinary repository reads, edits, searches, shell commands, and questions available in the host agent. Do not require proprietary commands, plugins, MCP servers, agent delegation, or tool-specific frontmatter. Resolve reference links relative to this SKILL.md, not the application working directory. If a tool or external system is unavailable, continue with supported work and report the exact unverified dependency. Never claim a command, live audit, import, or deployment was performed when it was not.

Install this complete folder as `lovable-supabase-migration/` in the host's skills directory and keep `references/` beside SKILL.md. Common locations: `.claude/skills/` (Claude Code; Cursor also reads it), `.cursor/skills/` (Cursor), `.agents/skills/` or `.codex/skills/` (Codex and other Agent Skills hosts), or the personal `~/` equivalents. One copy in `.claude/skills/` covers Claude Code, Cursor and Codex. The core files are host-neutral; `agents/openai.yaml` is optional Codex/ChatGPT metadata that other hosts ignore. Start with: “Use lovable-supabase-migration to analyze this project, ask me for the target stack, and migrate it into separate modular repositories.”

## Adapt to the project

This skill is generic. It must work for any Lovable or Supabase application: any business domain, any size, any combination of Supabase features. Everything below is conditional on evidence from the current project:

- Classify the project first (the project profile in discovery.md) and drive every later decision from that profile, not from the examples in this skill.
- Apply a section only when the project uses that capability. When it does not (no auth, no storage, no realtime, no Edge Functions, no email, no AI, single user, no tenants), record it as NOT APPLICABLE with the evidence and move on. Never build infrastructure for an unused capability.
- Names in this skill (`projects`, `invitations`, tickets, `handle_new_user`, buckets, roles) are illustrations only. Use the project's own domains, tables, roles and terms.
- Scale the process to the app. A small app still passes every gate, but its plan, ledger and reports can be short; a large app migrates in feature batches with resumable evidence.
- The listed stacks (Next.js, React, Vue; Express, NestJS) are the supported branches. If the user explicitly asks for a different one (for example Fastify, Hono, Nuxt, SvelteKit or Angular), apply the same architecture, security and verification rules, say that it is outside the documented branches, and confirm the framework conventions from its official docs.
- When evidence contradicts this skill (a newer Lovable template, a different Supabase feature, an unusual layout), follow the evidence, record the difference, and ask the user if it changes scope.

## Scope boundary

All work stays inside exactly two target projects: `<frontend-repo>` and `<backend-repo>` (the frontend may be the reused source repository). Everything the migration needs is placed in one of them:

| Concern | Lives in |
| --- | --- |
| UI, routes, feature API client, generated API types, component/E2E tests | `<frontend-repo>` |
| API, business logic, database migrations/seeds, auth, jobs/workers, webhooks, integrations, Edge Function ports, MCP server, data/identity/file import scripts, OpenAPI spec, Docker Compose, test database setup, `docs/migration/` | `<backend-repo>` |

- Do not create any other repository or top-level folder: no shared/contracts/types package, infra/devops, docs, worker, MCP, migrations or monorepo root, and no files directly in the parent workspace folder. If something looks like it needs its own deployable (for example a worker), keep it in the backend as a separate entry point and Docker target.
- Treat the source repository as read-only, except when it is explicitly reused as `<frontend-repo>`.
- Do not change anything outside these projects: no global package installs, shell profiles, system or editor settings, hosts files, other projects, or user-level config. Temporary files go in the system temp directory and are deleted afterwards; Docker containers, networks and volumes for development and tests use the `<backend-repo>` name as prefix and test ones are removed after the run.
- Stay within the migration. Do not add new product features, redesign the UI, refactor or upgrade unrelated code, or migrate other clients (mobile apps, scripts, partner integrations). Record such findings in the final report as follow-ups and ask the user before expanding scope.

## Non-negotiable outcomes

- Analyze before choosing architecture; ask for the missing frontend and backend selection before scaffolding. Never silently default to any stack (for example Express/TypeORM/React) because it is common.
- Create independent frontend and backend repositories with their own manifests, lockfiles, configuration, tests, CI, and deployment boundaries. Two folders in one repository do not satisfy this requirement.
- Organize both applications by business feature. Keep transport, validation, business rules, persistence, and presentation distinct. No generic everything-service or global table-query API as the final architecture.
- Keep controllers and route/page files thin. Put queries in repositories/data access and rules in services/use cases. Do not wrap existing `supabase.from()` chains in differently named files and call the migration complete.
- Keep backend business logic, privileged integrations, jobs, and persistence out of the frontend repository. Next.js/SSR rendering and thin session/API adapters may remain there; duplicate business logic may not.
- Preserve required functionality. Remove a used capability only when the user explicitly changes scope. Missing credentials mean blocked verification, not “not used.”
- Treat schema creation, existing-row migration, authentication identity migration, and storage-object migration as four separate workstreams.
- Use one authoritative schema/migration history. Never run competing Supabase, Drizzle, and target ORM migration paths against the target database.
- Write migrations as small, ordered files: roughly one table per file, with enums/extensions, functions, triggers, views and policies in their own focused files. Never produce one large dump-style migration. Every source table, constraint, index, sequence, enum, view, function, trigger, extension, cron job and policy must map to a target migration file or a recorded decision (moved to backend code, or retired with a reason).
- Before handover, start the migrated backend (and frontend) against an isolated test database built from the migrations, and prove every documented API operation works with automated tests, including denied or error cases (a documented NOT APPLICABLE only for operations with no meaningful failure case). Never run this against production data.
- Preserve authorization previously enforced by RLS through explicit tested backend policies, or deliberately configured target database RLS with verified request context and connection-pool isolation. Tenant/ownership checks apply to every read/write, upload/download, job, integration, and realtime channel.
- Document and test OpenAPI throughout implementation. A Swagger UI shell alone is insufficient.
- Use one standard API payload format, applied centrally: backend response/error interceptors (or middleware) wrap every application JSON response, except documented protocol responses that must keep their own format (OAuth, MCP, third-party webhooks, health checks, files, streams, SSE, 204), and the frontend API client uses request/response interceptors. Controllers and components never hand-build envelopes or parse raw responses.
- Handle errors deliberately: typed domain errors, try/catch only where it adds value (translate, clean up, compensate, retry), one central error handler, and bounded retries with backoff only for transient failures of safe or idempotent operations. Never swallow errors or retry forever.
- No circular dependencies between modules, files or Nest providers in either repository; check with a tool in CI.
- Proper structured backend logging from the start: one JSON logger, levels via `LOG_LEVEL`, one request log line with request ID, route, status and duration, central redaction of secrets/tokens/personal data, no `console.log` in application code (see backend.md).
- Docker must spin up the APIs, not just the database: one `docker compose -f docker-compose.dev.yml up --build` in `<backend-repo>` starts the database, runs migrations, and starts the API (plus worker/mail only if used) with healthchecks; production uses a multi-stage, non-root image. Verify it actually starts (see deployment.md).
- When the app sends email, every template (auth and product emails) uses one shared email layout built from the frontend's real design tokens — logo, app name, brand colors converted to hex, font and button style — in email-safe HTML with a plain-text version, previewed in Mailpit (see data-security.md).
- Each repository has a root `README.md` that explains how to spin everything up — prerequisites, env setup, Docker and non-Docker start, service URLs and ports, scripts, database, tests, logs, API docs, production and troubleshooting — and every command in it has been run successfully.
- No browser database credentials, service-role keys, known deployed secret defaults, or tokens in redirect URLs. Never print secret values during audits.
- Leave no unused code in the target repositories: no empty or placeholder folders, unused files, components, exports, dependencies, scripts, environment variables, scaffold demo code, or leftover Supabase/Lovable folders. Run the unused-code pass in implementation.md before handover and list every removal in the final report. Archive historical evidence under `docs/migration/history/` instead of leaving it in active code.
- Keep changes reversible; preserve original code/history and migration evidence. Do not overwrite sibling directories or delete duplicate repositories on assumption.
- Do not claim complete/production-ready when data, permissions, platform dependencies, or required runtime verification remain unresolved.

## Load references at the relevant phase

| Phase | Required reference |
| --- | --- |
| Discovery and source evidence | [discovery.md](references/discovery.md) |
| Stack decisions, domain boundaries, directory trees (phase 3) | [architecture.md](references/architecture.md) + [data-security.md](references/data-security.md) |
| Express/NestJS, layers, API and OpenAPI | [backend.md](references/backend.md) |
| Next.js/React/Vue, state, forms, client and assets | [frontend.md](references/frontend.md) |
| Database, identities, authorization, integrations and files | [data-security.md](references/data-security.md) |
| Feature-by-feature implementation and cleanup | [implementation.md](references/implementation.md) |
| Environment, Docker, CI and cutover preparation | [deployment.md](references/deployment.md) |
| Acceptance gates, negative tests and final report | [verification.md](references/verification.md) |

## Workflow and gates

Copy this checklist into the response (or `docs/migration/plan.md`) and update it as gates pass. Do not skip a gate; mark a blocked gate BLOCKED with the reason.

```text
Migration progress:
- [ ] 1. Discover: project profile, hosting mode, canonical tree, capability inventory, schema/RLS/functions, baseline
- [ ] 2. Target stack and data/identity scope confirmed by the user
- [ ] 3. Architecture (12 decisions), trees, ledger, data-export path and plan presented
- [ ] 4. Foundations: separate repos, config, DB/migrations, auth, errors, health, OpenAPI, API client
- [ ] 5. Vertical features migrated one ledger ID at a time, with tests and OpenAPI
- [ ] 6. Data/identity/file import and deployment rehearsed in isolation
- [ ] 7. Verification gates, schema coverage, dependency scan, unused-code and empty-folder cleanup
- [ ] 8. App spun up on an isolated test DB; every API operation tested
- [ ] 9. Final audit and overview report delivered
```

### 1. Discover

Read discovery.md. Start by writing the project profile (origin, hosting mode, frontend runtime, Supabase features used, size, auth and tenancy model). Determine whether the backend is Lovable Cloud (Supabase hosted by Lovable, usually without dashboard or direct database access) or the user's own Supabase project, because this decides how schema, rows, users, files, functions and secrets can be exported. Determine the canonical source and deployed tree, framework/runtime, domains, integrations, Supabase use, schema, identity flows and permissions. Audit existing migration work before replacing it. Record file/function evidence, uncertainty, and live-service access limits. Establish baseline build and core-journey behavior where possible.

**Gate:** Produce an evidence-backed inventory and explicit unknowns. Do useful read-only analysis without waiting for stack selection. Resolve unknowns that affect an implementation slice before coding that slice; do not invent schema or authorization.

### 2. Ask for the target stack

After presenting concise findings, ask only unanswered choices:
1. Frontend: **Next.js**, **React.js**, or **Vue.js**.
2. Backend: **Express.js** or **NestJS**.
3. Data/identity scope: fully leave Supabase (default intended goal), or explicitly retain named managed capabilities? Must existing users, rows, and files carry over?
4. Repository names and location (always ask; never derive from the app name): the **frontend repository name** (or reuse the existing source repository as the frontend), the **backend repository name**, and the **parent folder** (default: the folder containing the source repository). Also ask about material hosting constraints, if unknown.

Reuse explicit session decisions. Recommend a database library, auth approach, routing setup, package manager and deployment profile with reasons; do not ask the user to choose every package. Keep PostgreSQL semantics by default; treat a database-engine change as additional scope. If answers are unavailable, deliver discovery and the choices needed; do not choose a stack silently.

### 3. Present architecture and migration plan

Read architecture.md, the applicable frontend/backend branches, and data-security.md (the plan must state the auth, identity, data-export and authorization approach). Before source implementation, present the 12-part architecture summary, actual proposed trees, repository paths, API/domain map, dependency choices, parity matrix, risks, test strategy, and sequenced migration plan. Identify retained dependencies explicitly. User authorization to migrate permits implementation after required choices and the plan are established; do not introduce repeated approval gates. A request for analysis/plan only stops here.

**Gate:** Every observed workflow maps to a target module and verification case. Every temporary adapter has a removal condition. Record substantive assumptions instead of hiding them.

### 4. Establish foundations

Create collision-safe sibling repositories using the frontend and backend repository names the user gave (`<frontend-repo>`, `<backend-repo>`) in the parent directory of the source repository's Git root (see architecture.md), unless the user named another destination, or use the authorized existing repository destinations. Preserve source history/worktrees and user edits. Do not nest backend inside frontend or initialize over an existing unrelated checkout. Add strict TypeScript, configuration validation, persistence/migrations, auth policy plumbing, errors/logging, health endpoints, API contract generation, central frontend client, and framework routing. Read data-security.md before selecting auth or moving data.

### 5. Migrate vertical features

Read implementation.md. For each feature: specify domain contract and permission cases; implement persistence, service, controller and documented endpoint; add feature API functions and hooks/composables; migrate views; verify positive/negative flows; remove replaced shims. Update the migration ledger. Migrate active frontend server functions, Lovable email/AI/MCP, background jobs, webhooks and edge functions as discovered. Do not defer all tests or OpenAPI until the end.

### 6. Rehearse data and deployment

Read deployment.md. Prepare and test schema/data/identity/file import in isolated targets, environment examples, independent builds, development containers and production deployment configuration. Rehearse backup/restore, compatibility rollout and rollback. Production cutover or destructive operations require authorization specific to that environment; preparation and isolated rehearsals do not require repeated approval.

### 7. Verify and hand over

Read verification.md. Run builds, types, lint, meaningful tests, contract checks, negative authorization tests, migration/data reconciliation, core UI flows, dependency scans and production-mode startup checks. Report PASS/FAIL/BLOCKED/NOT RUN/NOT APPLICABLE with evidence. Continue fixes within scope until gates pass or a real external blocker remains. Never count a missing test script as a passing test. Run the unused-code and empty-folder pass from implementation.md, then rebuild and retest.

### 8. Spin up and test every API on a test database

Follow the runtime acceptance procedure in verification.md: create a fresh isolated test database, apply all migrations from zero, load test fixtures, start the backend in production-like mode, and run the API suite so every OpenAPI operation has at least one passing success case and one failing/denied case (or a documented NOT APPLICABLE when no meaningful failure case exists). Then start the frontend against that backend and run the core journey smoke tests. Fix failures and rerun until green. If Docker or a database runtime is unavailable, mark this gate BLOCKED and provide the exact commands; never report it as passed.

### 9. Deliver the final audit and overview report

Write `docs/migration/report.md` from the template in verification.md and give the user a summary in the response: the overview, gate results table, coverage numbers, removed items, remaining risks and exact next actions. Every PASS must link to evidence; anything unverified is shown as BLOCKED or NOT RUN, never omitted.

## Keep resumable evidence

Maintain `docs/migration/` in the backend repository once implementation starts, with a short pointer from frontend documentation. During analysis-only work, present the same artifacts in the response unless files were requested.

- `discovery.md`: canonical roots, source evidence, runtime/capability inventory and baseline.
- `architecture.md`: all 12 decisions and proposed trees.
- `plan.md`: sequence, dependencies, rollback and open decisions.
- `schema-coverage.md`: every source database object → target migration file or backend code → test → status.
- `ledger.md`: source workflow → module/API → authorization → frontend → data/files → test evidence → status.
- `verification.md`: commands, results, runtime environment and blockers.
- `cutover.md`: operational sequence, backups, thresholds and rollback.
- `report.md`: final audit and overview report (template in verification.md), also summarized in the final response.

Ledger row shapes and the final report template are in [verification.md](references/verification.md) and [discovery.md](references/discovery.md).

On resume, read these artifacts and current changes, verify completed evidence is still applicable, and continue at the earliest unmet gate. Do not restart discovery or repeat resolved questions unnecessarily.

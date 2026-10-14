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

Use ordinary repository reads, edits, searches, shell commands, and questions available in the host agent. Do not require proprietary commands, plugins, MCP servers, agent delegation, or tool-specific frontmatter. Resolve reference and script links relative to this SKILL.md, not the application working directory. The read-only helpers in `scripts/` (schema catalog diff, auth hash format count, empty-folder finder) are referenced from the phase that uses them. If a tool or external system is unavailable, continue with supported work and report the exact unverified dependency. Never claim a command, live audit, import, or deployment was performed when it was not.

## Adapt to the project

This skill is generic. It must work for any Lovable or Supabase application: any business domain, any size, any combination of Supabase features. Everything below is conditional on evidence from the current project:

- Classify the project first (the project profile in discovery.md) and drive every later decision from that profile, not from the examples in this skill.
- Apply a section only when the project uses that capability. When it does not (no auth, no storage, no realtime, no Edge Functions, no email, no AI, single user, no tenants), record it as NOT APPLICABLE with the evidence and move on. Never build infrastructure for an unused capability.
- Names in this skill (`projects`, `invitations`, tickets, `handle_new_user`, buckets, roles) are illustrations only. Use the project's own domains, tables, roles and terms.
- Scale the process to the app. A small app passes every gate with lighter paperwork (see [Small projects](#small-projects)); a large app migrates in feature batches with resumable evidence.
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

Each rule is detailed in the linked reference; the reference wins on specifics.

- **Ask before choosing the stack.** Analyze first, then ask for the frontend and backend; never silently default to a common stack.
- **Two independent repositories,** each with its own manifest, lockfile, config, tests, CI and deployment. Two folders in one repository do not count ([architecture.md](references/architecture.md)).
- **Feature-based modules with thin controllers/routes.** Queries in repositories, rules in services/use cases, no generic everything-service or table-query API, and no renamed `supabase.from()` chains ([backend.md](references/backend.md), [frontend.md](references/frontend.md)).
- **No business logic in the frontend repo.** SSR rendering and thin session/API adapters only.
- **Preserve required functionality.** Drop a used capability only on an explicit scope change; missing credentials mean BLOCKED, not "not used".
- **Four separate data workstreams:** schema, existing rows, auth identities, storage objects ([data-security.md](references/data-security.md)).
- **One migration history of small ordered files** (about one table per file) with every source database object mapped in `schema-coverage.md` ([data-security.md](references/data-security.md)).
- **Authorization parity:** every RLS rule becomes a tested backend policy (or deliberately retained RLS), including files, jobs and realtime.
- **Every API operation tested** on an isolated test database with a success and a denied/error case; never against production data ([verification.md](references/verification.md)).
- **OpenAPI documented and tested as you go;** a Swagger UI shell alone is insufficient.
- **One payload envelope and deliberate error handling,** applied by central interceptors/middleware; typed domain errors, bounded retries for transient failures only ([backend.md](references/backend.md)).
- **No circular dependencies,** checked by a tool in CI.
- **Structured JSON logging from the start** with request IDs and central redaction; no `console.log` in application code.
- **One Docker command starts DB, migrations and API;** production image is multi-stage and non-root ([deployment.md](references/deployment.md)).
- **Emails (if any) share one layout built from the frontend's design tokens** ([data-security.md](references/data-security.md#email-templates-follow-the-apps-design)).
- **A root README per repository** whose every command was run ([deployment.md](references/deployment.md#root-readme-in-each-repository)).
- **No secrets in the browser, logs, URLs or reports;** no known deployed secret defaults.
- **No unused code or empty folders** at handover; every removal listed in the report ([implementation.md](references/implementation.md#unused-code-and-empty-folder-pass)).
- **Reversible and honest.** Preserve source history and evidence, never overwrite sibling directories, and never claim complete or production-ready while data, permissions, platform dependencies or runtime verification are unresolved.

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

## Small projects

A project is small when it has roughly ten tables or fewer, a handful of screens, one auth method, no multi-tenant model and no other clients. It still passes every gate; only the paperwork and structure shrink:

- Combine discovery, architecture, plan and ledger into one `docs/migration/plan.md`; schema coverage and cutover can be sections in it. Keep `verification.md` and `report.md` separate.
- Present the 12 architecture decisions as one line each; mark the ones that do not apply NOT APPLICABLE in a single list.
- Use the minimal module trees in backend.md and frontend.md without the optional files.
- Write API acceptance tests as table-driven cases: one table of operations with their success and denied/error inputs, rather than a test file per endpoint. Every operation still needs both cases.
- Omit report sections and README sections that do not apply, with a one-line reason.

Never shrink authorization tests, data/identity reconciliation, secret handling or the runtime API acceptance run.

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

The ledger row shape is in [discovery.md](references/discovery.md#deliver-evidence) and the final report template in [verification.md](references/verification.md#final-audit-and-overview-report).

On resume, read these artifacts and current changes, verify completed evidence is still applicable, and continue at the earliest unmet gate. Do not restart discovery or repeat resolved questions unnecessarily.

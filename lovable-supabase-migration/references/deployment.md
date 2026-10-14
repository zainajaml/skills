# Environment, containers, CI and cutover

## Configuration contract

Maintain an environment inventory containing name, consumer, frontend/backend, public/secret, build-time/runtime, requirement, validation and example placeholder. Include only variables actually consumed in `.env.example`. Ignore real `.env` files; use deployment secret management. Never put database, JWT/session, SMTP, provider or service secrets in a public prefix or browser bundle. Public API/site URLs are configuration, not secrets. Remove obsolete Supabase/Lovable variables after their last consumer is replaced.

Centralize typed parsing, validate required values on startup, and fail on missing or known weak deployed secrets. Explicit local-only development values may be provided by isolated dev configuration, not fallback logic that accidentally enables production. Verify frontend URL behavior when values are baked during build versus read at runtime. Distinguish browser-facing origin from container-internal service URL. A browser cannot resolve a Docker service hostname such as backend.

Allowlist origins for credentialed CORS; do not combine wildcard origin with cookies. Define TLS, proxy trust, secure cookies, CSRF, CSP/headers and OAuth callback/public site URLs for actual hosting. Do not hardcode the old project's domain as a fallback.

## Development

When Docker Compose is applicable, use separate `docker-compose.dev.yml` and `docker-compose.prod.yml`. Compose files live in the backend repository (never in a separate infra repository or the parent workspace folder); document the relative path to the sibling frontend build precisely, or have the frontend run independently against the backend's port. Include backend and PostgreSQL for local standalone development; add frontend service or clear independent frontend instructions. Use Mailpit (or the selected local SMTP capture) only when email exists; MailHog is unmaintained, so prefer Mailpit for new setups. Include storage/queue dependencies only when chosen architecture requires them. Provide an isolated test database (a separate service, profile or Testcontainers setup with its own database name and volume) for the runtime API acceptance run in verification.md; never point tests at the development or production database.

Provide database health checks, persistent volumes, a migration service/command, deterministic installation, hot reload where practical, container networking and sample configuration. Wait for readiness rather than startup order alone. Bind dev-only database/admin/mail ports to local access. Seed only necessary reproducible non-sensitive development/bootstrap data, with idempotent commands. Do not create a known production admin password in seeds.

### One command spins up the whole stack, including the APIs

`docker compose -f docker-compose.dev.yml up --build` (run from `<backend-repo>`) must start everything needed to use the API locally, not only the database:

| Service | Purpose | Notes |
| --- | --- | --- |
| `db` | PostgreSQL | Pinned major version matching production; named volume; healthcheck `pg_isready`; port bound to `127.0.0.1` only |
| `migrate` | Runs all migrations (and idempotent dev seed if defined), then exits | Built from the backend `Dockerfile`; `depends_on: db: condition: service_healthy` |
| `api` | The backend API with hot reload | `depends_on: migrate: condition: service_completed_successfully`; source bind-mounted with `node_modules` kept in a container volume; healthcheck against the readiness endpoint (for example `node -e "fetch('http://localhost:PORT/health/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"`, which needs no curl in the image) |
| `worker` | Background jobs, only if the app has them | Same image, separate entry point |
| `mail` | Mailpit, only if the app sends email | UI port bound to `127.0.0.1` |
| `test-db` | Isolated test PostgreSQL | Under a Compose `profiles: [test]` so it starts only for test runs |
| `frontend` | Optional | Built from `../<frontend-repo>` if the user wants a single command for both; otherwise the frontend README explains running it against the API port |

After `up`, the API, its health endpoints and Swagger UI must respond on the documented ports. Use environment from `.env` (copied from `.env.example`) with safe local-only values; the Compose file must not contain real secrets.

`docker-compose.prod.yml` (or the hosting platform's equivalent) runs the production image: a one-shot `migrate` service or release job, then `api` (and `worker`) with no bind mounts, no hot reload, no Mailpit, no published database port, restart policy, resource limits, healthchecks and secrets injected from the environment or secret manager. If production uses managed PostgreSQL, omit the `db` service there.

### Dockerfiles

- **Backend `Dockerfile`:** multi-stage with named targets: `deps` (install from lockfile), `dev` (used by `docker-compose.dev.yml`, runs the watch command), `build` (compile TypeScript), and `prod` (production dependencies only, compiled output, non-root user, `NODE_ENV=production`, `EXPOSE` the API port, `HEALTHCHECK`, and the start command). Migrations run from the same image with a separate command, not automatically on every API start in production.
- **Frontend `Dockerfile`** (in `<frontend-repo>`): for an SPA, build the static assets then serve them from a small web server image with deep-link rewrites to `index.html` and the API URL supplied as documented (build-time or runtime config); for SSR (Next.js or TanStack Start), run the framework's production server as a non-root user.
- Each repository has a `.dockerignore` that excludes `node_modules`, build output, `.env*` (except `.env.example`), `.git`, test artifacts and local data.

### Verify the spin-up

Run the dev stack from a clean state (`docker compose -f docker-compose.dev.yml down -v` first, on the dev stack only) and confirm: all services become healthy, migrations finish, the API's health/readiness endpoints and Swagger UI respond, one authenticated API call works, and logs appear in `docker compose logs api` as structured lines with request IDs. Also build the production image and start it with test secrets to confirm it boots, passes its healthcheck and fails fast when a required secret is missing. Record the commands and results in `docs/migration/verification.md`. If Docker is unavailable, mark this BLOCKED with the exact commands.

## Root README in each repository

Each repository gets a root `README.md` written for a developer who has never seen the project. Every command in it must have been run successfully during verification (or be clearly marked as not verified with the reason). Use these sections, omitting any that do not apply:

**`<backend-repo>/README.md`**
1. **Overview** — what the service does, the stack and a link to `docs/migration/`.
2. **Prerequisites** — exact Node.js version (also in `.nvmrc` or `engines`), package manager and version, Docker and Docker Compose versions.
3. **Quick start with Docker** — copy `.env.example` to `.env`, the single `docker compose -f docker-compose.dev.yml up --build` command, and what starts.
4. **Services and URLs** — table of service, URL/port and purpose: API base URL, health and readiness endpoints, Swagger UI, OpenAPI JSON, Mailpit UI, database host/port for local tools.
5. **Run without Docker** — install, start a local database, migrate, seed, and run the dev server.
6. **Environment variables** — table of name, required/optional, description and example placeholder; never real values.
7. **Database** — commands to create a new migration, run, roll back and seed; where migrations live; how to reset the local database (with a warning that it deletes local data).
8. **Scripts** — table of every `package.json` script and what it does (dev, build, start, lint, type check, test, `test:e2e:api`, cycle check, OpenAPI generation).
9. **Testing** — how to start the test database, run unit/integration/API tests, and read the results.
10. **Logs** — how to view them (`docker compose logs -f api`), how to change `LOG_LEVEL`, and the log format with request IDs.
11. **API documentation** — Swagger location, where the spec file lives and how the frontend regenerates its client.
12. **Project structure** — a short tree of the top folders and feature modules.
13. **Production** — how to build and run the production image, run migrations as a release step, required secrets and health checks.
14. **Troubleshooting** — port already in use, database not ready, migrations failed, CORS errors, how to fully reset the dev stack.

**`<frontend-repo>/README.md`**
1. Overview, stack and link to the backend repository.
2. Prerequisites (Node.js and package manager versions).
3. Quick start: install, copy `.env.example`, set the API URL to the running backend, start the dev server, and the local URL.
4. Environment variables table (public build-time vs runtime).
5. Scripts table (dev, build, preview/start, lint, type check, tests, E2E, API client generation).
6. API client: how to regenerate it from the backend's OpenAPI spec.
7. Testing, including how E2E tests expect the backend to be running.
8. Project structure (features and shared folders).
9. Docker and production build, including SPA deep-link or SSR notes.
10. Troubleshooting (API unreachable, CORS, wrong API URL baked into a build).

## Production preparation

Build separate frontend/backend images or provider-appropriate artifacts. Use multi-stage production builds, supported pinned runtimes, dependency lockfiles, a non-root runtime where supported, minimal production dependencies, and .dockerignore excluding secrets and irrelevant files. Never bake real secrets into ARG/ENV layers or images. Match image output/entry point to actual SSR versus SPA behavior; configure SPA deep-link rewrites and SSR startup appropriately.

Do not ship dev hot reload, bind-mounted source, local mail capture (Mailpit/MailHog) or public PostgreSQL ports in production. Use persistent storage/backups and a managed DB or explicitly operated database. Do not deploy a second local database when the selected production architecture uses managed PostgreSQL. Define connection pooling, resource limits, shutdown/draining, liveness/readiness and migration release jobs. Test required secret validation in production mode.

Configure frontend API origin, reverse-proxy routing, allowed origins, TLS, cookie domain, provider callbacks, object storage policy, health monitoring and log redaction. Resolve cross-origin/cross-site cookie behavior with the actual domain arrangement; do not assume localhost behavior proves production auth.

## Independent CI and contract compatibility

Each repository must install from its own lockfile and run formatting/lint/type checks, a circular-dependency check, meaningful tests and a production build. Backend CI uses isolated PostgreSQL to apply migrations and test APIs/authorization. Generate/lint OpenAPI and run route/spec/response checks. Frontend CI checks against a pinned contract artifact/client and runs component/core journey tests as applicable. Never copy backend source from a sibling path to make CI pass.

Record security/dependency scan results, necessary exceptions and build artifacts. Define a contract compatibility check and deployment order for breaking changes. Prefer additive API/database changes, migrate clients/data, then remove old behavior after verified usage has ended.

## Rehearsal and cutover runbook

Prepare before production execution:
1. Record source/target versions, environment, authorized operator, downtime window and success/rollback criteria.
2. Snapshot database and objects; rehearse a restore in isolation and record evidence.
3. Apply additive target migrations, import rows/identities/files with checkpoints, and reconcile.
4. Disable real external side effects in rehearsal; use test provider accounts and SMTP capture; disable imported `pg_cron` jobs, `pg_net` calls and database webhooks.
5. Configure secrets, provider webhooks/redirects, issuer metadata, origins and monitoring; validate with representative accounts.
6. Freeze source writes or apply final captured deltas; reconcile again with timestamps.
7. Deploy compatible backend then frontend, switch routes/DNS as planned, invalidate obsolete sessions/caches and execute smoke/permission tests.
8. Monitor defined error/login/job/webhook/data metrics; keep the previous release and backups until acceptance.
9. Roll back if thresholds fail. Explain how writes made after cutover are preserved/reconciled: rolling back only code or restoring an old snapshot can lose data. Prefer forward-compatible expand/contract schemas and a tested reverse/delta strategy where required.
10. Decommission old services only after explicit authorization, completed observation and proven absence of consumers.

Do not execute production deployment, DNS changes, live imports/destructive migrations, provider account changes or service decommissioning without relevant user authorization. Do prepare scripts/config/runbook and isolated validation proactively. Keep “deployment prepared,” “deployed,” and “production cutover verified” as separate statuses.

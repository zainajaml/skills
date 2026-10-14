# Backend modules and API contracts

Contents: [Express](#expressjs-branch) · [NestJS](#nestjs-branch) · [API behavior](#api-behavior) · [Payload format and interceptors](#payload-format-and-interceptors) · [Errors and retries](#error-handling-and-retries) · [Circular dependencies](#no-circular-dependencies) · [Logging](#logging) · [OpenAPI](#openapi-is-implementation-work) · [Evidence](#required-evidence-per-feature)

## Express.js branch

Use a composition root to mount feature routers and inject dependencies. Keep application creation separate from listening so integration tests can use the app without opening a port. Adapt names to the project's conventions; the following is illustrative, not a requirement to create empty files.

```text
<backend-repo>/        # name given by the user, see architecture.md
  src/
    app.ts
    server.ts
    config/env.ts
    database/client.ts
    database/migrations/
    database/seeds/
    shared/http/errors.ts
    shared/http/error-handler.ts
    shared/http/request-context.ts
    shared/security/authenticate.ts
    shared/observability/logger.ts
    modules/
      projects/
        projects.routes.ts
        projects.controller.ts
        projects.service.ts
        projects.repository.ts
        projects.schemas.ts
        projects.dto.ts
        projects.types.ts
        projects.policy.ts
        projects.openapi.ts
        projects.constants.ts
        projects.entity.ts
        utils/
        tests/
      auth/
      users/
    integrations/
  tests/integration/
  tests/contracts/
  openapi/
  docs/
  package.json
  tsconfig.json
  .env.example
  Dockerfile
  .dockerignore
  docker-compose.dev.yml
  docker-compose.prod.yml
  README.md
```

Register middleware in an intentional order, including raw-body routes needed for webhook signature verification before generic JSON parsing. Configure payload limits, allowlisted CORS, secure headers, trusted proxy settings appropriate to hosting, authentication, validation, rate limits, route mounting, 404 handling and a final error handler. Verify async error propagation for the selected Express major version; do not copy incompatible patterns.

Keep schemas beside each feature and validate path/query/body independently, including pagination limits and allowlisted sorting/filter fields. Controllers translate validated requests and trusted context into service calls and map results to HTTP DTOs. Services own invariants, orchestration and transaction intent; repositories implement parameterized persistence with the transaction client passed consistently. Put resource/tenant policies in the module, with shared primitives only when genuinely common.

## NestJS branch

Use Nest modules, dependency injection, controller decorators, pipes, guards, filters and interceptors according to their responsibilities. Controllers already declare routes; do not add redundant Express-style route files.

```text
<backend-repo>/        # name given by the user, see architecture.md
  src/
    main.ts
    app.module.ts
    config/
    database/
      database.module.ts
      migrations/
      seeds/
    common/
      guards/
      filters/
      interceptors/
      decorators/
      logging/
    modules/
      projects/
        projects.module.ts
        projects.controller.ts
        projects.service.ts
        projects.repository.ts
        projects.policy.ts
        dto/create-project.dto.ts
        dto/project-response.dto.ts
        entities/project.entity.ts
        types/
        constants/
        tests/
      auth/
      users/
    integrations/
  test/integration/
  test/contracts/
  openapi/
  docs/
  package.json
  tsconfig.json
  .env.example
  Dockerfile
  .dockerignore
  docker-compose.dev.yml
  docker-compose.prod.yml
  README.md
```

Choose an ORM-compatible model layout: TypeORM entities can live in the feature; a tool requiring a central schema can keep that schema in database/ with ownership documented per module. Never create fake entities to satisfy this tree. Use DTO validation at the boundary and serialization that excludes sensitive fields. Configure transform/coercion and unknown-field behavior deliberately. Define guards for auth/roles and invoke resource policies for actual ownership checks. Avoid circular module dependencies and routine forwardRef use; redesign boundaries first.

## API behavior

Design named domain operations from observed workflows: for example `PATCH /api/v1/projects/:id`, `POST /api/v1/invitations/:id/accept`. Choose versioning based on consumer/rollout needs and use it consistently. A table's existence does not justify a public CRUD endpoint. Do not accept arbitrary table names, column lists, SQL fragments, RPC names or generic client-supplied query chains as the final public API.

Define pagination/cursors, sort/filter allowlists, ordering guarantees, bulk limits, concurrency/version conflicts and idempotency for operations that can duplicate external effects. Move multi-request UI mutations into atomic backend use cases where the workflow requires all-or-nothing behavior.

Use the standard payload format below and show it in the plan. Expose only safe field errors in `details`. Use correct status codes, stable machine-readable codes, request correlation and structured redacted logs. Preserve deliberate 204/no-body, file/stream/SSE and provider protocol responses instead of forcing every response into an envelope. Do not expose password hashes, refresh tokens, internal columns, SQL errors or stack traces in DTOs.

Use centralized validated configuration; fail startup for missing/weak required deployed secrets. Keep .env reads and process.env access in config adapters rather than scattered services. Add graceful shutdown and liveness/readiness without exposing secrets.

## Payload format and interceptors

Define one JSON format for the whole API (adapt names if the project already has a working convention, but keep it identical across modules):

```jsonc
// success
{ "data": { "id": "…", "name": "…" }, "meta": { "requestId": "…" } }
// paginated list
{ "data": [ … ], "meta": { "requestId": "…", "nextCursor": "…", "total": 120 } }
// error
{ "error": { "code": "PROJECT_NOT_FOUND", "message": "Project not found", "details": [] }, "meta": { "requestId": "…" } }
```

Apply it centrally, never by hand in controllers:

- **NestJS:** a global response interceptor (registered with `APP_INTERCEPTOR` or `app.useGlobalInterceptors`) wraps controller return values in `{ data, meta }`; a global exception filter (`APP_FILTER`) maps domain errors, validation errors and unknown exceptions to the error format; a request-context interceptor or middleware sets and returns the request ID; serialization excludes sensitive fields. Controllers return plain DTOs.
- **Express:** a small response helper or middleware (for example `res.ok(dto)`, `res.paginated(items, meta)`) produces the success format; one final error-handling middleware produces the error format; a request-ID middleware runs first. Route handlers never call `res.json` with ad-hoc shapes.
- **Both:** map each domain error class to a status code and stable `code` in one place; unknown errors become a generic 500 with the request ID and are logged with the stack, never returned to the client.

Deliberate exceptions skip the envelope and are documented in OpenAPI: 204/no-body responses, file downloads and streams, SSE, health checks if a platform requires a fixed shape, and responses to third-party webhooks or OAuth/MCP protocol endpoints that must follow the provider's format.

Document the envelope once in OpenAPI as reusable wrapper schemas (success, paginated, error) and reference them from every operation, so the generated frontend client and the contract tests see the real shape.

## Error handling and retries

- **Typed errors.** Define domain/application error classes (for example `NotFoundError`, `ForbiddenError`, `ConflictError`, `ValidationError`, `ExternalServiceError`) in shared code; services throw them, the central handler formats them.
- **Async errors reach the handler.** NestJS does this automatically. With Express 5, rejected promises from handlers are forwarded to the error middleware; with Express 4, wrap async handlers so rejections call `next(err)`. Verify for the installed major version.
- **try/catch with purpose.** Catch only to translate a low-level error into a domain error (for example a unique-violation `23505` into `ConflictError`), to clean up or roll back, to compensate a partial external action, or to retry. Rethrow or convert everything else. Never use an empty catch, never return success after a caught failure, and never log and continue when the caller needs to know.
- **Bounded retries where applicable.** Retry only transient failures: network errors, timeouts, HTTP 429/502/503/504 from external providers, and database serialization failures (`40001`) or deadlocks (`40P01`) by retrying the whole transaction. Use a maximum attempt count (typically 3), exponential backoff with jitter, a per-attempt timeout and an overall deadline, and respect `Retry-After`. Retry non-idempotent operations (payments, emails, external creates) only with an idempotency key or deduplication; otherwise do not retry. Never retry validation, authentication, authorization or other 4xx errors. Use a maintained helper (for example `p-retry`, `cockatiel`, or the provider SDK's built-in retry) rather than hand-written loops, and add a circuit breaker only when an unstable dependency justifies it.
- **Background work.** Jobs and webhook processing use the queue's bounded retry with backoff, then move to a dead-letter or failed state that is logged and visible; they never loop forever.
- **Logging.** Follow the Logging section below. Log each final failure once, at the boundary, with request ID, error code and safe context; log retry attempts at a lower level. Redact secrets and personal data.

## No circular dependencies

Feature modules depend in one direction: controllers → services → repositories, and features → shared/infrastructure, never the reverse. Shared code must not import feature code. When two features need each other, extract the shared part into a lower-level module, depend on an exported interface, or communicate through a use case or domain event; do not paper over cycles with lazy `require`, re-export barrels or NestJS `forwardRef` (allowed only as a documented last resort).

Check both repositories with a tool and fail CI on any cycle. The check must cover every source file type the stack uses (`.ts`, `.tsx`, `.js`, `.jsx`, `.mts`/`.cts`, `.vue`), resolve the project's path aliases from `tsconfig`/bundler config, and start from the real entry points (app bootstrap, routes/pages directory, workers, CLI and migration scripts). For example `npx madge --circular --extensions ts,tsx,js,jsx --ts-config tsconfig.json src`, or `dependency-cruiser` with a `no-circular` rule and its `tsConfig` option (use dependency-cruiser for Vue SFCs). Confirm the tool actually scanned the expected number of files; a check that silently skips `.tsx` or aliased imports proves nothing. Index/barrel files are a common source of hidden cycles; import from the specific file when a barrel creates one. Nest's own startup error about circular provider dependencies is a failure to fix, not to suppress.

## Logging

Set up proper structured logging in the backend as foundation work, not at the end.

- **One logger.** Use a maintained structured JSON logger, for example `pino` with `nestjs-pino` (NestJS) or `pino-http` (Express); keep an existing working logger such as winston if the project already uses one. Create it once in `shared/observability/logger.ts` (Express) or the Nest logging module, and inject or import it everywhere. No `console.log` in application code; enforce with the `no-console` lint rule (scripts and tests excepted).
- **Levels.** Use `fatal`, `error`, `warn`, `info`, `debug`, `trace` consistently. Configure the level with a validated `LOG_LEVEL` variable (default `info` in production, `debug` in development). Use human-readable output (for example `pino-pretty`) only in development; production writes one JSON object per line to stdout so Docker and the hosting platform collect it. Do not write log files inside containers unless the user asks.
- **Request logs.** Log one line per request on completion with: request ID, method, route template (for example `/api/v1/projects/:id`, not the raw URL with IDs or query strings), status code, duration in ms, and the authenticated user ID/tenant ID when present. Log health/readiness requests at `debug` or skip them so they do not flood the logs.
- **Correlation.** Accept a valid incoming `X-Request-Id` or generate one, keep it in request context (for example `AsyncLocalStorage`, or the Nest/pino request context), add it to every log line in that request, return it in the response header and the error body `meta.requestId`, and forward it on outbound calls to other services.
- **What to log.** Startup (app version, environment, port, enabled integrations — never secret values) and shutdown; migration runs; outbound provider calls (provider, operation, status, duration, retry attempt); background job start/finish/failure with job ID; webhook receipt and deduplication; authentication events (login success/failure, logout, token refresh failure, lockout) without revealing whether an account exists; authorization denials at `warn`; and every unhandled error once at `error` with stack trace and request ID.
- **Redaction.** Configure redaction centrally (for example pino `redact` paths) for `authorization` and `cookie` headers, `set-cookie`, passwords, tokens, API keys, secrets, password hashes and personal data such as email/phone where not needed. Never log request or response bodies by default; log selected safe fields only.
- **Shutdown.** Flush logs during graceful shutdown so the last errors are not lost.
- **Tests.** Assert that a request produces a log line with the request ID, that a thrown error is logged once with the same request ID, and that a request with an `Authorization` header and a password field does not leak them into logs.

## OpenAPI is implementation work

For every implemented endpoint document:
- operation ID, tag, purpose and path/method;
- path/query/header parameters and constraints;
- request bodies, required/nullable fields, formats, enums, limits and examples;
- cookie/bearer/OAuth security scheme as applicable, plus authorization meaning;
- response DTOs/content types, successful status codes and pagination;
- validation, authentication, authorization, conflict, rate-limit and server errors where applicable;
- multipart upload or stream behavior when used.

Select one source of truth: runtime schemas that generate OpenAPI, or DTOs/decorators with consistency checks. Never maintain a detached aspirational spec. Explain validation semantics that the generator cannot encode, such as refinements and cross-field rules, and test them.

Generate a machine-readable spec and Swagger UI for local development; define appropriate production access controls. Validate the spec in CI, check route/spec coverage and stable operation IDs, and contract-test actual request/response examples including errors. If CI regenerates committed specs or client DTOs, fail on an unexplained diff. Publish/version the contract so independent frontend builds use a known compatible version; client generation does not replace runtime validation or authorization.

## Required evidence per feature

Include unit tests for meaningful rules and integration tests for persistence, transactions, validation and authorization. Test controller output against the contract. Inspect imports to ensure controllers do not query the database and unrelated modules do not reach into each other's internals. Test that success and error responses match the envelope, that a thrown domain error produces the right status and code, that an unknown error returns a safe 500 with request ID, and that retried calls stop at the limit. Do not count empty module folders, empty test files or a Swagger decorator on one endpoint as architecture compliance.

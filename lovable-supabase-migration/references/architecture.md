# Architecture before implementation

## Required decision summary

Present these 12 numbered sections with project-specific reasons:
1. Identified domains, responsibilities, dependencies and user journeys.
2. Frontend framework/runtime, route conventions, feature/shared boundaries and directory tree.
3. Backend framework, modules/layers, composition and directory tree.
4. Database, ORM/query builder, migrations, transactions and data import strategy.
5. Authentication/session lifecycle, authorization/tenant isolation and identity migration.
6. Domain API resources/use cases, versioning, pagination, contracts and repository contract distribution.
7. Backend validation, frontend forms, DTOs and serialization.
8. Server state, local UI state, global state and cache invalidation.
9. API errors, UI errors, logs, request correlation and observability.
10. Unit/integration/contract/E2E tests and baseline/negative cases.
11. OpenAPI schema source, generation, Swagger UI and CI drift checks.
12. Important libraries, exact compatible versions when resolved, purpose, alternatives and justification.

Include source and target paths; staged conversion sequence; data/file/identity cutover; risks and unknowns; deletion/rollback conditions; hosting constraints; and any retained provider. A retained Supabase/Lovable dependency must be visible in scope and completion wording.

## Repository boundaries

Use two independent sibling roots whose names **the user chooses**:

```text
<workspace>/
├── <frontend-repo>/   # name given by the user
└── <backend-repo>/    # name given by the user
```

**Ask the user for the names; do not derive them.** Never name the repositories after the source app's folder, Git remote, `package.json` name or product title, and never use literal `frontend`/`backend` unless the user chooses exactly that. Before creating any folder, ask in one message:

1. **Frontend repository name**, with options: reuse the existing source repository as the frontend (keeps its folder), or create a new folder with a name the user types.
2. **Backend repository name**: a name the user types.
3. **Parent location**: the default `<workspace>` described below, or another path the user gives.

Do not suggest app-derived names as defaults. Validate the answers: lowercase letters, digits, hyphens or underscores; no spaces, slashes or `..`; the two names must differ; and a new folder's path must not already exist (if it does, say so and ask again; never reuse or overwrite it). The only existing folder that may be used is the source repository, and only when the user picked the reuse option for the frontend. Record the confirmed names and absolute paths in the plan, then use them consistently: folder names, each repository's `package.json` `name`, Docker image/service and Compose project names, CI workflow names and documentation. If the user has not answered, continue read-only analysis and do not create either repository.

`<workspace>` is the **parent directory of the source application's Git root** (the folder that contains the current Lovable/Supabase repository), not the current working directory and never a folder inside the source repository. Find it with `git rev-parse --show-toplevel` from the source app and take its parent. If the source is inside a monorepo, or the parent is not writable or is an unrelated location (for example the home directory or a system folder), ask the user where to create the repositories. A destination the user names always wins. Example:

```text
/home/dev/projects/            <- <workspace> (parent of the source repo)
├── <source-repo>/             <- existing Lovable source repo (preserved)
├── <frontend-repo>/           <- name from the user, or the source repo reused as the frontend
└── <backend-repo>/            <- name from the user
```

New repositories are created **locally** with `git init` and their own initial commit. Creating or pushing to a remote (GitHub, GitLab and so on) happens only when the user asks and access is available.

Reuse the existing frontend repository when the selected stack makes that practical (it keeps its current folder name unless the user asks to rename it; the new backend is then `<backend-repo>` beside it); create a new sibling frontend when a framework transition requires it. Preserve source history and the old application until replacement verification. Check path collisions first. Each target has its own Git root, package manifest, lockfile, build, tests, environment example, CI and deployment instructions. Do not place a new `.git` under an unrelated existing Git root without a deliberate plan. Remote repository creation/publishing follows user authorization and available access; local repositories can still be prepared when remotes are unavailable.

The frontend must build without reaching into the backend repository's source (for example `../<backend-repo>/src`). Share the contract without a third repository: the backend owns and versions the OpenAPI spec (for example `openapi/openapi.json`), and the frontend generates its typed client into its own source (for example `src/shared/api/generated/`) from a pinned copy of that spec or the backend's spec URL, with a documented update command. Publish the client as a package only if the user explicitly asks. Never share ORM entities or database row types as browser contracts. Backend changes should support staggered deployments where feasible.

## Domain boundaries and proportionality

Derive features from user workflows (for example projects or invitations), not one module per database table. List each module's public surface and dependencies. Reuse through explicit exports/interfaces; do not reach into another module's repository internals. Put shared infrastructure in config/database/observability, and generic presentation primitives in shared UI. Domain-specific helpers stay in their feature.

Use route → validation/guard → controller → service/use case → repository/data access. Domain services must not depend on HTTP request/response objects. Repositories must not return transport responses. Perform authorization where resource context is available, before persistence; authentication alone is insufficient. Pass trusted actor/tenant context rather than client-supplied ownership.

Use repositories for actual persistence boundaries, not empty generic base classes. Split services into use cases when independent rules/workflows justify it. Do not create empty folders for unused models, state, constants or utilities. Avoid interfaces with one trivial implementation unless they support a useful boundary or test seam. Do not introduce CQRS, microservices, event buses or a monorepo by default.

Keep naming consistent within the chosen framework and existing useful conventions. Use strict typing, formatter/linter, focused functions and explicit exports. Review authored files around 300 lines and split when they mix responsibilities; do not mechanically split cohesive code to meet a numeric limit. Generated code/schema snapshots are exceptions and should be clearly marked.

## Library selection

Inspect what is already working before adding dependencies. Consult official docs for installed/target versions and check peer compatibility at execution time. Record unresolved version compatibility if online access is unavailable; never claim a frozen version recommendation is current.

| Concern | Selection guidance |
| --- | --- |
| Persistence | Choose one supported PostgreSQL ORM/query builder based on schema features, team constraints and migration needs. TypeORM, Prisma or Drizzle are candidates, not simultaneous mandates. Preserve custom SQL/extension behavior where needed. |
| Express validation/contracts | A schema library such as Zod plus a compatible OpenAPI generator can align runtime validation and docs. Verify transforms/refinements are represented accurately. |
| NestJS validation/contracts | DTOs with class-validator/class-transformer and Nest Swagger are a conventional option; a schema-first integration is acceptable if validated. Do not maintain conflicting schema systems. |
| React/Next forms | React Hook Form plus a compatible schema resolver when forms warrant it; keep existing effective patterns. |
| Vue forms | A maintained schema/form integration such as VeeValidate when appropriate; preserve accessible native form semantics. |
| API/server state | Existing fetch client can suffice; Axios only for a clear benefit. TanStack Query is suitable for interactive cached server state; do not add it to purely server-rendered data without need. |
| Global UI state | React context or a small store; Vue Pinia when shared state warrants it. Avoid duplicating server data in a second store. |
| Tests | Use compatible existing test tools, or Vitest/Jest, Testing Library/Vue Test Utils, HTTP integration tests, and Playwright as justified by behavior. |

Security, auth and validation libraries must be maintained and appropriate for the chosen versions. Do not implement custom cryptographic primitives, OAuth or session protocols when a suitable established library can provide them.

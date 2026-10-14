# Mapping upstream changes onto the migrated architecture

Contents: [Learn the destination](#learn-the-destination) · [Find the mapping](#find-the-mapping) · [Supabase and Lovable equivalents](#supabase-and-lovable-equivalents) · [Existing-feature detection](#existing-feature-detection) · [Implementing a unit](#implementing-a-unit) · [Database changes](#database-changes) · [Dependencies and configuration](#dependencies-and-configuration)

The destination repositories are the architectural authority. Every synced change must look as if the destination team wrote it.

## Learn the destination

Before the first unit of a session, read, in this order:
1. `docs/migration/` in the backend (written by lovable-supabase-migration): `ledger.md` maps source workflows to modules and endpoints, `architecture.md` holds the decisions and trees, `schema-coverage.md` maps source database objects, and `report.md` lists retained providers. These are the best starting map.
2. Each repository's README, `package.json` scripts, lint and TypeScript config, and folder structure.
3. One or two representative feature modules end to end, in each repository. Note route and controller style, service/use-case boundaries, the repository or ORM pattern, validation library, DTO and response envelope, error classes, auth guards and policies, logging, OpenAPI source, test layout and naming.
4. The frontend's router, central API client, server-state library, form and validation pattern, design system components, auth/session handling, and feature folder layout.

Record the conventions you will follow in the plan, briefly. If the destination differs from the illustrative trees in the task or in other skills, the destination wins. Framework differences matter: a Next.js App Router page, a React Router route and a Vue Router view express the same upstream page differently, and so do an Express router and a NestJS controller.

## Find the mapping

Upstream paths rarely match. Map by behavior, using these in order of reliability:
1. The migration ledger, and earlier sync records (`sync_state.py show --commit`, `Lovable-Upstream:` trailers in `git log`), for the same source file or workflow.
2. Data identity: the table, column, bucket or function name in the upstream code, then the destination repository, entity, migration or endpoint that owns it.
3. Route and API identity: the upstream route path, page title or Edge Function name, then the destination route, feature folder or endpoint (OpenAPI operation IDs help).
4. UI identity: visible strings, component names and test IDs, searched in the destination (`rg`).
5. Business rules: the same validation, calculation or permission logic in a differently named place.

Write each mapping in the plan as `upstream path or behavior → destination module and files`. When nothing maps, the feature is missing. Plan a new module in the destination's style, not a copy of the upstream file layout.

## Supabase and Lovable equivalents

Never assume an equivalent exists. Find it, or plan it.

| Upstream | Destination equivalent | If it is missing |
| --- | --- | --- |
| `supabase.from()` / `.rpc()` in components | Backend repository + service + endpoint; frontend feature API function + hook through the central client | Add them to the owning feature module; never call the database or Supabase from the frontend |
| `supabase.auth.*` | Destination auth module (sessions/JWT, guards, current-user context) | Extend the auth module; ask before adding a new login method |
| Edge Function | Backend module endpoint or job, validated config, explicit authorization | New use case in the right module, documented in OpenAPI |
| Supabase Storage | Destination file-storage service and its policy | Add to the files module, with ownership checks on upload, download and signed URLs |
| Realtime channels | Destination SSE/WebSocket/event mechanism with permission filtering | Ask: adding realtime infrastructure is high impact |
| RLS policy | Service/policy-layer authorization (or deliberately retained database RLS) | Write the policy and negative tests; never rely on the frontend hiding things |
| `auth.uid()` in defaults or triggers | Trusted actor context set by the backend | Set it in the service or repository from the authenticated user |
| Database triggers and functions | Destination migration or backend use case, as the migration decided (`schema-coverage.md`) | Follow the same decision pattern |
| `pg_cron`, `pg_net`, database webhooks | Backend scheduled jobs and integrations | Add a job or integration with bounded retries |
| Lovable AI gateway | Destination AI provider integration | Map the model name explicitly and ask if the provider differs |
| `.env` / `Deno.env.get` names | Destination config validation and `.env.example` | Add names with placeholders; ask the user for real values |

If the migration deliberately kept a Supabase capability (see `report.md`), use that capability the way the destination already does.

## Existing-feature detection

Before writing code for a unit, classify the destination:

| Finding | Action |
| --- | --- |
| Behavior already exists and matches | `already-present` with evidence: the file or endpoint, plus how you compared (the same inputs give the same outputs, rules and errors; a test proves it, or you read both sides) |
| Exists under another name or a refactored structure | Change it in place |
| Implemented during migration in a different way with the same result | `already-present` with evidence |
| Exists with local improvements upstream does not have | Merge only the new upstream behavior and keep the improvements; a real disagreement is a conflict |
| Replaced by a different implementation on purpose | Conflict: compare the four behaviors (conflict-resolution.md) |
| Partially present | Implement only the missing part |
| Missing | Implement it in the destination's architecture |

"Looks similar" is not "matches". Skip a change only after verifying the behavior, including permissions and error cases.

## Implementing a unit

Backend, for the module that owns the behavior:
- route or controller thin, with validation schemas or DTOs at the boundary, matching the existing library;
- service or use case for the rules, and repository or data access for queries; transactions where the upstream behavior must be all-or-nothing;
- authorization from the authenticated actor and current membership, never from client-supplied IDs; reproduce every RLS intent (`USING` and `WITH CHECK`);
- the existing error classes, response envelope and logging; no `console.log`;
- OpenAPI updated through the destination's source of truth (decorators or schemas), with error responses;
- tests in the existing style: unit tests for rules, and integration tests for endpoints, including denied, invalid and not-found cases.

Frontend, in the feature that owns the screen:
- route or page files stay thin and use feature views and components;
- data goes through the central API client and feature API functions or hooks; no raw `fetch`, no Supabase client, no row types from the backend;
- the existing design system components, styling tokens, form library, error and loading states, and accessibility;
- split large upstream components into the destination's component granularity; never paste a monolithic Lovable page;
- regenerate the typed API client from the updated OpenAPI if the frontend uses generated clients;
- component or E2E tests where the destination has them.

Keep each unit's changes focused. Do not refactor unrelated code, upgrade unrelated packages or redesign UI while syncing. Report such findings as follow-ups.

## Database changes

- Translate upstream SQL into a **new** migration in the destination's tool and naming scheme (one focused file per table or object change). Never copy `supabase/migrations` files, and never edit migrations that have already been applied.
- Map `auth.users` references to the destination's users table, and `auth.uid()` to backend-set values. Policies become backend authorization unless the migration kept database RLS.
- Changes that affect existing data (drops, type narrowing, new `NOT NULL` without a default, renames) need the user's approval and an expand/contract plan: add first, backfill, switch the code, remove later.
- Update `docs/migration/schema-coverage.md` if the backend keeps one.
- Lovable Cloud may change the schema without a migration file. A changed `types.ts` with no SQL means asking the user for the current schema, or for a schema export.

## Dependencies and configuration

- Add an upstream dependency only if the synced behavior needs it in that repository, and only in the repository that runs the code (a server-only SDK goes to the backend). Prefer a library the destination already uses for the same job.
- Check compatibility with the destination's framework and runtime versions. Ask before major-version upgrades or anything that touches the build.
- Use the destination's package manager and regenerate its lockfile. Ignore upstream lockfile churn.
- Ignore `lovable-tagger`, `@lovable.dev/*` and Lovable build-wrapper changes unless the destination still uses them.
- Upstream Tailwind or theme token changes: apply the same values to the destination's theme files. Email templates built from those tokens need updating too.
- New env variable names: add them to config validation and `.env.example` with placeholders, document them in the README, and list them in the report as "needs a value from the user". Never copy values.

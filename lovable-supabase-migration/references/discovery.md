# Discovery: inspect the actual application

## Project profile (write this first)

Classify the project from evidence before anything else, and keep the profile at the top of `discovery.md`. Every later choice must follow from it.

| Dimension | Possible values (not exhaustive) |
| --- | --- |
| Origin | Lovable; another AI builder (Bolt, v0 and similar); hand-written; a mix |
| Backend hosting | Lovable Cloud; user-owned Supabase (cloud or self-hosted); several Supabase projects; no Supabase (frontend only, or another backend) |
| Frontend runtime | Vite SPA (React Router or other); TanStack Start; Next.js (Pages or App Router, often with `@supabase/ssr`); other; JavaScript or TypeScript |
| Repository shape | single app; monorepo/workspaces; several apps sharing one Supabase project; partly migrated already |
| Supabase features in use | database, auth, storage, realtime, Edge Functions, RPC/SQL functions, cron, queues, vectors, GraphQL, webhooks, Vault (each: used / not used, with evidence) |
| Auth model | none (public app); email/password; magic link/OTP; phone/SMS; OAuth/SSO/SAML; anonymous sign-ins; MFA |
| Tenancy and roles | single user; per-user data; teams/organizations; admin roles; public content |
| Other clients | only this web app; mobile apps, scripts, partner integrations or MCP clients also calling Supabase directly |
| Size | number of screens, tables, policies, functions; data volume; users |

Other clients matter: if a mobile app or external script also uses the same Supabase project, removing Supabase breaks them. Record them, and agree with the user whether the new API must serve them, they stay on Supabase for now, or they are out of scope.

If the project has no Supabase usage at all (for example a frontend-only Lovable app), say so; the work becomes a frontend restructure plus a new backend only for the behavior that needs one. Confirm the scope with the user rather than inventing a database.

## Establish the source of truth

Identify current directory, Git roots/status, canonical frontend, any backend, duplicate app trees, package names, deployment scripts, build output and deployed entry point. Do not assume the current directory or a sibling named frontend is the deployed app. If contradictory deployment evidence remains, ask which tree is authoritative before writing application code. Do not delete duplicates. Record actual absolute paths in the migration plan, not in this reusable skill.

Read project instructions, package manifests, all lockfiles, compiler/build/router settings, CI, containers, reverse proxies, source entry points, generated route trees, migration directories and docs. Determine whether React is a browser SPA, TanStack Start server application, Next.js SSR application, or another runtime. A Vite configuration does not prove a static SPA. Trace wrappers such as `@lovable.dev/vite-tanstack-config`, Nitro, plugins, server functions and middleware before changing the build.

Do not assume the runtime. Newer Lovable apps may be TanStack Start projects, older ones are often Vite + React Router SPAs, and non-Lovable Supabase apps can be Next.js or anything else; confirm from manifests and entry points. The `@lovable.dev/vite-tanstack-config` wrapper targets Cloudflare Workers by default, so a TanStack Start source may currently depend on a Workers-style runtime. Record the actual build target and hosting before choosing the target frontend runtime.

## Hosting mode and export path

Establish which backend mode the project uses, from code and by asking the user when unclear:

| Mode | Typical evidence | Export implications |
| --- | --- | --- |
| Lovable Cloud | No user-owned Supabase project; managed from Lovable's Cloud tab | Usually no Supabase dashboard or direct DB connection. The documented route is Lovable's Cloud → Overview → Advanced settings → Export data (full database including `auth.users` with password hashes; size and frequency limits apply). It does **not** include storage files, Edge Function code or secrets: obtain function code from the repository, list secret *names* from code and ask the user to supply values, and plan file extraction separately (for example a backend-run script using authorized storage access). |
| User-owned Supabase | Project ref the user controls; dashboard access | Use the Supabase CLI (`supabase db dump` for schema/data/roles) or `pg_dump` against the direct/session connection, not the transaction-mode pooler. Export storage objects via the Storage API or S3-compatible access. |

Lovable's UI and limits change; confirm the current export procedure with the user or Lovable docs rather than assuming. If no export path is available yet, continue code analysis and mark data/identity/file migration BLOCKED with the exact missing access.

## Known Lovable/Supabase locations

For Lovable projects, start with these common locations, then confirm by import graph (they are leads, not guarantees). Other Supabase apps may create clients anywhere (for example `lib/supabase/*`, `utils/supabase/*`, `@supabase/ssr` middleware), so always search for every `createClient`/`createBrowserClient`/`createServerClient` call:

- `src/integrations/supabase/client.ts` (client creation, often with a hard-coded project URL and anon/publishable key) and `src/integrations/supabase/types.ts` (generated row types).
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_ANON_KEY`, `VITE_SUPABASE_PROJECT_ID` and other `SUPABASE_*` names.
- `supabase/config.toml`, `supabase/migrations/`, `supabase/functions/<name>/index.ts`, `supabase/seed.sql`.
- `lovable-tagger` and `componentTagger()` in the Vite config (development-only tagging; remove with the Lovable tooling).
- `LOVABLE_API_KEY` and calls to the Lovable AI gateway (`ai.gateway.lovable.dev`), Lovable Emails, and `.lovable` metadata.
- Multiple lockfiles (`bun.lockb`/`bun.lock`, `package-lock.json`) left by different tools.

Search files and import/call graphs; treat a text match as a lead, not proof of runtime use. Prefer `rg --files --hidden` (or `git ls-files`/`grep -r` when ripgrep is unavailable) with exclusions for `.git`, dependency and generated build directories. Search variable names and file paths without displaying `.env` values or secret-bearing lines. Inspect ignored runtime configuration privately if authorized. Distinguish source, generated files, runtime config, tests, migration history and stale documentation.

## Capability inventory

Audit these categories even if `@supabase/supabase-js` is already absent:

| Category | Inspect and record |
| --- | --- |
| Product | Screens, routes, forms, roles, tenants, user journeys, accessibility, empty/error states, redirects, imports/exports, business invariants |
| Hosting/export | Lovable Cloud vs user-owned Supabase, available export route, access the user can grant, data size |
| Supabase queries | SDK imports and aliases, `.from`, query chains, REST/PostgREST URLs, client clones, `.rpc`, `.single`/`.maybeSingle`, pagination/count/filter behavior, generated row types |
| Auth | Login/logout/registration, session refresh, verification/reset, OAuth/SSO/SAML, magic links, email/phone OTP, anonymous sign-ins, MFA if used, auth hooks, invites/admin operations, profiles, metadata, account linking, guards, callback URLs, token storage |
| Schema | Tables/columns/types, PK/FK/unique/check constraints, indexes, sequences, defaults, nulls/enums, views/materialized views, functions/triggers, extensions (`pg_cron`, `pg_net`, `pgvector`, `pgmq` queues, `pg_graphql`, Vault), database webhooks, references to `auth.users`/`auth.uid()`, grants and RLS |
| Storage | Buckets, public/private access, signed URLs, metadata, object keys, limits, MIME types, transform/CDN behavior, upload/download/delete and references embedded in rich text |
| Realtime | Channels, postgres_changes, broadcast, presence, role-watch SSE/polling, subscriptions, reconnect and permission changes |
| Server behavior | Supabase Edge Functions (Deno), Next server actions/routes, TanStack `*.server.ts`/`*.functions.ts`, middleware, cron, workers, queues, email, billing, invitations, onboarding, rate limits |
| External services | Payments/webhooks, Jira or other imports, email templates/queues/retries, AI/RAG/model gateways/vector data, MCP tools/OAuth discovery/consent, analytics and delivery providers |
| Platform coupling | `@lovable.dev/*`, `lovable-tagger`, `LOVABLE_API_KEY`, Lovable AI gateway/Lovable Emails URLs and headers, preview postMessage brokers, `.lovable` metadata, auth attachers, build wrappers, MCP plugins, server-only SDKs |
| Configuration | Variable names, consumers, runtime/build-time scope, public/secret classification, required/optional status, fallback behavior, CORS/site/API URLs, hardcoded hosts and issuers |
| Operations | DB/file backups, schema owners, multiple schema histories, CI, package manager, frontend/server deployment targets, production data size, test availability, observability |

Trace aliases such as `export const supabase = backend` and service clients sending `x-service-token`. Record generic `/api/query` and `/api/rpc/:name` as compatibility infrastructure. Inspect runtime requests and redirects where tools permit; search results alone cannot establish independence from a remote service.

## Schema, policies and function evidence

Compare authorized live introspection/schema export with versioned SQL, generated types and actual call sites. Record source date and drift. If live access is unavailable, label the repo-derived schema provisional. Generated TypeScript types do not establish triggers, RLS, constraints or function bodies. Request missing exports necessary for affected slices; do not fabricate columns or policy semantics.

Record every place the public schema depends on Supabase's `auth` schema, because removing it breaks these silently:
- foreign keys to `auth.users(id)` (usually from `profiles`, ownership and membership tables);
- triggers on `auth.users` (in many projects a `handle_new_user`-style trigger creates a profile/role row on signup; names vary) — the target registration use case must reproduce whatever they do, transactionally;
- `auth.uid()`, `auth.jwt()` and `auth.role()` in column defaults, views, functions and policies;
- roles or tenant claims read from `raw_app_meta_data`/`raw_user_meta_data` (app_metadata/user_metadata) and any custom access-token hook.

Inventory extensions and database features with hidden side effects: `pg_cron` schedules (`cron.job`), `pg_net`/`http` calls from triggers or functions, Supabase Vault secrets (`vault.secrets`; record names only), database webhooks (`supabase_functions.hooks` triggers), `pgvector` columns/indexes, and `storage.objects` policies. Each active one maps to a backend job, integration, secret or policy.

Supabase Edge Functions run on Deno. Record for each: trigger (HTTP, webhook, cron, database webhook), auth expectation (`verify_jwt` in `config.toml`), `Deno.env` secret names, `npm:`/`jsr:`/`esm.sh`/URL imports, `Deno.serve` handler behavior, CORS handling, and service-role client use. Porting to Node requires replacing these runtime APIs, not copying files.

For each RPC/function/trigger record source, inputs/outputs, caller, grants, SECURITY DEFINER/search_path concerns, transaction/locking behavior, side effects, error behavior and target replacement. SQL set operations may remain in backend-owned database functions when justified; expose named domain operations and enforce policy. Do not blindly translate everything to application loops or a raw SQL endpoint.

For every RLS policy record table/operation/role, USING visibility and WITH CHECK write rules, ownership/tenant joins, helper functions and permissive/restrictive composition. Build actor × resource × action cases, including denial. Missing historical policy coverage is a security blocker for affected features, not a cosmetic limitation.

## Deliver evidence

Assign stable IDs to workflows and dependencies. Use this ledger shape:

| ID | Source file/function | Behavior and capability | Domain | Target API/owner | Permission case | Data/file/identity impact | Frontend change | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W-01 | `src/pages/Projects.tsx` `supabase.from('projects').select()` | List member's projects | projects | `GET /api/v1/projects` / projects module | Member sees own tenant only; non-member empty | none | `features/projects/api` + hook | API list + cross-tenant denial test, E2E list | pending |
| W-02 | `supabase/functions/invite-user` | Owner invites by email, sends mail | invitations | `POST /api/v1/invitations` | Owner only; member 403 | invitation rows; email | invite form uses feature API | service + HTTP 403 test, mail capture | pending |
| D-01 | trigger `handle_new_user` on `auth.users` | Creates profile on signup | auth/users | registration use case | n/a | profile rows; identity import | none | signup integration test | pending |

These rows are illustrative shapes; replace them with evidence from the actual project.

Use `pending`, `implemented-unverified`, `verified`, `blocked`, `not-applicable`, or `retained-by-explicit-decision`; do not mark a feature verified merely because code exists. Add temporary adapters and their exit criteria. Record known functional dependencies separately from dead code and historic SQL/docs.

Summarize baseline commands and results, feature/domain candidates, unknowns, integrations not used, schema discrepancies, data access limits, security findings and stack implications. Never turn example filenames, bucket names or provider choices from this skill or another project into requirements for the current project.

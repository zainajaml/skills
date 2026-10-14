# Data, identity, security and platform replacement

## Database ownership and transactions

Select one authoritative schema/migration tool.

### Migration file granularity

Split the schema into small, reviewable, ordered migrations; never one large generated dump. Use the selected tool's naming (timestamp or sequence prefix) so order is deterministic, for example:

```text
database/migrations/
  0001_extensions.sql            # pgcrypto, citext, vector ... only those used
  0002_enums_and_types.sql
  0003_fn_generate_slug.sql      # a function that a later table default or check constraint uses
  0004_create_users.sql          # one table per file: columns, PK, checks, defaults, own indexes
  0005_create_organizations.sql
  0006_create_memberships.sql    # FKs to tables created earlier
  0007_create_projects.sql
  ...
  0020_add_cyclic_foreign_keys.sql   # only for FK cycles that cannot be created in table order
  0021_fn_set_updated_at.sql     # one function (or a tightly related group) per file
  0022_trg_projects_updated_at.sql   # triggers after the tables and functions they use
  0023_views.sql
  0024_policies.sql              # only when database RLS is deliberately retained
```

Order by the actual object dependencies found in the source schema (for example from `pg_depend` or the order in a schema dump), not by a fixed category list. A typical order is extensions → enums/types → functions that tables need (used in defaults, check constraints, generated columns or domain checks) → tables in foreign-key order → deferred/cyclic FKs → remaining functions → triggers → views/materialized views → grants/policies. If a function itself depends on a table, create the table first and add the dependent default or constraint in a later migration. Prove the order by applying all migrations to an empty database. Prefer one table per file; a join table may live with its owning table when that is clearer. ORMs that generate migrations (TypeORM, Prisma, Drizzle) must still be run per table or feature step to produce multiple small migrations, and any SQL the ORM cannot express (functions, triggers, partial/expression indexes, check constraints, extensions) goes into hand-written migrations under the same history. Each migration must apply cleanly to an empty database in order, and include a working down/rollback step where the tool supports it.

### Schema coverage matrix

Build `docs/migration/schema-coverage.md` from the source schema export, one row per source object:

| Source object | Kind | Target | Migration file / code location | Test | Status |
| --- | --- | --- | --- | --- | --- |
| `public.projects` | table | table | `0007_create_projects.sql` | repository integration test | done |
| `public.set_updated_at()` | function | DB function | `0021_fn_set_updated_at.sql` | trigger test | done |
| `on_auth_user_created` → `handle_new_user()` | trigger on `auth.users` | registration use case | `modules/auth/register.service.ts` | signup test | done |
| `cron: nightly-cleanup` | pg_cron job | backend scheduled job | `jobs/cleanup.job.ts` | job test | done |

Kinds to enumerate: tables, columns, PK/FK/unique/check/exclusion constraints, indexes (including partial/expression), sequences and identity columns, defaults, enums/domains/composite types, views/materialized views, functions/procedures, triggers, extensions, `pg_cron` jobs, database webhooks, grants and RLS policies. Every row must be `done` (recreated in a migration or replaced in backend code with a test) or `retired` with an explicit reason; no object may be silently dropped. Triggers and functions that depend on `auth.*` or call external services are normally replaced by backend use cases or jobs rather than copied.

Verify coverage mechanically: compare the source schema export with the target database after running all migrations, for example by listing objects from `information_schema` and `pg_catalog` (`pg_class`, `pg_constraint`, `pg_indexes`, `pg_proc`, `pg_trigger`, `pg_type`, `pg_extension`, `pg_policies`) in both and diffing names and definitions for the `public` and other application schemas. Explain every difference in the matrix. Preserve PostgreSQL keys/relations, checks, indexes, enums, decimals/bigints, timestamps/time zones, JSON, sequences, views, functions, extensions and deletion semantics used by the product. Document API serialization choices (for example large integers/decimals as strings). Do not copy Supabase internal auth/storage schemas wholesale or silently omit unsupported types.

Baseline an existing target database deliberately; do not apply a fresh-schema migration blindly to populated tables. Freeze/archive competing Supabase/Drizzle histories with clear historical labels once the target history is verified. Remove obsolete migration commands/config/dependencies only after replacement. Disable automatic production schema synchronization; with TypeORM use `synchronize: false`. Review generated SQL and destructive changes. Run migrations as an explicit release job with concurrency control rather than from every application replica.

Keep queries in repositories/data access, parameterized and tenant-scoped. Define transactions for multi-step invariants and external side-effect coordination. Do not hold database transactions open while waiting for arbitrary external APIs; use idempotency/outbox/job patterns when the failure model warrants them. Consider race conditions, uniqueness, locking, pagination stability, indexes and representative query performance.

## Existing rows: separate from schema

Inventory source volume, sensitive fields and acceptable downtime. Define extraction permissions, snapshot timestamp, FK order, stable IDs/mapping tables, batch sizes, checkpoints, transforms, retry/idempotency and sequence resets. Back up and rehearse restoring the target. Import into an isolated target first; prevent rehearsal emails, webhooks and payments.

Reconcile row counts by table/tenant, key sets, checksums or aggregate totals, foreign-key orphans, null/enum conversions and representative relationships. Record source/target timestamps so comparisons are meaningful. Plan a write freeze or delta-capture/final-sync strategy; do not lose writes that occur after a snapshot. Preserve IDs referenced by storage, audit history and third-party systems, or migrate every reference through an explicit mapping.

A schema-only migration is not a populated application. If live access is absent, produce runnable import/reconciliation steps and mark data migration BLOCKED/NOT RUN. An empty target is acceptable only when the user explicitly chooses fresh-start scope.

## Identity migration and session security

Inventory actual auth flows and external identities. Choose a maintained auth/session library or provider that fits deployment. Map user IDs to application profiles/roles/ownership; migrate provider subject mappings and verification status deliberately. Preserve the original user UUIDs as target user IDs where possible so existing ownership/foreign-key values remain valid.

Supabase Auth stores password hashes in `auth.users.encrypted_password`, and the Lovable Cloud database export includes them. Hashes created by Supabase itself are normally bcrypt (`$2a$`/`$2b$`/`$2y$`), but Supabase can also verify imported Argon2 (`$argon2id$`/`$argon2i$`) and Firebase scrypt hashes, so a project that previously migrated users may contain several formats. Inspect the actual hash prefixes and count users per format, without printing hash values. For each format, confirm the chosen target auth library can verify it (including any parameters such as Firebase scrypt's signer key, salt separator, rounds and memory cost, which must be obtained from the user's earlier Firebase project if needed). Import every supported hash unchanged with its format recorded, and optionally rehash to the target's preferred algorithm after the next successful login. For formats the target cannot verify, agree a fallback with the user (for example a verification adapter for that format, or a guided password reset for only those users) before cutover. Do not force a password reset on everyone merely because the provider changes, and never convert or weaken hashes. Users without a hash (OAuth/magic-link/OTP-only) need their provider identities (`auth.identities`) mapped instead. Active sessions and refresh tokens are not portable: plan a forced re-login at cutover. OAuth providers must be re-registered with the new callback URLs and client configuration. Never print or log hashes; treat the export as a secret.

Replace dependencies on the `auth` schema explicitly: repoint foreign keys from `auth.users(id)` to the target users table, reimplement the `handle_new_user`-style signup trigger as a transactional registration use case (or a target-owned trigger), replace `auth.uid()`/`auth.jwt()` in defaults/functions/views with trusted request context or backend-set values, and move role/tenant claims held in user/app metadata into explicit tables. Inventory MFA factors, recovery codes, passkeys and account-linking requirements if present. Verify secure portability with the target provider; if unsupported, plan explicitly approved re-enrollment without silently disabling protection or locking users out. Never export private authenticators insecurely. Document session invalidation and user communication needs.

Prefer Secure, HttpOnly cookies for browser session/refresh credentials when compatible with the architecture. Define SameSite/domain/path/expiry, HTTPS/proxy handling, CSRF protection for state-changing requests, CORS credential policy and cross-site hosting constraints. If bearer access tokens are appropriate, minimize browser exposure and keep refresh credentials out of localStorage where possible. Do not silently preserve an insecure legacy token storage strategy for compatibility.

Rotate refresh tokens, store refresh/session secrets safely (hash where applicable), handle reuse/revocation and concurrent refresh, and revoke on logout/password or relevant account changes. Set appropriate expiry and audience/issuer/signature validation. Use a vetted password hashing implementation with current suitable parameters. Apply brute-force protection and avoid account enumeration.

For OAuth use library-supported state/nonce/PKCE as applicable, exact callback allowlists, shared expiring state/session storage or a secure stateless alternative that works across replicas, and single-use replay checks. Never keep essential OAuth state only in one process Map. Do not put access/refresh tokens in query strings or URL hashes; use a safe code/session exchange. Make verification/reset/invitation tokens short-lived and single-use. Do not ship a required login method as a permanent 501 stub when credentials are absent; implement it and mark operational verification blocked.

## Authorization parity

Translate RLS into explicit domain policies, or deliberately retain defensible database RLS with validated request context and connection-pool reset behavior. A backend service role that bypasses RLS is not sufficient authorization. Do not trust role/tenant/owner IDs sent by the client. Derive them from verified identity plus current membership/role data.

Test anonymous, owner, other user, member/non-member, tenant A/B, admin and suspended/archived accounts as applicable. Cover select/insert/update/delete, list/count/search, bulk actions, invited users, role downgrade, onboarding, file access, realtime, jobs and admin/service endpoints. Enforce both old USING and WITH CHECK intent; pre-read authorization alone must not allow a race or a forbidden ownership change. Choose intentional empty-result versus 403/404 semantics and align route guards/UI behavior.

Keep privileged admin operations backend-only, narrowly scoped, logged and authorized. Eliminate frontend-server service-role bypasses when business use cases move. Required production secrets have no known default; fail startup. Redact secrets/tokens/PII in logs and error bodies. Rotate exposed credentials when authorized; do not reproduce their values in reports. Add rate limits, payload bounds, secure headers, injection protections and SSRF/URL allowlists for features that fetch user-supplied remote resources.

## File storage

Choose object storage or durable local storage based on scale/deployment. Implement private/public policies, upload limits, MIME/content checks, safe object names, path traversal prevention, download disposition, signed URL expiration and cleanup. Apply actor/tenant checks to signing as well as upload/download/delete; do not expose a private bucket as public to make old links work.

Import actual objects separately from metadata. The Lovable Cloud database export contains `storage.objects` metadata rows but not the file bytes; download objects through authorized Storage API access (a backend-run script using a temporary credential the user provides), never by making buckets public. Translate `storage.objects` RLS policies into the files module's policy. Preserve or map keys, content type, ownership, cache headers and privacy; compare counts/bytes/checksums and sample downloads. Update URLs in rows, rich-text documents and frontend assets; expire/reissue old signed links rather than copying them. Define retry/checkpoints and orphan cleanup. Local disk is not shared across replicas: provide a durable shared strategy and backup if selected.

## Realtime and integrations

Replace only used realtime semantics. SSE may fit one-way role notifications; presence/broadcast/bidirectional use may require WebSockets. Authenticate subscriptions and filter by permission; recheck role changes, reconnect/resume events, and avoid cross-tenant fanout. Plan shared pub/sub when multiple instances require it; retain polling fallback if the original workflow relies on it.

Move used edge functions, frontend server business logic, scheduled jobs and integrations into backend feature modules or backend-owned workers. Preserve inputs, authorization, retries, concurrency, scheduling time zone and failure behavior.

Edge Functions are Deno code. When porting to Node, replace `Deno.serve` handlers with routes/controllers, `Deno.env.get` with validated config, `npm:`/`jsr:`/`esm.sh`/URL imports with locked package dependencies, and per-function CORS handling with the backend's CORS policy. Replace the function's service-role Supabase client with repository calls plus explicit authorization, and reproduce `verify_jwt` behavior with backend authentication. Secret values are not exported; list required names and ask the user for values or rotated replacements.

Replace database-side side effects deliberately: `pg_cron` jobs become backend scheduler/worker jobs (or remain in the target database only by explicit decision, with ownership documented); `pg_net`/HTTP calls and database webhooks become backend integrations or outbox-driven jobs with retries; Supabase Vault secrets move to the deployment secret manager. Disable each in rehearsal targets so imports do not fire real requests. Verify webhook signatures against raw body, deduplicate event IDs, handle retry/out-of-order delivery and use provider test modes. Move rate limiting to a shared backing store when multi-instance correctness requires it.

For Lovable Emails, move templates, triggers, retries, previews/webhooks and actual product mail, not only auth emails, to a chosen provider. Use Mailpit (maintained; MailHog is unmaintained but acceptable if already in use) or another chosen local SMTP capture when email is used; do not require an unused mail service. For the Lovable AI gateway (`ai.gateway.lovable.dev`, `LOVABLE_API_KEY`, OpenAI-compatible chat completions), choose a direct provider and map each gateway model name to an explicit replacement model. For AI/RAG, inventory models, prompts, embeddings/dimensions, vector indexes, streaming, tool calls, quotas and stored data. Choose a provider explicitly, test equivalent behavior and re-embed/reindex only with a plan when models change.

### Email templates follow the app's design

Apply this only when the app sends email. Every email the backend sends (auth emails such as sign-up confirmation, magic link, password reset, invitation and email change, plus all product/transactional emails) must look like it belongs to the frontend app, not like a default provider template.

1. **Inventory the existing emails and their content.** Find every email the app sends: Supabase Auth templates (configured in the Supabase dashboard under Auth email templates; on Lovable Cloud, ask the user for the content or screenshots if it cannot be exported), Lovable Emails, Edge Functions that render HTML or use a template library, and provider-side templates (Resend, SendGrid, Brevo and similar). Record for each: trigger, recipient, subject, body text, variables, links and language. Keep the existing wording unless the user asks for changes.
2. **Extract the design tokens from the frontend.** Read them from the actual source, never guess: brand colors from the Tailwind config and the CSS variables in the global stylesheet (for example shadcn/ui `--primary`, `--primary-foreground`, `--background`, `--foreground`, `--muted`, `--border`, `--destructive`), border radius, font family, logo and app name from the frontend's assets and title. Convert values to hex (CSS variables and `hsl(var(--x))` do not work reliably in email clients) and keep them in one backend file, for example `src/modules/notifications/email/theme.ts`, with a comment naming the frontend source file they came from. Follow the user's brand guidelines if they provide them.
3. **Build one shared layout and reusable parts.** Create a single email layout (header with logo and app name, content area, footer with company/app name, support contact and the reason the user received the email) and shared components for the primary button (primary color and foreground, matching radius), secondary link, heading, paragraph and divider. Every template uses this layout; no template has its own hard-coded colors.
4. **Write email-safe HTML.** Use an email framework rather than hand-written HTML, for example React Email (`@react-email/components` rendered on the backend) or MJML, or a template engine with CSS inlining (for example Handlebars plus `juice`). Requirements: table-based layout with inline styles produced by the tool, maximum width about 600px, responsive on mobile, web-safe font fallbacks after the app font, logo as an absolute HTTPS URL with width, height and `alt` (no base64 or local paths), sufficient color contrast, `lang` attribute, and a plain-text version of every email. Consider dark-mode clients: avoid logos that disappear on dark backgrounds.
5. **Use correct links and variables.** Links point to the new frontend's public URL from configuration (never a hard-coded or old Lovable/Supabase domain), include only the short-lived single-use token the flow needs, and every variable is escaped. Subjects and sender names use the app name.
6. **Preview and test.** Provide a preview route or script for development only (for example the React Email preview server, or a dev-only endpoint disabled in production) and send every template to Mailpit during development. Add tests that render each template with sample data, check the subject, required variables, link URLs and plain-text version, and snapshot the HTML. Manually compare each email's look with the frontend (logo, primary color, button style, font) and record the result in the verification evidence.


For MCP, identify whether external consumers use it; preserve used tools, auth scope and consent semantics. Move the server to the backend as appropriate. Update issuer/audience, discovery metadata, JWKS/authorization/token endpoints, redirect registrations and clients as one auth migration. Prefer a standards-compliant provider/library; do not invent an OAuth server. A live Supabase issuer remains a dependency even if no SDK remains. Remove MCP only on explicit scope change or evidence it is unused.

Remove preview auth brokers, generated auth attachers, wrappers and legacy dependencies only after import/runtime analysis and behavior replacement. Keep historical SQL/docs clearly marked; update current docs, package names, comments and deployment paths so they do not misstate the active system.

# Implement vertical features and retire compatibility code

## Foundation sequence

1. Recheck canonical paths and user changes. Prepare independent target repositories without overwriting existing work. Keep source provenance and a reversible baseline.
2. Resolve compatible runtime/package versions and one package manager per repository. Create strict TypeScript, formatting/linting and meaningful build/test scripts. Do not add success-returning placeholder scripts.
3. Implement config validation, structured logging with request IDs and redaction (backend.md), errors, database client/migration path, auth/session primitives, HTTP security, request correlation, health/readiness, and OpenAPI generation. Add the multi-stage `Dockerfile`, `.dockerignore` and `docker-compose.dev.yml` that spins up database, migrations and API (deployment.md) early, and start each repository's root `README.md`; keep both updated as features land.
4. Establish frontend routing/providers, shared API transport/error types, session handling, design primitives and contract consumption.
5. Implement one representative protected feature end-to-end, including a denied request and documented contract. Use it to validate boundaries before repeating across modules.

## Per-feature migration loop

For each inventory ID:
1. Reconstruct current visible behavior and business invariants from source/evidence. Identify related server functions, SQL, files, side effects and access policy.
2. Specify domain DTOs and endpoint(s), errors, permission matrix, pagination and transaction/idempotency requirements. Define acceptance cases before moving code.
3. Implement the feature's small migration files (one per table/function/trigger as in data-security.md) and update `schema-coverage.md`, then the module repository/data access. Add service/use-case logic and resource policy, then thin controller and routes/Nest controller bindings. Implement validation and response mapping.
4. Generate/update OpenAPI and verify endpoint/request/response coverage. Test the actual endpoint with representative and denied actors.
5. Implement typed feature API calls and hooks/composables through the shared transport. Move view logic into focused feature components; preserve routes, deep links, UX, accessibility and error semantics.
6. Move related frontend server functions, edge functions and privileged provider operations into backend modules/workers. Keep only rendering and explicitly designed thin adapters in frontend.
7. Test the complete journey and its failure paths. Compare with baseline behavior; investigate differences rather than assuming they are improvements.
8. Remove the replaced shim, legacy queries/types/SDK calls/config and packages after import/call-site checks. Regenerate contracts and lockfiles with the selected package manager. Update evidence and status.

## Compatibility adapters are temporary

If an incremental adapter is needed, record its callers, supported operations, scope, reason, security boundaries, feature exit conditions and removal test. Never expose arbitrary client-selected tables, unbounded filters or service-role access. Do not add new product features to a generic `/api/query` or `/api/rpc/:name` facade. The final target uses named domain APIs and DTOs; wrapping or renaming the old chain is not sufficient.

Retire `supabase.from/rpc/auth/storage`, `src/integrations/supabase/`, `lovable-tagger`, client clones, generated database row DTOs and misleading names only as callers move. Preserve necessary auth-header attachment, OAuth, storage and server-only checks in their replacements. A rename does not substitute for moving business rules or testing authorization.

## Realistic example of decomposition

If a ticket form previously creates a ticket, uploads attachments and sends email from frontend server functions, design the actual required failure model. A tickets module owns validation, access checks and ticket creation; a files module owns upload authorization/storage; notifications owns dispatch. Coordinate their public interfaces through a ticket use case. Use an outbox/job only when reliable asynchronous delivery is required. Provide a UI flow for upload failure and retries, and document whether attachments are staged before ticket creation. Do not make a controller issue unrelated table writes or return success after an untracked email failure.

## Cleanup and handover

Run import-aware and runtime-aware scans of both repositories, build outputs and deployment configuration. Review aliases, hardcoded remote URLs, issuers, package scripts, config and stale docs. Preserve historical migrations until the new path and imports are verified; archive rather than silently erase evidence. Remove competing active schema commands, duplicate lockfiles only after choosing the manager, and unused build plugins only after replacement production builds.

Do not delete a duplicate repository merely because it looks old. Correct setup/docs/CI to name the canonical trees. Keep only one current architectural description, link to historical audits, and update misleading RLS/Supabase session comments. Do not invent features from examples in this skill; each cleanup must have source evidence.

## Unused-code and empty-folder pass

Run this in **each target repository** before handover, and only on the target repositories. The original source repository is preserved; if the existing frontend repository was reused, removals happen through normal commits so history keeps them.

1. **Unused files, exports and dependencies.** Run an import-graph tool for the stack, for example `npx knip` (it has plugins for Vite, Next.js, Vue, NestJS, Vitest, Playwright and others; configure entry points so routes, CLI scripts, migrations and decorated Nest providers are not falsely reported). Use `npx depcheck` as a fallback for dependencies. Review each finding, then remove unused files, components, hooks/composables, exports, types, dependencies and devDependencies. Regenerate the lockfile with the selected package manager.
2. **Empty and placeholder folders.** List them with `find . -type d -empty -not -path '*/.git/*' -not -path '*/node_modules/*'`, and also find folders containing only `.gitkeep`, an empty `index.ts`, or empty test files. Delete each one unless a tool requires it (for example a migrations folder that is about to receive files). The illustrative trees in this skill are not a reason to keep empty `utils/`, `constants/`, `types/`, `state/` or `tests/` folders.
3. **Scaffold and template leftovers.** Remove generator demo code that the app does not use, for example NestJS `app.controller.ts`/`app.service.ts` "Hello World" and its default spec, Vite `src/assets/react.svg`, `public/vite.svg`, `App.css` demo styles, default `README` boilerplate, and Lovable `public/placeholder.svg` or Lovable-branded favicons/OG images when the app no longer references them.
4. **Leftover platform folders and files.** After their last consumer is replaced and history is archived: remove `src/integrations/supabase/`, the `supabase/` folder from the frontend (move `migrations/` and `functions/` source into the backend's `docs/migration/history/` as read-only evidence), `.lovable/`, `lovable-tagger` and its Vite plugin call, `@supabase/*` and `@lovable.dev/*` packages, the second lockfile, and old generated row types.
5. **Unused configuration.** Compare `.env.example` names with the variables actually read by config code; remove names nobody reads and add any that are read but missing. Remove unused package scripts, CI steps, Docker services, path aliases, ESLint/TS config entries and feature flags.
6. **Dead code paths.** Remove unreachable routes, unused API client functions, commented-out blocks, debug logging and temporary adapters whose exit condition is met.
7. **Prove nothing broke.** After the removals, run install from a clean state, type check, lint, build, the full test suite and the runtime API acceptance run. Restore anything that was actually needed and record why.

Never delete without evidence: dynamic imports, string-based route or provider registration, files used only by Docker/CI/migrations, and public assets referenced from HTML, CSS or the database can look unused. Record every removal (path, reason, evidence) in the final report's cleanup table.

If an external dependency blocks testing, finish reversible implementation only for slices whose schema, policy and behavior have sufficient evidence, and provide exact follow-up commands/configuration. Unknown policy/schema behavior blocks the affected implementation; do not substitute guesses and label them merely unverified. Mark the associated ledger items blocked rather than continuing to describe the full migration as done.

# Validation and reporting

The checkpoint advances only over work that is proven. Proof means commands that ran on the committed work branch, recorded with `sync_state.py validation`. Compilation alone does not prove behavior, and neither does a mock-only test or a test script that does not exist.

## Run checks on committed work

1. Commit each unit's changes on the work branch. Uncommitted changes make a validation invalid, because the script records the commit and the tree state.
2. Use the destination's own scripts (`package.json`, README, CI config). Discover them; do not invent them. Missing scripts are reported as `NOT_RUN` with the reason, never as a pass.
3. Record every check with its scope, name, exact command, result and a short outcome. Never include secrets in the evidence.

```bash
python3 <skill>/scripts/sync_state.py validation --scope backend --name tests --command "npm test" --result PASS --evidence "212 passed, 0 failed"
```

Results: `PASS`, `FAIL`, `BLOCKED` (cannot run: missing secret, Docker unavailable), `NOT_RUN`, `NOT_APPLICABLE` (with the reason in the evidence). `FAIL`, `BLOCKED` and `NOT_RUN` all keep the checkpoint where it is.

## Required checks

Per touched repository (always):

| Check | Typical command |
| --- | --- |
| Install from lockfile (when dependencies changed) | `npm ci` / `pnpm install --frozen-lockfile` / the destination's equivalent |
| Type check | `npm run typecheck` or `tsc --noEmit` |
| Lint, including the circular-dependency check if configured | `npm run lint` |
| Unit and integration tests | `npm test` |
| Production build | `npm run build` |

Depending on what the units changed:

| Change | Extra evidence |
| --- | --- |
| New or changed endpoint | HTTP integration test with a success case and a denied, invalid or not-found case; OpenAPI regenerated and validated; response matches the envelope |
| Authorization or RLS-derived rule | Tests for owner, other user, other tenant, anonymous and admin as applicable |
| Database migration | Migrations apply in order to a fresh isolated test database, and down migrations run where supported; repository tests pass against it. Never run them against a shared or production database |
| Frontend behavior | Component tests or an E2E journey for the changed flow, including one failure path |
| Both repositories in one unit | `integration` scope: the frontend against the running backend for the changed journeys (the destination's E2E suite, or a scripted API plus UI smoke test) |
| API contract change | Typed client regenerated in the frontend, and the frontend type check passes against it |
| Dependency change | Install, build and tests in that repository; audit output summarized |
| New env variable names | Config validation fails when the variable is missing; `.env.example` lists it |
| Email, jobs, webhooks | Rendering, job and signature tests with provider test modes or local capture; no real side effects |

Before marking units `verified`, confirm upstream parity: for each unit, the intent sentence is true in the destination, and the evidence shows it. List any part of the upstream behavior you could not reproduce. Such a unit stays `blocked` or becomes a conflict. It is never `verified`.

## Missing infrastructure or secrets

If a check needs a secret, an external service or Docker that is not available:
- implement what can be implemented and tested without it (mocks are acceptable for unit tests only);
- record the check as `BLOCKED` with the exact command and what is missing;
- keep the unit `blocked` with the reason. The checkpoint stops before it, and other units continue;
- tell the user exactly which names or infrastructure to provide. Never ask them to paste secret values into the chat; they put values in their own `.env`.

## Finalize and report

1. `sync_state.py finalize --dry-run` previews the checkpoint and problems; then run `finalize`.
2. Commit the written `.lovable-sync/sync-ref.json` files on the work branches.
3. `generate_report.py --write` saves `<workspace>/.lovable-sync/reports/<session>.md`.
4. In the reply, show the report's summary block, then:
   - changed modules per repository, with the sync branch names;
   - validation results, including anything `BLOCKED` or `NOT_RUN` and why;
   - units not finished, open conflicts needing decisions, and new env variable names needing values;
   - next actions: review and merge the sync branches (the user, or you if asked), provide values, answer the open conflicts, then `resume`.

Say "completed" only when `finalize` reports `completed`. A `partial` session is reported as partial, with the new checkpoint and what remains.

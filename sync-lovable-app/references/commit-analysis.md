# Commit analysis and work units

Contents: [Running the analysis](#running-the-analysis) · [Range status and edge cases](#range-status-and-edge-cases) · [Reading a commit](#reading-a-commit) · [Classification](#classification) · [Work units](#work-units) · [Lovable and Supabase signals](#lovable-and-supabase-signals)

## Running the analysis

```bash
python3 <skill>/scripts/analyze_commits.py --repo <source> --base <checkpoint> --target <branch-or-commit> --output <tmp>/analysis.json
```

Resolve the target explicitly. Use the configured branch, or a commit the user names. If the branch tracks a remote, `sync_state.py status` shows whether the local branch is behind it. When it is behind, say so. Fetch only when `allowFetch` is true or the user agrees, and never pull or check out in the source repository.

For each commit, the output lists the hash, parents, author, dates, subject and body, and the changed files with their status. Renames carry `oldPath` and similarity. For each file it also gives the added and deleted line counts and path hints. Per commit you also get:
- content signals and names (tables, RPCs, buckets, Edge Function calls, env variable names), taken from changed lines;
- SQL objects created, altered or dropped in `.sql` files;
- `package.json` dependency and script changes;
- reverts and cherry-pick markers, the patch-id, a `destructive` flag, and sensitive files (`.env*`), whose contents are never read.

The summary groups files touched by several commits, renames, deletions, duplicate patches, reverts, every env variable name, and sensitive files.

The script states facts. You still decide intent.

## Range status and edge cases

| Status or situation | Action |
| --- | --- |
| `no-new-commits` | Report "up to date" with the checkpoint and branch tip. Nothing else to do. |
| `target-missing` | The branch or commit does not resolve. Show the branches from `discover_repositories.py` and ask. |
| `base-missing` | The checkpoint object is not local: a shallow clone (`checks.shallow`), unfetched history, or a rewritten branch. Ask before running `git fetch --unshallow` or `git fetch`. If the commit truly no longer exists, follow [rewritten history](sync-state.md#rewritten-upstream-history). |
| `base-not-ancestor` | Rewritten history. Stop and follow [rewritten history](sync-state.md#rewritten-upstream-history). |
| Merge commit (`isMerge`) | The merged side-branch commits are already in the range as separate commits. Analyze those, then only the merge's own conflict resolution: `git show --remerge-diff <merge>` (Git 2.36+), or compare `git diff <first-parent> <merge>` with the side commits. |
| Revert (`reverts`, `revertsInRange`) | If the reverted commit is in the range, the pair cancels out. Record one unit covering both, as `ignored` with reason "reverted within range", after confirming the net diff is empty for those files. If the reverted commit was synced earlier, the revert is real work: remove or undo that behavior in the destination. |
| Cherry-pick or duplicate patch (`cherryPickedFrom`, `duplicatePatches`) | Implement once. Put all matching commits in the same unit. |
| Several commits on one feature (`filesTouchedByMultipleCommits`) | Read the net change (`git diff <first>^ <last> -- <paths>`) and implement the final behavior once. Do not replay each intermediate step. |
| Renamed or moved files | Follow `oldPath`. A rename alone usually changes nothing in the destination unless it changes a route, URL or public name. |
| Deleted files or functionality | Find the behavior in the destination. Remove it only when upstream clearly removed the feature (not a refactor) and the user approves removing behavior. Keep shared code that other features still use. |
| Sensitive files changed | Never open them. Report the variable *names* the code now uses (`envVarsReferenced`), and add them to the destination's config validation and `.env.example` with placeholder values. |
| Large ranges | Analyze in batches of related commits. Keep every unit in the session so resume works. |

## Reading a commit

For every commit, run `git show <hash>` (or `git show --stat` first for big commits) and read the surrounding code at that commit with `git show <hash>:<path>`. Answer:

1. Which user-visible behavior or rule changed? Who can do what, with which data, and what happens on errors?
2. Which data is read or written (tables, columns, buckets, external services)? Does access control change (RLS policies, `auth.uid()` checks, role checks)?
3. Which inputs are validated, and how (zod schemas, form rules, database constraints)?
4. Is the change functional, or is it tooling or generated output (regenerated `types.ts`, lockfile churn, `.lovable/` metadata, formatting)?
5. Does it depend on, fix or undo another commit in the range?

Write the answer as a one-sentence **intent**, for example: "An authenticated user can upload a profile image up to 2 MB (png/jpeg), which replaces their previous one and appears in the header." Never infer intent from the commit message alone. Lovable messages are often generic ("Changes", "Fix bug").

## Classification

| Category | Typical evidence | Expected action |
| --- | --- | --- |
| `ui` | components, pages, styles, assets only | Frontend: same visual result in the destination's component structure and design system |
| `feature` | UI plus data access, functions or migrations | Map across the frontend and backend |
| `bugfix` | small diff that corrects logic | Find the equivalent logic in the destination and fix it there, or confirm it is already correct |
| `validation` | zod/yup schemas, form rules, constraints | Backend validation (authoritative) plus the frontend form schema |
| `api` | Edge Functions, server functions, `.rpc()` | Backend module endpoint or use case, plus OpenAPI |
| `database` | `supabase/migrations/*.sql`, changed generated types | New ordered migration in the destination's tool, plus repository code |
| `auth` | `supabase.auth`, auth triggers, `auth.users` | Adapt to the destination's auth module. Never reintroduce Supabase Auth unless it was deliberately kept |
| `storage` | `.storage`, bucket policies | Destination file-storage module and its authorization |
| `realtime` | `.channel`, `postgres_changes` | Destination realtime mechanism (SSE/WebSocket) with permission filtering |
| `integration` | email, AI gateway, payments, webhooks | Backend integration module and provider config |
| `dependency` | `package.json` changes | Apply only if the destination needs the package for the synced behavior and it is compatible ([architecture-mapping.md](architecture-mapping.md#dependencies-and-configuration)) |
| `configuration` | build config, env names, Tailwind tokens | Port runtime-relevant parts. Design tokens go to the destination theme |
| `supabase-specific` | Supabase plumbing with behavior behind it | Extract the behavior and translate it. Never ignore it for being Supabase code |
| `lovable-tooling` | `.lovable/`, `lovable-tagger`, editor metadata | `ignored` with reason, when nothing in the migrated apps uses it |
| `docs`, `tests` | Markdown, tests | Port tests as destination tests where the behavior is synced. Docs usually `ignored` |
| `revert` | revert commits | See the edge cases above |

A commit can contain several categories. Classify by behavior, not by the largest file.

## Work units

Group commits into units by behavior:
- one unit per user-visible behavior or rule, even if it spans many commits;
- split a commit that mixes unrelated behaviors into several units (a commit may belong to several units);
- tooling-only commits form their own `ignored` unit;
- order units by dependency: schema → backend → frontend, and fixes after the features they fix.

For each unit, present the intent, commits, category, targets, destination mapping, tests and risk. Record it with `sync_state.py unit --id U<n> --title ... --intent ... --category ... --commit ... --targets ...` before starting work.

## Lovable and Supabase signals

| Signal or path | What it usually means |
| --- | --- |
| `src/integrations/supabase/types.ts` changed | The schema changed. Find the matching migration, or ask: Lovable Cloud may change the schema without a migration file in the repository |
| `supabase/migrations/*.sql` | Schema, RLS, functions, triggers: read every statement (the `sql` field lists objects) |
| `supabase/functions/<name>/` | Edge Function: server behavior, secrets (`Deno.env.get` names), `verify_jwt` in `supabase/config.toml` |
| `.from('<table>')`, `.rpc('<fn>')` | Data access that must become a backend endpoint/use case, never a direct query from the frontend |
| `auth.uid()`, `create policy`, `service_role` | Authorization semantics to reproduce as backend policy, with tests |
| `.storage.from('<bucket>')` | File behavior plus bucket policy |
| `functions.invoke('<name>')` | Frontend call to an Edge Function: maps to a backend API call through the central client |
| `ai.gateway.lovable.dev`, `LOVABLE_API_KEY` | Lovable AI gateway: maps to the destination's AI provider integration |
| `lovable-tagger`, `.lovable/`, `@lovable.dev/*` | Tooling: usually ignored |

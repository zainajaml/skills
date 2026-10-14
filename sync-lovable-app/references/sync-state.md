# Sync state, checkpoints and recovery

Contents: [Layout](#layout) · [sync-state.json](#sync-statejson) · [Sessions and units](#sessions-and-units) · [Checkpoint rule](#checkpoint-rule) · [Ledger and references](#ledger-and-destination-references) · [Work isolation](#work-isolation) · [Recovery](#recovery) · [Rewritten upstream history](#rewritten-upstream-history) · [Manual fallback](#manual-fallback)

## Layout

The canonical state lives in the workspace (the parent folder of the three repositories), not in any of them:

```text
<workspace>/
├── .lovable-sync/                 canonical state, its own local Git repository
│   ├── sync-state.json            configuration, single checkpoint, session history, baselines
│   ├── ledger.json                one record per upstream commit ever handled
│   ├── sessions/<session-id>.json units, conflicts, validations, events of one run
│   ├── reports/<session-id>.md    generate_report.py output
│   └── worktrees/                 optional isolated checkouts (ignored by its Git)
├── <lovable-source>/              read-only upstream
├── <frontend-repo>/.lovable-sync/sync-ref.json   lightweight reference, committed
└── <backend-repo>/.lovable-sync/sync-ref.json    lightweight reference, committed
```

Why the workspace: a sync branch may stay unmerged for a while, and state committed inside a destination repository would then disagree between branches. `sync_state.py` commits every change to `.lovable-sync/`'s own Git history, which gives an audit trail and a way to recover. Suggest that the user add a private remote to it if several machines or people run syncs. Repository paths are stored relative to the workspace, and each repository is identified by its root commits and remote URL, with credentials stripped.

Every mutating command takes `.lovable-sync/.lock`, writes each file through a temporary file and an atomic rename, and saves the checkpoint (`sync-state.json`) last. A crash therefore leaves either the old checkpoint or the new one, and rerunning `finalize` is safe. After a crash, `sync_state.py unlock` removes a stale lock. Check first that no other run is active.

## sync-state.json

```json
{
  "schemaVersion": 1,
  "stateId": "uuid shared with every sync-ref.json",
  "source": { "path": "lovable-original", "branch": "main", "remoteUrl": "https://github.com/org/app.git",
              "rootCommits": ["…"], "allowFetch": false, "lastSyncedCommit": "<full hash>" },
  "targets": {
    "frontend": { "path": "app-frontend", "branch": "main", "remoteUrl": "…", "rootCommits": ["…"],
                  "lastValidatedCommit": "<full hash>", "workBranch": "lovable-sync/<session-id>" },
    "backend":  { "…": "same shape" }
  },
  "lastSuccessfulSync": { "sessionId": "…", "sourceCommit": "<checkpoint>", "completedAt": "…",
                          "status": "baseline | partial | completed | rebaselined" },
  "activeSession": "<session-id> or null",
  "history": [ { "sessionId": "…", "status": "…", "startCommit": "…", "targetCommit": "…",
                 "checkpointAfter": "…", "destinationHeads": { "frontend": "…" } } ],
  "baselineHistory": [ { "commit": "…", "previous": "…", "reason": "…", "approvedByUser": true } ]
}
```

`source.lastSyncedCommit` is **the** checkpoint. `targets.*.lastValidatedCommit` is the destination commit at which the work up to that checkpoint was validated. It may still sit on an unmerged sync branch (`workBranch`); `verify` warns until it reaches `branch`.

## Sessions and units

`start` opens a session over `checkpoint..target` (topological order) and records every upstream commit in it. A **work unit** is one behavior, covering one or more upstream commits:

| Field | Meaning |
| --- | --- |
| `id`, `title`, `intent` | Stable ID (U1, U2…), short name, one-sentence functional requirement |
| `category` | `feature`, `ui`, `bugfix`, `validation`, `api`, `database`, `auth`, `storage`, `realtime`, `integration`, `dependency`, `configuration`, `supabase-specific`, `lovable-tooling`, `docs`, `tests`, `revert`, `other` |
| `commits` | Upstream commits the unit covers; a commit may belong to several units |
| `targets` | `frontend`, `backend` or both |
| `frontendCommits`, `backendCommits` | Destination commits that implement it |
| `status` | See below |
| `evidence`, `reason`, `decision`, `userApproved` | Why the status is true |

| Status | Resolved? | Requirements enforced by `unit` |
| --- | --- | --- |
| `pending`, `in-progress`, `implemented` | no | — (`implemented` = code done, not yet verified) |
| `verified` | yes | Destination commits for every target, plus evidence |
| `already-present` | yes | Evidence of where the behavior exists and how it was compared |
| `ignored` | yes | Reason (Lovable tooling, generated files, no runtime effect) |
| `declined` | yes | User decision + `--user-approved` (the user chose not to sync it) |
| `retained-local` | yes | User decision + `--user-approved` (destination behavior kept over upstream) |
| `deferred`, `blocked` | no | Reason (missing secret, infrastructure, an answer from the user) |

`deferred` is "later" and keeps the checkpoint where it is. If the user never wants the change, use `declined`. Conflicts (see conflict-resolution.md) link to a unit. An open conflict keeps its unit unresolved.

Record validations with `validation --scope frontend|backend|integration`. The script stores the work-branch commit, and for `integration` both repositories' commits, plus whether the tree had uncommitted changes. A validation is stale once code changes after it. A commit that only touches `.lovable-sync/` does not make it stale.

## Checkpoint rule

`finalize` advances the checkpoint to the newest upstream commit C in the session such that:

1. every upstream commit in `start..C` (all of C's new ancestors, including merged side branches) is resolved: covered by units that are all resolved and have no open conflict, or resolved in an earlier session and already merged in the destinations; and
2. no recorded validation for a touched repository, or for integration, is `FAIL`, `BLOCKED`, `NOT_RUN` or stale; every touched repository has at least one `PASS`; units that changed both repositories have a passing integration validation; and every recorded destination commit is on the current work branch.

If C is the target, the session is `completed`. If C lies between the start and the target, the session is `partial` and stays active for `resume`. Otherwise the checkpoint does not move. Every finalize also writes the per-commit ledger, so applied work beyond the checkpoint is never lost or repeated. The checkpoint never moves backwards.

Example: commits a101–a105, with a103 (backend invoice logic) blocked on a missing test secret. The checkpoint moves to a102, the frontend work for a104 stays recorded, and `resume` continues with a103. Once it is verified and validations pass at the new commits, `finalize` moves the checkpoint to a105.

## Ledger and destination references

`ledger.json` maps each upstream commit to `{sessionId, resolved, dispositions, units, waitingOn, frontendCommits, backendCommits}`. Dispositions are `frontend`, `backend`, `both`, `already-present`, `ignored`, `declined`, `retained-local`, `blocked`, `deferred` or `pending`. Use `sync_state.py show --commit <hash>` to answer "was this synced, and where?".

`finalize` writes `.lovable-sync/sync-ref.json` into each touched destination: the `stateId`, the checkpoint, and per session the checkpoint range, the applied units, the upstream commits and the destination commits. Commit it on the work branch (`chore(sync): record lovable sync <session-id>`). `verify` rejects a reference whose `stateId` differs, or which claims a checkpoint the canonical state never reached. That happens when the workspace state was lost or copied from another project. Stop and ask the user. Do not overwrite either side.

Destination commit messages carry trailers, which still connect commits to upstream if the state is lost:

```text
feat(invoices): add invoice totals endpoint

Lovable-Sync-Session: 20260115-101500-a1b2
Lovable-Upstream: 3f2c9e1d…, 8a7b6c5d…
```

## Work isolation

- **Clean destination:** create `lovable-sync/<session-id>` from the target branch (`git switch -c`).
- **Destination with uncommitted changes:** never stash, reset or commit the user's changes. Create a worktree from the target branch instead: `git -C <repo> worktree add <workspace>/.lovable-sync/worktrees/<repo>-<session-id> -b lovable-sync/<session-id> <target-branch>`. Install dependencies there and do all the work there.
- **Previous sync branch not merged yet:** the next session must start from it or wait for the merge, or it would redo or contradict that work. Ask the user. Start the new branch from the previous sync branch if they agree.
- Record the location with `sync_state.py workspace --role <role> --path <path> --branch <branch>`.
- **Frontend reused from the Lovable repository** (same Git history, different branch): treat the upstream branch as read-only and always work in a worktree of the frontend branch.
- Merging, pushing and removing worktrees happen only when the user asks (`git worktree remove` only after the work is merged).

## Recovery

| Situation | Action |
| --- | --- |
| Interrupted run (crash, closed session) | `status` → `unlock` if the lock is stale → `resume`. Check that each unit's destination commits exist; uncommitted changes in the work branch belong to the unit marked `in-progress`. Review them before continuing. |
| Frontend done, backend failed | Leave the frontend unit commits recorded and keep the unit `implemented` or `blocked`. Fix the backend in the same session, rerun validations, then `finalize`. |
| A recorded destination commit disappeared (branch rewritten or deleted) | `finalize` reports it. Ask the user whether to restore the branch or re-implement the unit. Never edit the session to hide it. |
| The user wants to stop | `close --reason`. The checkpoint is unchanged and the ledger keeps the applied work. A later `start` marks commits as previously resolved only if their destination commits are merged into the target branches. |
| State corrupted or deleted | Restore it from `.lovable-sync`'s Git history (`git -C .lovable-sync log`, then `git checkout <commit> -- <file>`). If it is gone, rebuild the checkpoint from the `sync-ref.json` files and commit trailers, and confirm it with the user through `init` with that baseline. |
| No new commits | `start` reports zero and opens no session. |

## Rewritten upstream history

When `verify` reports that the checkpoint is not an ancestor of the source branch, the upstream branch was rebased, amended or force-pushed:

1. Stop normal synchronization and explain what happened: run `analyze_commits.py --base <checkpoint> --target <branch>` and report its `divergence` counts.
2. Run `analyze_commits.py --repo <source> --find-equivalent <checkpoint> --target <branch>`. A candidate with the same patch-id, or a matching tree, is strong evidence. A match on subject or date alone is weak. If the old commit object is gone, compare recorded subjects from `ledger.json` with the new history.
3. Present the candidate, the evidence, and the upstream commits that are new compared with the ledger's records. Ask the user to approve the mapping.
4. Only after approval: `sync_state.py rebaseline --commit <new> --reason <...> --evidence <...> --user-approved`. If no candidate is trustworthy, ask the user for a baseline commit and treat any commits they cannot vouch for as unsynchronized.

Never switch to an unrelated commit silently, and never treat an unknown baseline as proof that the earlier commits were migrated.

## Manual fallback

Without Python, keep the same files and rules by hand: update the JSON with an atomic rename (write `file.tmp`, then `mv`), commit `.lovable-sync/` after each change, and use these git equivalents: `git rev-parse --verify <c>^{commit}`, `git merge-base --is-ancestor <checkpoint> <branch>`, `git rev-list --topo-order --reverse <checkpoint>..<target>`, `git diff-tree -r -M --name-status <commit>`.

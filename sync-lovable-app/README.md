# sync-lovable-app

An Agent Skill that keeps an already-migrated frontend (Next.js, React or Vue) and backend (Express or NestJS) in step with a Lovable + Supabase project that is still being developed. It is the ongoing companion to [lovable-supabase-migration](../lovable-supabase-migration/). Migration builds the new architecture once; this skill brings each new upstream change into that architecture without rebuilding or weakening it.

It does not copy files or cherry-pick commits. For every new Lovable commit, it works out what the change does, maps that onto the migrated modules, implements it in the destination's own conventions, validates it, and only then moves a single upstream checkpoint forward.

## Install

Copy this whole folder as `sync-lovable-app/` into the host's skills directory, keeping `references/` and `scripts/` beside `SKILL.md`:

| Host | Project location | Personal location |
| --- | --- | --- |
| Claude Code (Cursor also reads it) | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Codex and other Agent Skills hosts | `.agents/skills/` or `.codex/skills/` | `~/.agents/skills/` or `~/.codex/skills/` |

The personal location is usually the right one, because the skill works across three repositories. Requirements: git, and Python 3.8+ for the helper scripts (standard library only).

## Use

| Ask | What happens |
| --- | --- |
| "Use sync-lovable-app to set up syncing" | Lists the Git repositories in your workspace, lets you pick the Lovable app, frontend and backend (with branches) and the last synced Lovable commit, then creates `.lovable-sync/` in the workspace |
| "…show the sync status" | Checkpoint, upstream tip, pending commits, repository states, open problems |
| "…analyze the new Lovable commits" / "…preview the sync" | Plan only: work units, intent, destination mapping, conflicts, tests. Nothing is written |
| "…sync the new Lovable changes" | Implements the plan on `lovable-sync/<session>` branches, validates, advances the checkpoint, writes a report |
| "…resume the sync" | Continues an interrupted or partial session |
| "…validate the last sync" | Reruns checks on the sync branches without taking new upstream changes |
| "…show the sync history" | Past sessions, baselines and reports |

In Claude Code, `/sync-lovable-app status` (or `analyze`, `sync`, …) also works.

Nothing is pushed, merged or deployed unless you ask. The Lovable repository is never modified.

## What it stores

`<workspace>/.lovable-sync/` is its own local Git repository. It holds the checkpoint, a per-commit ledger, session records and reports. Each destination repository gets a small committed `.lovable-sync/sync-ref.json`, and the sync commits carry `Lovable-Sync-Session:` and `Lovable-Upstream:` trailers. See [references/sync-state.md](references/sync-state.md).

## Contents

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Modes, safety rules and the A–F workflow |
| `references/` | State and recovery, commit analysis, architecture mapping, conflicts, validation |
| `scripts/discover_repositories.py` | Finds and describes repositories in a workspace |
| `scripts/analyze_commits.py` | Range checks and per-commit facts; equivalent commits after rewritten history |
| `scripts/sync_state.py` | Checkpoint, sessions, units, conflicts, validations, finalize, history |
| `scripts/generate_report.py` | Markdown sync report |
| `agents/openai.yaml` | Optional Codex/ChatGPT display metadata |

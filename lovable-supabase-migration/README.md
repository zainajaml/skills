# lovable-supabase-migration

An Agent Skill that analyzes a Lovable or Supabase-backed app and migrates it into separate, feature-based frontend (Next.js, React or Vue) and backend (Express or NestJS) repositories.

## Install

Copy this whole folder as `lovable-supabase-migration/` into the host's skills directory, keeping `references/` and `scripts/` beside `SKILL.md`:

| Host | Project location | Personal location |
| --- | --- | --- |
| Claude Code (Cursor also reads it) | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Codex and other Agent Skills hosts | `.agents/skills/` or `.codex/skills/` | `~/.agents/skills/` or `~/.codex/skills/` |

One copy in `.claude/skills/` covers Claude Code, Cursor and Codex. The core files are host-neutral; `agents/openai.yaml` is optional Codex/ChatGPT metadata that other hosts ignore.

## Use

Start with a prompt such as:

> Use lovable-supabase-migration to analyze this project, ask me for the target stack, and migrate it into separate modular repositories.

Ask for "analysis and plan only" to stop before any code is written.

## Contents

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Workflow, gates and non-negotiable outcomes |
| `references/` | Phase-specific detail, loaded when the workflow reaches that phase |
| `scripts/schema-catalog.sql` | Lists database objects so source and target schemas can be diffed |
| `scripts/auth-hash-formats.sql` | Counts Supabase Auth users per password hash format without printing hashes |
| `scripts/find-empty-dirs.sh` | Finds empty and placeholder-only folders before handover |
| `agents/openai.yaml` | Optional Codex/ChatGPT display metadata |

## License

MIT, see [LICENSE](LICENSE).

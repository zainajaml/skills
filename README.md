# Skills for moving off Lovable + Supabase

Agent Skills that help an AI coding agent (Claude Code, Cursor, Codex and other Agent Skills hosts) turn apps built with Lovable into professionally structured projects:
- a frontend-only Lovable site becomes a clean React, Next.js, Vue or Angular project;
- a Lovable + Supabase app becomes separate frontend and backend repositories, which are kept up to date while development continues in Lovable.

| Skill | Use it to |
| --- | --- |
| [lovable-supabase-migration](lovable-supabase-migration/) | Migrate a Lovable/Supabase app once, into an independent frontend (Next.js, React or Vue) and backend (Express or NestJS) |
| [sync-lovable-app](sync-lovable-app/) | Bring new commits from the original Lovable app into the migrated repositories, again and again, without redoing the migration |
| [lovable-migration](lovable-migration/) | Rebuild a frontend-only Lovable app (landing page, company site, portfolio, static dashboard) as a modular React, Next.js, Vue or Angular project that looks and behaves the same |

## What is a skill?

A skill is a folder of instructions that an AI agent loads when a task matches it. The core is a `SKILL.md` file. Its frontmatter (`name`, `description`) tells the agent when to use the skill, and its body tells the agent how to do the work. Longer guidance lives in `references/` and is read only when needed. `scripts/` holds helper programs for steps that must be exact, such as Git history checks or state files.

You do not run a skill yourself. You ask the agent in plain language ("migrate this Lovable app", "sync the new Lovable changes"), and the agent follows the skill.

## Which skill do I need?

| Your Lovable app… | Use |
| --- | --- |
| has no backend: no Supabase, no login, no database (forms posting to Formspree and similar are fine) | **lovable-migration** |
| uses Supabase, Lovable Cloud, auth, Edge Functions or other backend features | **lovable-supabase-migration**, then **sync-lovable-app** for later changes |

Not sure? Ask for lovable-migration. Its first step classifies the project and stops with an explanation if it finds a backend.

## How the backend skills fit together

```text
 Lovable app (Supabase)
        │
        │  1. lovable-supabase-migration   (once)
        ▼
 ┌────────────────┐   ┌────────────────┐
 │ frontend repo  │   │  backend repo  │   your architecture, your repos
 └────────────────┘   └────────────────┘
        ▲                      ▲
        └──────────┬───────────┘
                   │  2. sync-lovable-app   (every time Lovable gets new commits)
        Lovable app keeps changing
```

1. **Migration** analyzes the Lovable app, asks you which stack you want and what to call the repositories, then builds two independent repositories. Each is organized by feature, and the backend owns the API, auth, database migrations, OpenAPI, Docker and tests. The skill checks its work against a test database before handover.
2. **Synchronization** remembers the last Lovable commit that is already in your migrated apps. For each new commit, it works out what the change does (not just which files changed), finds where that behavior lives in your repositories, and implements it in their style. It validates the result and only then moves its checkpoint forward. Lovable decides *what* changed; your migrated repositories decide *how* it is built.

## Requirements

- An AI coding agent that supports Agent Skills: Claude Code, Cursor, or Codex and other compatible hosts.
- Git.
- Python 3.8+ for the `sync-lovable-app` and `lovable-migration` helper scripts (standard library only).
- Node.js. For `lovable-migration`, network access to install Playwright's Chromium for the visual parity check.
- For full-stack migration verification: Docker, plus `psql` if you want to use the schema-diff script.

## Install

Clone this repository, then copy or symlink the skill folders into your agent's skills directory:

```bash
git clone git@github.com:zainajaml/skills.git
cd skills

# personal install for Claude Code (also read by Cursor)
mkdir -p ~/.claude/skills
ln -s "$PWD/lovable-supabase-migration" ~/.claude/skills/lovable-supabase-migration
ln -s "$PWD/sync-lovable-app" ~/.claude/skills/sync-lovable-app
ln -s "$PWD/lovable-migration" ~/.claude/skills/lovable-migration
```

With a symlink, `git pull` here updates the installed skills. Copy the folders instead if you want a fixed version. Keep each folder whole, with `SKILL.md`, `references/`, `scripts/` and `assets/` together.

| Host | Project location | Personal location |
| --- | --- | --- |
| Claude Code (Cursor also reads it) | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Codex and other Agent Skills hosts | `.agents/skills/` or `.codex/skills/` | `~/.agents/skills/` or `~/.codex/skills/` |

The personal location is usually best: the skills work across several repositories, not inside one project. Each skill's `agents/openai.yaml` is optional Codex/ChatGPT display metadata that other hosts ignore.

## Usage

Open your agent in the folder that holds your Lovable app (or its parent folder) and ask in plain language. In Claude Code you can also type `/lovable-migration`, `/lovable-supabase-migration` or `/sync-lovable-app <mode>`.

**Rebuild a frontend-only site**

> Use lovable-migration to analyze this Lovable project, ask me which framework and styling I want, and rebuild it as a modular project that looks the same.

The agent captures screenshots of the original first. It asks for the framework (React, Next.js, Vue or Angular), language, styling and UI library, package manager and output folder, then builds the new project in a separate folder. Finally, it compares every route at mobile, tablet and desktop sizes against the original, and writes `MIGRATION_REPORT.md`.

**Migrate a full-stack app (once)**

> Use lovable-supabase-migration to analyze this project, ask me for the target stack, and migrate it into separate modular repositories.

Ask for "analysis and plan only" to stop before any code is written.

**Sync (whenever Lovable has new commits)**

> Use sync-lovable-app to set up syncing.

On the first run, the agent lists the Git repositories in your workspace. You pick which one is the Lovable app, which is the frontend and which is the backend, with their branches. Then you give the last Lovable commit that is already in the migrated apps.

After that, use:

| Ask | What happens |
| --- | --- |
| "…show the sync status" | Last synced commit, new Lovable commits waiting, repository states |
| "…analyze the new Lovable commits" / "…preview the sync" | A plan only; nothing is written |
| "…sync the new Lovable changes" | Implements the changes on `lovable-sync/<session>` branches, validates them, moves the checkpoint and writes a report |
| "…resume the sync" | Continues an interrupted or partly finished sync |
| "…validate the last sync" / "…show the sync history" | Re-checks, or lists past syncs |

## Safety by design

- **Your code stays yours.** No skill resets, cleans, stashes or overwrites existing work. The original Lovable project is never modified by a migration. Sync work happens on separate branches, or in worktrees when you have uncommitted changes.
- **The Lovable repository is read-only** for synchronization.
- **Nothing is pushed, merged, deployed or run against production** unless you ask.
- **Secrets stay secret.** Only environment variable *names* are recorded, `.env` files are never read, and credentials are stripped from remote URLs.
- **Honest status.** Checks that were not run are reported as not run, never as passed. The sync checkpoint only moves over changes that are implemented and validated. A frontend rebuild is only "complete" when its screenshots match the original, or each difference was approved by you.
- **You decide the important things:** the stack, repository names, baselines, conflicts between Lovable and your own improvements, and anything high-impact.

## Repository layout

```text
skills/
├── README.md                        this file
├── lovable-supabase-migration/
│   ├── SKILL.md                     workflow, gates, non-negotiable outcomes
│   ├── README.md
│   ├── agents/openai.yaml
│   ├── assets/icon.svg
│   ├── references/                  discovery, architecture, backend, frontend, data/security, …
│   └── scripts/                     schema catalog diff, auth hash formats, empty-folder finder
├── sync-lovable-app/
│   ├── SKILL.md                     modes, setup, A–F sync workflow
│   ├── README.md
│   ├── agents/openai.yaml
│   ├── assets/icon.svg
│   ├── references/                  sync state, commit analysis, mapping, conflicts, validation
│   └── scripts/                     discover repositories, analyze commits, sync state, report
└── lovable-migration/
    ├── SKILL.md                     scope gate, six phases, safety rules
    ├── README.md
    ├── agents/openai.yaml
    ├── assets/                      icon, visual-parity Playwright kit, report template
    ├── references/                  analysis, React/Next.js/Vue/Angular, styling, components, validation
    └── scripts/                     project analyzer, report generator
```

## Adding or changing a skill

- One folder per skill, named like its `name` field: lowercase words joined by hyphens.
- `SKILL.md` starts with frontmatter. `description` says what the skill does **and when to use it**, because that is what the agent matches on.
- Keep `SKILL.md` short (about 100–200 lines) and move detail into `references/`, linked from the step that needs it.
- Use scripts for steps that must be exact or repeatable, and test them.
- Write for any host: no tool-specific commands or frontmatter that other agents cannot use.
- Each skill's own `README.md` covers install details and its file list.

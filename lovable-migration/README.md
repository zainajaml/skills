# lovable-migration

An Agent Skill that rebuilds a **frontend-only** Lovable app (landing page, company or marketing site, portfolio, static dashboard, UI prototype) as a clean, modular, production-ready **React, Next.js, Vue or Angular** project. The result looks and behaves the same as the original.

It is not a redesign tool. The agent analyzes the original, asks which framework, language, styling and UI library you want, extracts components, layouts and static data, migrates routes, styles, assets and interactions, and then proves parity: it compares screenshots of every route at mobile, tablet and desktop sizes against the original.

Apps that use Supabase, authentication or a backend are detected and handed to [lovable-supabase-migration](../lovable-supabase-migration/) instead, unless you agree on a frontend-only strategy.

## Install

Copy this whole folder as `lovable-migration/` into the host's skills directory, keeping `references/`, `scripts/` and `assets/` beside `SKILL.md`:

| Host | Project location | Personal location |
| --- | --- | --- |
| Claude Code (Cursor also reads it) | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Codex and other Agent Skills hosts | `.agents/skills/` or `.codex/skills/` | `~/.agents/skills/` or `~/.codex/skills/` |

Requirements: Node.js, Python 3.8+ for the analyzer and report scripts (standard library only), and network access to install Playwright's Chromium for the parity check.

## Use

> Use lovable-migration to analyze this Lovable project, ask me which framework and styling I want, and rebuild it as a modular project that looks the same.

The agent will:
1. analyze the project and show an assessment (routes, sections, design tokens, interactions, external services, Lovable leftovers, risks);
2. capture baseline screenshots of the original;
3. ask for the framework, language, styling and UI library, package manager and output folder, suggesting defaults;
4. present the folder structure, route map and component map;
5. build the new project in a separate folder, page by page, rerunning the parity check as it goes;
6. run install, type check, lint, build, tests, the route and visual parity check, accessibility and SEO checks;
7. hand over `MIGRATION_REPORT.md`, whose status says "complete" only when every check passed and every visual difference was approved.

Your original project is never modified. Nothing is committed, pushed or deployed unless you ask.

## Contents

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Scope gate, safety rules, the six phases |
| `references/project-analysis.md` | Discovery checklist, Lovable project anatomy, scope decisions, risks |
| `references/{react,nextjs,vue,angular}-architecture.md` | Target structure, routing, state, SEO and assets per framework |
| `references/styling-migration.md` | Compatible styling and UI choices, design tokens, keeping the design identical |
| `references/component-extraction.md` | What to extract, props, static data, interactions, forms |
| `references/validation.md` | Baseline, parity run, required checks, accessibility, SEO, report |
| `scripts/analyze_project.py` | Read-only project inventory and frontend-only classification |
| `scripts/generate_report.py` | Renders the handover report and computes its status |
| `assets/visual-parity/` | Playwright kit: per-route, per-viewport screenshot and page-facts comparison |
| `assets/report-template.json` | Report data to fill in during the migration |
| `agents/openai.yaml` | Optional Codex/ChatGPT display metadata |

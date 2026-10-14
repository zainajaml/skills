---
name: lovable-migration
description: >-
  Rebuild a frontend-only Lovable app (landing page, marketing or company site,
  portfolio, static dashboard, UI prototype) as a clean, modular, production-ready
  React, Next.js, Vue or Angular project that looks and behaves exactly like the
  original. Analyzes the project, asks for the target framework, language, styling
  and UI library, extracts components, layouts and static data, migrates routes,
  styles, assets and interactions, and proves visual parity with screenshots at
  mobile, tablet and desktop sizes. Use when the user wants to restructure,
  modernize, clean up, componentize or convert a Lovable-generated frontend. Apps
  that use Supabase, auth or a backend go to lovable-supabase-migration instead.
---

# Lovable frontend migration

**The migrated app must look and behave like the original; only its internal architecture and code quality change.** This is not a redesign. Do not copy Lovable files into a new folder and call it done: understand each page, then rebuild it in the target framework's conventions.

## Scope gate

This skill is for frontend-only apps. It never adds backends, databases, Supabase, auth servers, new API endpoints or cloud infrastructure. The analyzer classifies the project; confirm the classification by reading the code it cites:

| Classification | Action |
| --- | --- |
| `frontend-only` | Proceed. |
| `frontend-with-external-calls` | Proceed. Keep third-party client services (form services such as Formspree or EmailJS, analytics, maps, embeds) working exactly as before, call them through a small service module, and list them in the report. |
| `backend-dependent` (Supabase, auth, Lovable Cloud, Edge Functions, Lovable AI gateway, own API) | **Stop before changing anything.** Report what was found and where. Offer two options: use the **lovable-supabase-migration** skill, or an explicitly agreed frontend-only strategy (keep the existing calls unchanged behind a service module, or replace them with clearly labeled mocks if the user accepts losing that behavior). Never remove the functionality silently. |

## Safety rules

- The original project is read-only. Never edit, reformat, install into, build in, delete or overwrite it. Build it from a temporary copy ([validation.md](references/validation.md#1-capture-the-baseline-first)). Create the migrated app in a new folder the user confirms. Working in place on a new branch requires the user's explicit request, and never touches uncommitted changes.
- Do not invent content, images, links or features. Keep every text, image, URL, route and interaction. Never replace real images with placeholders.
- Do not redesign. Any visible difference must be explained, and the user must approve it.
- Do not add dependencies without a reason (state management, icon sets, UI kits). Remove Lovable tooling (`lovable-tagger`, `componentTagger`, Lovable meta images) only after confirming nothing needs it.
- Do not commit, push or deploy unless the user asks. Never read or print `.env` values; carry over variable names only.
- Never report a build, test, route or visual check as passed unless it ran and passed.

## Tools

`<skill>` is the folder containing this file.

| Tool | Use |
| --- | --- |
| `python3 <skill>/scripts/analyze_project.py <original> --format markdown` (or `--output analysis.json`) | Inventory: framework, dependencies by purpose, routes, pages, components, unused ui primitives, assets, fonts, head/SEO, theme, interactions, env names, Lovable tooling, backend/network evidence, classification |
| `<skill>/assets/visual-parity/` | Playwright kit: baseline screenshots from the original, then pixel comparison of the migrated site per route at 375/768/1440 px, plus status, title, description, heading outline and new runtime errors |
| `<skill>/assets/report-template.json` + `python3 <skill>/scripts/generate_report.py` | Handover report; its status is computed from the recorded checks |

Without Python, do the same inventory by hand with the checklist in [project-analysis.md](references/project-analysis.md).

## Phase 1: Discovery

1. Run the analyzer on the original and read every file it flags: routes, the largest pages, network and backend evidence, interactions. Read [project-analysis.md](references/project-analysis.md).
2. Apply the scope gate.
3. Capture the parity baseline from the original **before** any migration work ([validation.md](references/validation.md#1-capture-the-baseline-first)). If the original cannot be built or served, say so, and ask whether a deployed URL of the same version can serve as the baseline.
4. Present the assessment: what the site is, routes, sections per page, styling and design tokens, fonts, assets, interactions, SEO tags, external services, Lovable leftovers and risks.

## Phase 2: Configuration

Ask only what is not already known, in one message, with defaults suggested from the analysis:

1. **Framework:** React (Vite), Next.js (App Router), Vue 3 or Angular. Never assume one.
2. **Language:** TypeScript (default when the original uses it) or JavaScript.
3. **Styling and UI library:** only combinations compatible with the framework. Default to keeping the original system (Lovable: Tailwind + shadcn/ui), because that is the lowest-risk way to keep the design ([styling-migration.md](references/styling-migration.md#compatibility)). Warn that switching to Bootstrap, MUI, Ant Design, Chakra or Angular Material changes how components look.
4. **Package manager:** suggest the one matching the original's lockfile.
5. **Output directory:** suggest a sibling folder of the original. It must not exist yet.

## Phase 3: Architecture plan

Read the target framework's reference ([React](references/react-architecture.md), [Next.js](references/nextjs-architecture.md), [Vue](references/vue-architecture.md), [Angular](references/angular-architecture.md)) and [component-extraction.md](references/component-extraction.md). Present:
- the folder tree, sized to the app (a one-page site gets a small tree);
- a route map: original path → target route file, with layouts, the 404 page, redirects and anchor links;
- a component map: each original page → its sections and shared components, plus the static data files;
- dependency changes and their reasons, design tokens to extract, and expected risks.

When the user asks for a migration, the plan does not need separate approval, unless it includes visible changes or dropped behavior.

## Phase 4: Implementation

Scaffold with the framework's official generator, configure strict linting and formatting, then migrate in this order:
1. **Design foundation:** tokens, global styles, fonts, dark mode, breakpoints ([styling-migration.md](references/styling-migration.md)).
2. **Layouts:** header, footer, navigation and the router.
3. **Pages,** one at a time: sections → shared components → static data → interactions. Rerun the parity check per page as you go.
4. **Assets, head/SEO, external service modules, 404 page.**
5. **Cleanup:** no unused files, components, ui primitives, dependencies, env names, Lovable tooling or scaffold demo code.

Add a README covering setup, scripts, structure and deployment.

## Phase 5: Validation

Run everything in [validation.md](references/validation.md): install, type check, lint, build, tests, the route and visual parity run, the interaction checklist, accessibility, SEO and assets. Fix differences, rebuild and rerun. Each remaining difference is either fixed, or explained and approved by the user.

## Phase 6: Handover

Fill in a copy of `assets/report-template.json` while you work, then render it with `generate_report.py --output MIGRATION_REPORT.md` in the migrated project. Give the user the summary: status, structure before and after, migrated routes, main components, dependency changes, check results (including anything not run), visual parity results, limitations, and the setup, dev, build and deploy commands. If the report says "incomplete", say so plainly.

## References

| Need | Read |
| --- | --- |
| Discovery checklist, Lovable project anatomy, scope decisions, assessment template | [project-analysis.md](references/project-analysis.md) |
| Target structure, routing, state, head/SEO, assets per framework | [React](references/react-architecture.md) · [Next.js](references/nextjs-architecture.md) · [Vue](references/vue-architecture.md) · [Angular](references/angular-architecture.md) |
| Compatible styling/UI choices, token extraction, keeping the design identical | [styling-migration.md](references/styling-migration.md) |
| What to extract, props, static data, interactions | [component-extraction.md](references/component-extraction.md) |
| Baseline, parity run, checks, accessibility, SEO, report | [validation.md](references/validation.md) |

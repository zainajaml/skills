# Validation

Contents: [1. Baseline](#1-capture-the-baseline-first) · [2. Parity run](#2-run-the-parity-check) · [3. Required checks](#3-required-checks) · [4. Interactions](#4-interaction-checklist) · [5. Accessibility, SEO, performance](#5-accessibility-seo-and-performance) · [6. Report](#6-record-and-report)

Nothing is reported as passed unless it ran and passed. A check that cannot run is reported as `BLOCKED` or `NOT_RUN`, with the reason.

## 1. Capture the baseline first

Capture the original's screenshots before migrating, so every comparison is against the real original.

1. Build the original from a **temporary copy** (installing and building inside the original would change it):
   ```bash
   tmp=$(mktemp -d)
   rsync -a --exclude node_modules --exclude dist --exclude .git <original>/ "$tmp/original/"
   cd "$tmp/original" && npm ci && npm run build && npx vite preview --port 4173 --strictPort
   ```
   Use the original's package manager and its frozen-lockfile install (`npm ci`, `pnpm install --frozen-lockfile`, `bun install --frozen-lockfile`, `yarn install --immutable`). If the build needs env variables, ask the user. If it cannot be built, ask whether the published site (for example `<project>.lovable.app`), at the same version, can be the baseline.
2. Set up the parity kit in another temporary folder, outside both projects:
   ```bash
   cp -r <skill>/assets/visual-parity "$tmp/parity" && cd "$tmp/parity"
   npm init -y && npm i -D @playwright/test && npx playwright install chromium
   ```
3. Write `routes.json` (see `routes.example.json`), using the analyzer's routes:
   - every static route, plus one concrete URL for each dynamic route;
   - an unknown path for the 404 page;
   - key interactive states, through `actions` (open mobile menu, open FAQ item, dark mode via `COLOR_SCHEME=dark`), limited with `projects` (`["mobile"]` for a mobile menu);
   - `mask` for live or random content (maps, videos, autoplay carousels, dates) and `hide` for overlays that differ per visit (cookie banners, chat widgets).
4. Capture the baseline: `BASE_URL=http://localhost:4173 npx playwright test --update-snapshots=all`. This stores screenshots and page facts (title, description, `lang`, h1–h3 outline, existing runtime errors) under `baseline/`. If the original has dark mode, copy the kit to a second folder (`parity-dark`) and capture there too. If the theme follows the system setting (`next-themes` with `defaultTheme="system"`, or `prefers-color-scheme`), set `COLOR_SCHEME=dark`. If it only changes through a toggle, add a `click` action on the toggle to each route in that folder's `routes.json`.

## 2. Run the parity check

Build and serve the migrated app in production mode (for Next.js static export, serve `out/`; for SSR, `next start`; for Angular, serve `dist/<app>/browser` with a static server or `ng serve --configuration production`), then:

```bash
BASE_URL=http://localhost:4174 npx playwright test          # in $tmp/parity
npx playwright show-report report                          # expected / actual / diff images
```

For each route and viewport (375, 768, 1440 px) the check:
- requires HTTP status < 400 (deep links work);
- requires the same title, meta description, `lang` and h1–h3 outline;
- reports runtime errors and failed requests that the original did not have;
- compares a full-page screenshot with the baseline (default: at most 1% of pixels differ, `MAX_DIFF_RATIO`).

Rerun it after each migrated page, not only at the end. For every failure, open the diff and find the cause. Usual suspects: a missing font weight, a changed default line-height or border color, wrong class merge order, a missing breakpoint, an image size, or missing scrollbar or gap styles. Fix it. A difference may remain only if it is explained and the user approves it, for example an accessibility fix that changes contrast. Raising the threshold to hide a difference is not allowed. Anti-aliasing noise below the threshold is normal.

Without Playwright (no browser download possible), fall back to manual screenshots: Chrome headless `google-chrome --headless --screenshot=<file>.png --window-size=1440,4000 <url>` per route and viewport, for both sites, compared side by side. Record visual parity as checked manually, with the routes compared, never as automated PASS.

## 3. Required checks

| Check | How | Evidence |
| --- | --- | --- |
| Install | Frozen-lockfile install from a clean state | Success, no peer-dependency errors |
| Type check | `tsc --noEmit` / `vue-tsc --noEmit` / the Angular build's type check | 0 errors |
| Lint and format | The project's ESLint (or framework equivalent) and Prettier check | 0 errors; warnings explained |
| Build | Production build | Success; output size compared with the original's `dist` |
| Tests | Component tests for extracted components with logic (menus, accordions, forms, filters), plus the parity run | Results |
| Routes | Parity run statuses, plus a check of every navigation link (header, footer, buttons) | All routes reachable, anchors scroll to the right section, 404 page shown for unknown paths |
| Assets | Parity run (no failed requests), and a search for references to removed files | No 404s for images, fonts or icons |
| Interactions | Checklist below | Each item checked |
| Accessibility | `npx @axe-core/cli <url>` per route, or Lighthouse accessibility, plus keyboard checks | No new violations compared with the original; fixes listed |
| SEO | Parity facts, head review, robots and sitemap present when the original had them | Same tags per page |
| Unused code | `npx knip` (React/Vue/Next) or a search for every component, data file and dependency | Nothing unused remains |

## 4. Interaction checklist

Check each interaction in both the original and the migrated app, at mobile and desktop sizes:
- navigation: menu toggle, close on link click and on Escape if the original did, active link style, sticky header, anchor scrolling and offset;
- disclosure widgets: accordions (single or multiple open), tabs, dropdowns, dialogs and sheets (focus trap, Escape, overlay click, scroll lock), tooltips;
- carousels: autoplay timing, arrows, dots, swipe, loop;
- forms: required fields, validation messages and timing, disabled and loading state, success and error states, the same submission target;
- theme toggle and persistence (storage key unchanged), reduced-motion behavior;
- on-scroll animations, counters, hover and focus states, `target="_blank"` links.

Turn the important ones into tests (Testing Library, Vue Test Utils, Angular TestBed or Playwright).

## 5. Accessibility, SEO and performance

- **Accessibility:** semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page, alt text on meaningful images (empty alt on decorative ones), labels on inputs and icon-only buttons, visible focus, keyboard access for every control, `prefers-reduced-motion` respected, contrast checked. Fixes that change how the page looks need the user's approval.
- **SEO:** per-route title and description through the framework's native head handling; canonical, Open Graph and JSON-LD carried over; robots and sitemap carried over or generated from the route list. Replace Lovable placeholder `og:image` and author meta only with values the user gives.
- **Performance:** route-level code splitting where the framework supports it, lazy-loaded below-the-fold media, image dimensions set, no unused dependencies, and no client JavaScript added where the original page was static. Compare bundle and asset sizes before and after in the report.

## 6. Record and report

Copy `<skill>/assets/report-template.json` into the migrated project (or a temporary folder), and fill it in as checks run: routes, components, dependency changes, removed files, checks with commands and results, visual parity results, approved differences, external services, limitations and commands. Then:

```bash
python3 <skill>/scripts/generate_report.py migration-report.json --output MIGRATION_REPORT.md
```

The status is computed. It is "complete" only when every required check is `PASS` or `NOT_APPLICABLE` with a reason, every route is migrated or changed with approval, the parity run ran, and every difference is explained and approved. Delete the template copy if the user does not want it in the repository. Keep `MIGRATION_REPORT.md`.

Afterwards, stop the preview servers and remove the temporary folders.

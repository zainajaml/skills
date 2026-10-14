# Project analysis

Contents: [Run the analyzer](#run-the-analyzer) · [Anatomy of a Lovable project](#anatomy-of-a-lovable-project) · [Discovery checklist](#discovery-checklist) · [Scope decisions](#scope-decisions) · [Common risks](#common-risks) · [Assessment template](#assessment-template)

## Run the analyzer

```bash
python3 <skill>/scripts/analyze_project.py <original> --format markdown        # summary to show and reason about
python3 <skill>/scripts/analyze_project.py <original> --output <tmp>/analysis.json  # full detail
```

The analyzer only reads files. It skips `node_modules` and build output, never opens `.env` files (it lists that they exist), and redacts long tokens in evidence lines. Its matches are leads: open each flagged file and confirm what it does. Key fields in the JSON:

| Field | Use |
| --- | --- |
| `classification` | Scope gate input, with backend signals, dependencies, hosts and network calls |
| `routes`, `lazyImports` | Route map: path, component, file and line; `dynamic` and `catchAll` flags |
| `pages`, `components`, `largestFiles` | Where the big monolithic files are |
| `uiComponents.unused` | shadcn/ui primitives no file imports (Lovable ships many): don't migrate them |
| `assets` | Sizes, large files, files no source mentions (check dynamic paths before dropping) |
| `fonts` | Google Fonts, `@font-face`, local files, configured families; flags fonts that are configured but never loaded |
| `head`, `seoFiles` | Title, meta, Open Graph, canonical, JSON-LD, robots and sitemap |
| `theme` | Tailwind dark mode setting, `dark:` usage, CSS variables in `:root` and `.dark`, custom breakpoints and animations |
| `interactions` | Files using state, effects, storage, observers, timers, dialogs, carousels, forms, toasts and theme toggles |
| `externalHosts`, `networkEvidence`, `backendEvidence` | Every URL host and network call |
| `lovable` | Tooling to drop, and Lovable URLs that need a replacement from the user (for example the default `og:image`) |

## Anatomy of a Lovable project

Confirm everything from the files. Typical Lovable output:
- **Vite + React + TypeScript**, with `@/` mapped to `src/`. Newer Lovable apps may use **TanStack Start** (`@tanstack/react-start`, file routes in `src/routes/`, often `@lovable.dev/vite-tanstack-config`). Their server functions mean the app is not frontend-only.
- **React Router** routes in `src/App.tsx`, usually with a catch-all `*` → `NotFound`. That page often has a leftover `console.error` and a plain `<a href="/">` link.
- **Tailwind CSS v3** (`tailwind.config.ts`, `darkMode: ["class"]`, `tailwindcss-animate`) with **shadcn/ui** in `src/components/ui/` (Radix primitives, `cva`, `cn()` in `src/lib/utils.ts`). Design tokens are HSL CSS variables in `src/index.css`.
- `lucide-react` icons, `sonner` and `toaster` toasts, `@tanstack/react-query` (often wired up but unused), `react-hook-form` + `zod`, `embla-carousel-react`, `recharts`, and sometimes `framer-motion`.
- Pages in `src/pages/` as long single components. Hooks such as `use-mobile.tsx` and `use-toast.ts` in `src/hooks/`.
- Lovable leftovers: `lovable-tagger` with `componentTagger()` in `vite.config.ts`, Lovable `og:image` and author meta in `index.html`, `public/placeholder.svg`, a Lovable README, `bun.lockb` next to `package-lock.json`, and `.lovable/`.

## Discovery checklist

Record what you find for each item. Every item feeds the plan or the report.

1. **Structure:** root tree, entry point, aliases, generated files.
2. **Package manager:** lockfiles (two lockfiles mean you choose one with the user), Node version and scripts.
3. **Framework and build:** Vite config, plugins, base path, env usage, build output folder.
4. **Routing:** every route, the 404 page, nested and dynamic routes, redirects, anchor links (`#contact`), scroll behavior, links that use `<a>` instead of the router, external links and `target="_blank"`.
5. **Pages and components:** sections per page, repeated blocks, shared layout, sizes.
6. **Styling:** Tailwind config (colors, fonts, radius, screens, keyframes), global CSS, CSS variables, dark mode mechanism, custom classes, inline styles.
7. **UI libraries:** which primitives each page actually uses (Dialog, Sheet, Accordion, Tabs, Carousel, Tooltip, Toast…), and their behavior (focus trap, Escape to close, keyboard navigation).
8. **Assets:** images, SVGs, video, favicon, manifest, remote images (Unsplash and similar), sizes and formats.
9. **Fonts and icons:** font sources and weights; icon library and the icons used.
10. **State and interactivity:** `useState`/effects, context, storage, timers, observers, animations, theme toggle, forms and validation.
11. **Data:** hard-coded arrays and repeated content that should become static data.
12. **Environment:** env variable names, and what they configure.
13. **External integrations:** every network call and host, embeds, analytics, form services.
14. **Tests and quality tooling:** existing tests, ESLint and Prettier config.
15. **Build and deployment:** `vercel.json`, `netlify.toml`, `_redirects`, Dockerfile, CI. Note the SPA fallback setup.
16. **SEO:** title, description, Open Graph and Twitter tags, canonical, `lang`, robots, sitemap, JSON-LD, per-page titles (`document.title`, Helmet).

## Scope decisions

| Finding | Decision |
| --- | --- |
| `@supabase/*`, `src/integrations/supabase/`, `supabase/` folder | Backend-dependent. Stop and offer lovable-supabase-migration or an agreed frontend-only strategy |
| Login or signup screens, protected routes | Backend-dependent, even when the auth looks mocked; confirm with the user |
| `functions.invoke`, `ai.gateway.lovable.dev`, `LOVABLE_API_KEY` | Backend-dependent (Edge Functions, Lovable AI) |
| TanStack Start server functions (`createServerFn`, `*.server.ts`) | Backend-dependent |
| `fetch` to the app's own `/api/...` | Backend-dependent |
| Form posting to Formspree, EmailJS, Web3Forms, Getform or a Zapier/Make webhook | In scope: keep the same endpoint and behavior, and put endpoint IDs in config |
| Analytics, Google Maps, YouTube/Vimeo, Calendly embeds | In scope: keep them, load them the same way, and list them |
| `@tanstack/react-query` with no queries | Unused: remove it, with the reason recorded |
| Fake data with a "submit" that only shows a toast | In scope: keep the exact behavior, and label it as a client-side demo in the report |

Never build a replacement backend, and never fabricate a working submission for a form that had none.

## Common risks

- **Fonts configured but never loaded.** The original renders fallback fonts, so loading the "correct" font would change the look. Keep the rendered result, and report the difference as a follow-up for the user to decide.
- **Default Lovable `og:image` and author meta:** report them and ask the user for their own image. Never invent one.
- **Remote images** (Unsplash URLs): keep the URLs, or download them only with the user's agreement. Check the license notes.
- **Tailwind v3 → v4** changes defaults (border color, ring width, shadow and blur scales, placeholder color). Keep the original major version unless the user asks to upgrade, and run the parity check after any upgrade.
- **Huge single-file pages** with inline arrays: extract them carefully and compare section by section.
- **Animations on scroll** (IntersectionObserver, framer-motion): keep timing and easing; the parity check scrolls the page to trigger them.
- **Multiple lockfiles** or `bun.lockb`: agree on one package manager.
- **Third-party scripts in `index.html`:** carry them over through the framework's script handling.

## Assessment template

```markdown
## Project assessment: <name>
- What it is: <one sentence>
- Classification: frontend-only | frontend-with-external-calls | backend-dependent (evidence: …)
- Stack: <framework, router, styling, UI library, icons, animation, forms>
- Size: <routes> routes, <pages> pages, <components> components, largest file <file> (<lines> lines)
- Routes: / (Index), /about (About), * (NotFound)
- Sections per page: Home = Hero, Services (3 cards), Testimonials (carousel), FAQ (accordion), Contact form (Formspree), Footer
- Design system: tokens in src/index.css (light + dark), fonts <…>, custom animations <…>
- Interactions: mobile menu, accordion, carousel autoplay, theme toggle, form validation
- External services: <hosts and purpose>
- Lovable leftovers: lovable-tagger, og:image from lovable.dev, placeholder.svg, 31 unused ui primitives
- Risks: <list>
- Baseline: captured from <temporary build or URL> (<n> routes × 3 viewports) | not possible because …
```

# React (Vite) target

Use this when the user picks React. If the original is already React + Vite, this is a restructure, not a rewrite: keep the working libraries and move code into the structure below.

## Scaffold

- `npm create vite@latest <dir> -- --template react-ts` (or `react` for JavaScript). Use the current stable React and Vite unless the original's versions must stay for compatibility. Check peer support of the libraries you keep.
- Keep the `@/` → `src/` alias (in `vite.config` and `tsconfig`).
- Tailwind: use the same major version as the original. For Tailwind v3, copy `tailwind.config` and `postcss.config` and update the `content` globs.
- Lint and format: the template's ESLint flat config plus `eslint-plugin-react-hooks` and `eslint-plugin-jsx-a11y`; Prettier with `prettier-plugin-tailwindcss` when Tailwind is used.
- Tests: Vitest + Testing Library (`jsdom`) for components with logic.

## Structure

```text
src/
├── app/
│   ├── App.tsx            providers + router
│   ├── router.tsx         route table (lazy pages)
│   └── providers/         ThemeProvider etc. (only if needed)
├── features/
│   └── <feature>/
│       ├── components/
│       ├── hooks/          only if the feature has reusable logic
│       ├── data.ts         feature content
│       └── pages/<Feature>Page.tsx
├── components/
│   ├── layout/            SiteHeader, SiteFooter, PageLayout
│   └── ui/                used primitives only (shadcn/ui)
├── data/                  shared content (navigation, social links)
├── config/site.ts         site name, URL, default SEO
├── hooks/  lib/  services/  types/   only when they hold real code
├── styles/globals.css
├── assets/                imported images
└── main.tsx
public/                    favicon, robots.txt, sitemap.xml, files referenced by URL
```

For a one-page site, `features/home/` plus `components/layout/` and `data/` is enough. Skip empty folders.

## Routing

- Use React Router with the original's paths, exactly. Declarative mode (`<BrowserRouter>` + `<Routes>`) or `createBrowserRouter`. Follow the docs for the installed major version (v7 ships as `react-router`).
- Lazy-load pages: `const AboutPage = lazy(() => import('@/features/about/pages/AboutPage'))` with a `<Suspense>` fallback that does not change the layout (null, or a same-height placeholder). Keep the home page eager if it is the main landing page.
- Shared layouts: a layout route with `<Outlet />` for pages that share header and footer.
- Catch-all `*` → `NotFoundPage`. Remove Lovable's leftover `console.error` only if the user agrees (it changes nothing visible). Replace a plain `<a href="/">` with `<Link>` only if the behavior stays the same.
- Hash links (`#contact`): keep them. If the original scrolled smoothly (`scroll-behavior: smooth` or `scrollIntoView`), keep that. Add scroll-to-top on route change only if the original did it.
- Static hosting needs an SPA fallback to `index.html` (`vercel.json` rewrites, Netlify `_redirects`, nginx `try_files`). Carry the original's setup over.

## Head and SEO

- React 19 renders `<title>`, `<meta>` and `<link>` from any component and hoists them to `<head>`. Use a small `<PageMeta title description />` component per page. On React 18, or if the original uses it, keep `react-helmet-async`.
- Keep `index.html`'s global tags (charset, viewport, favicon, default OG tags, third-party scripts) exactly, except Lovable's placeholders, which the user replaces.
- An SPA cannot serve per-route meta to crawlers that do not run JavaScript. If the site's SEO depends on that, tell the user that prerendering or Next.js is the fix. Do not add it unasked.

## State and interactivity

- `useState`/`useReducer` locally; context only for cross-cutting state (theme). Custom hooks for reused behavior (`useScrollSpy`, `useMediaQuery`). Keep Lovable's `use-mobile` breakpoint value if components rely on it.
- No global store unless the app really needs one.
- Memoize only where profiling or obvious re-render cost justifies it.

## Assets and fonts

- Images imported from `src/assets` get hashed URLs. Files referenced by absolute path (`/images/x.png`, favicon, OG image) stay in `public/` with the same paths.
- Fonts: keep the original's loading method (Google Fonts `<link>` in `index.html`, or `@fontsource` packages if used).

## Build and deploy

`npm run build` → `dist/`. `npm run preview` serves it for the parity run. Document the SPA fallback for the target host.

# Next.js (App Router) target

Use this when the user picks Next.js. Use React Router patterns nowhere: routing comes from the `app/` folder.

## Scaffold

- `npx create-next-app@latest <dir>` with TypeScript, ESLint, App Router, `src/` directory and the `@/*` alias. Choose Tailwind to match the original. Check the scaffolded Tailwind major version, and align it with the original's config (v3 config file vs v4 CSS `@theme`) before migrating styles.
- **Rendering:** a static Lovable site becomes fully static. Use `output: 'export'` in `next.config` when the user hosts static files; otherwise use the default static rendering. Do not add server-only features (route handlers, server actions, middleware, `cookies()`) to a static site.
- Lint: `next lint`/ESLint with `jsx-a11y`; Prettier. Tests: Vitest or Jest + Testing Library for client components with logic.

## Structure

```text
src/
├── app/
│   ├── layout.tsx            <html lang>, fonts, global CSS, header and footer, default metadata
│   ├── page.tsx              home: imports HomePage from features
│   ├── about/page.tsx
│   ├── (marketing)/...       route groups only when layouts differ
│   ├── not-found.tsx
│   ├── sitemap.ts  robots.ts when the original had them
│   └── globals.css
├── features/<feature>/       components/, data.ts, <Feature>Page.tsx (no routing here)
├── components/layout/  components/ui/
├── config/site.ts            site name, URL, default SEO
├── data/  lib/  hooks/
public/                       favicon, OG image, files referenced by URL
```

Route files (`page.tsx`, `layout.tsx`) stay thin: metadata plus one feature component.

## Routing mapping

| Original (React Router) | Next.js |
| --- | --- |
| `<Route path="/about">` | `app/about/page.tsx` |
| `/blog/:slug` | `app/blog/[slug]/page.tsx`; with static export, `generateStaticParams` over the static data |
| `*` → NotFound | `app/not-found.tsx` |
| `<Link to>` / `useNavigate` | `next/link` `<Link href>` / `useRouter` from `next/navigation` |
| `useLocation().pathname` | `usePathname()` (client component) |
| `<Navigate to>` redirects | `redirect()` in a page, or `redirects` in `next.config` (not available with `output: 'export'`; use host redirects) |
| Hash links `#contact` | Same `href="#contact"`, or `/#contact` from other pages |

Keep every public URL, including trailing-slash behavior (`trailingSlash` in config if the original host added slashes).

## Server and client components

- Components are server components by default. Sections that only render markup stay server components: no client JavaScript for static content.
- Add `'use client'` only on the smallest interactive leaf (menu toggle, accordion, carousel, form, theme toggle) and pass static content in as props or children.
- `window`, `document` and `localStorage` only in client components, inside effects or event handlers.
- Radix-based shadcn/ui primitives are client components. Import them only into client components, or into server components through their client boundary as shadcn's setup does.

## Metadata and SEO

- Use `export const metadata` per page (title, description, openGraph, alternates.canonical), with a title template in the root layout matching the original titles **exactly**. The parity check compares them.
- Move `index.html` head content to the metadata API. Move third-party scripts to `next/script` with a strategy that keeps their original timing (`afterInteractive` for scripts that were in `<head>`).
- `app/sitemap.ts` and `app/robots.ts` only if the original had a sitemap or robots file, or the user asks.

## Fonts and images

- `next/font/google` (or `next/font/local`) with the same family, weights, styles and `display`. Expose it as the CSS variable the Tailwind config uses.
- `next/image` changes markup and loading. Use it where it keeps the same rendered size and look (set `width`/`height` or `fill` with a sized parent). With `output: 'export'`, set `images.unoptimized: true` or a loader. Plain `<img>` is acceptable where parity requires it; note it in the report.

## Build and deploy

`next build`. With `output: 'export'`, serve `out/` with any static server for the parity run. Otherwise run `next start`. Document the host (Vercel, Netlify, static hosting) and any redirect or trailing-slash settings.

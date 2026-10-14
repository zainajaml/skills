# Component extraction

Contents: [Find the pieces](#find-the-pieces) · [Rules](#rules) · [Props and types](#props-and-types) · [Static data](#static-data) · [Interactions and state](#interactions-and-state) · [Forms](#forms) · [Example](#example)

## Find the pieces

For each page, list its parts from top to bottom before writing code:
1. **Layout parts** used on several pages: header and navigation, footer, page shell, section container. These go to `components/layout` (or the framework's layout mechanism).
2. **Page sections** (usually `<section>` blocks): Hero, Features, Services, Testimonials, Pricing, FAQ, CTA, Contact. Each becomes a component in the page's feature folder.
3. **Repeated blocks** inside sections (cards, list items, pricing tiers, team members, logos): one component, plus a data array.
4. **Shared UI patterns** across features (section heading with eyebrow and subtitle, icon card, badge, CTA button group): `components/ui` or a shared folder, only when used in two or more places.
5. **Behavior** (menu toggle, accordion state, carousel, theme, scroll spy): a hook, composable or service only when it is reused or complex. Otherwise local state.

## Rules

- A page or route component only composes sections and sets page metadata. Aim for about 20–60 lines.
- A component has one responsibility, named after it (`PricingSection`, `PricingCard`). Review files over about 200 lines, and split them by responsibility, not by line count.
- Extract only when it removes duplication, names a meaningful part of the page, or isolates behavior. Do not wrap single elements (`<Title>`, `<Paragraph>`) or create one-off abstractions.
- Prefer composition (children and slots) over boolean prop flags that switch layouts.
- Feature-specific components live in their feature. Shared components must not import from features.
- Keep markup, classes and element order identical while moving code. Change one thing at a time, so parity failures point to the cause.
- Keep semantic HTML and accessibility attributes, and add the missing ones (`aria-label` on icon buttons, `aria-expanded` on toggles, `alt` on images).
- Remove dead code found during extraction (commented blocks, unused imports, unused state) and record it.

## Props and types

- Props describe content and variants, not styling internals: `title`, `description`, `items`, `variant: 'primary' | 'outline'`.
- With TypeScript, export an interface or type per component and per data item (`Service`, `Testimonial`), with no `any`.
- Pass `className` (or `class`) through only on components that are meant to be positioned by their parent.
- Vue: `defineProps` with types, and `emits` for events. Angular: `input()`/`output()` signals (or `@Input`/`@Output` on older versions).

## Static data

Move repeated or list-like content out of markup:

| Data used by | Location |
| --- | --- |
| One feature | `features/<feature>/data.ts` (or the feature's `data/`) |
| Several features (navigation, social links, company info) | `src/data/*.ts` |
| Site metadata (name, URL, default description, OG image) | `src/config/site.ts` |

- Keep every text, URL, image reference and order exactly. Copy; do not retype.
- Icons in data: store the icon component (React and Vue) or icon name (Angular `lucide-angular`).
- Images in data: import them (bundler assets) or use public paths, as the framework handles assets.
- Do not introduce a CMS, a database or fetch calls for static content.
- Long legal or blog text can stay in markup, or move to Markdown/MDX only if the user asks.

## Interactions and state

- Local UI state (menu open, active tab, accordion item) stays in the component. React `useState`, Vue `ref`, Angular `signal`.
- State shared by distant components (theme, cart in a demo, consent): context/provider (React), a composable with module state, or Pinia when it is truly global (Vue), or an injectable service with signals (Angular).
- Do not add Redux, Zustand, Pinia or NgRx for a static site.
- Remove `@tanstack/react-query` when nothing fetches. Keep it only for real remote reads (it is rare in frontend-only apps).
- Keep event behavior exact: when menus close, debounce timings, autoplay intervals, scroll offsets, storage keys.
- Effects that touch `window` or `document` must run on the client only (Next.js client components, `onMounted` in Vue, `afterNextRender` or platform checks in Angular SSR).

## Forms

- Keep fields, order, placeholders, validation rules and messages, and the success and error UI.
- Keep the same submission target (form service endpoint, `mailto:`, or client-only demo). Put endpoint IDs in config.
- If the original posted to a backend that is out of scope, report it. Keep the call unchanged, or agree with the user on a clearly labeled mock. Never fabricate a working service.
- Validation libraries: React Hook Form + zod (React and Next.js, as in Lovable), VeeValidate + zod (Vue), Angular reactive forms with validators (Angular).

## Example

A 900-line `src/pages/Index.tsx` becomes:

```text
features/home/
├── components/
│   ├── HeroSection.tsx         headline, subtext, CTA buttons, hero image
│   ├── ServicesSection.tsx     heading + grid of ServiceCard
│   ├── ServiceCard.tsx
│   ├── TestimonialsSection.tsx carousel of TestimonialCard
│   ├── TestimonialCard.tsx
│   ├── FaqSection.tsx          accordion
│   └── ContactSection.tsx      form; submits through services/contact.ts
├── data.ts                     services, testimonials, faq items
└── pages/HomePage.tsx          composes the sections (about 25 lines)
components/layout/  SiteHeader, SiteFooter, PageLayout
data/navigation.ts  header and footer links
services/contact.ts the same form endpoint as before
```

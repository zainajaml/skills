# Styling migration

Contents: [Compatibility](#compatibility) · [Keep the design identical](#keep-the-design-identical) · [Design tokens](#design-tokens) · [Translating Tailwind](#translating-tailwind-to-another-styling-system) · [UI primitives per framework](#ui-primitives-per-framework) · [Icons, fonts, animation, dark mode](#icons-fonts-animation-and-dark-mode)

## Compatibility

Offer only combinations marked ✓. Check the current docs for each library's support of the chosen framework version before recommending it.

| Styling / UI library | React (Vite) | Next.js | Vue 3 | Angular |
| --- | --- | --- | --- | --- |
| Keep original system (Tailwind + shadcn-style primitives) | ✓ shadcn/ui | ✓ shadcn/ui | ✓ Tailwind + shadcn-vue (Reka UI) | ✓ Tailwind + spartan/ui or Angular CDK |
| Tailwind CSS only | ✓ | ✓ | ✓ | ✓ |
| Standard CSS | ✓ | ✓ | ✓ (scoped `<style>`) | ✓ (component styles) |
| CSS Modules | ✓ | ✓ | ✓ (`<style module>`) | ✗ (use component style encapsulation) |
| SCSS / Sass | ✓ | ✓ | ✓ | ✓ |
| Bootstrap | ✓ (CSS or react-bootstrap) | ✓ | ✓ (CSS or bootstrap-vue-next) | ✓ (CSS or ng-bootstrap) |
| Material UI | ✓ | ✓ (needs its App Router setup) | ✗ (Vuetify is the Material option) | ✗ (Angular Material) |
| Ant Design | ✓ | ✓ | ant-design-vue | ng-zorro-antd |
| Chakra UI | ✓ | ✓ | ✗ | ✗ |
| Vue libraries: PrimeVue, Vuetify, Element Plus, Naive UI | ✗ | ✗ | ✓ | ✗ |
| Angular Material, PrimeNG | ✗ | ✗ | ✗ | ✓ |

**Recommended default:** keep the original styling system. Lovable apps are Tailwind + shadcn/ui, and keeping Tailwind with the same config gives near-identical output in any framework. Switching to a component library with its own look (Bootstrap, MUI, Ant Design, Chakra, Vuetify, Angular Material) means theming it with the extracted tokens. Spacing, typography, focus rings and motion will still differ. Tell the user before they choose, and get their approval for each difference the parity check shows.

## Keep the design identical

- Keep exact values: colors, spacing, sizes, radius, shadows, font families, weights, sizes and line heights, letter spacing, breakpoints, z-index order, transitions and keyframes.
- Keep the same Tailwind major version and config (theme extensions, `darkMode`, plugins, `content` globs adapted to the new file types such as `.vue`, `.html` and `.component.ts`).
- Copy global CSS (base layer, CSS variables, custom utilities) first. Then migrate components, and compare each page as it is done.
- Keep class order and merge behavior. `cn()` (clsx + tailwind-merge) decides which class wins. Use the same helper, or resolve the final classes manually.
- Keep hover, focus-visible, active and disabled states, and `group-*` and `peer-*` behavior.
- Do not "clean up" values that look odd (`py-[18px]`, `tracking-[-0.02em]`); they are part of the design.

## Design tokens

Extract the design into one token source before migrating components:
1. Read `tailwind.config.*` (`theme.extend`: colors, fontFamily, borderRadius, keyframes, animation, screens) and the CSS variables in `src/index.css` (`:root` and `.dark`).
2. Keep them as CSS custom properties: one global stylesheet (`src/styles/globals.css`, or `src/styles.css` in Angular) with the same names and values, light and dark.
3. Map them for the chosen system:
   - **Tailwind:** keep the config mapping (`primary: 'hsl(var(--primary))'`).
   - **CSS, CSS Modules, SCSS:** use `var(--primary)` directly. In SCSS, add a `_tokens.scss` with breakpoint mixins equal to Tailwind's screens (`sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`, unless customized).
   - **Component libraries:** create the library theme from the same tokens (MUI `createTheme`, Ant Design `ConfigProvider` tokens, Chakra theme, Vuetify theme, an Angular Material theme generated from the primary color). Record which tokens the library cannot express.
4. Repeated visual patterns become components (section shell, section heading, card, button variants), not new global classes.

## Translating Tailwind to another styling system

Only when the user chooses to leave Tailwind:
- Use the computed values Tailwind produces (spacing scale `4` = `1rem`, `text-lg` = `1.125rem / 1.75rem`, and so on), not approximations. Keep `rem` units.
- Keep the mobile-first order: base styles first, then `min-width` media queries in the same breakpoint order.
- Recreate Tailwind's preflight (or the browser defaults it changes: margins, list styles, borders, `box-sizing`, image display), or the whole layout shifts.
- Translate `space-x-*` and `gap-*`, `divide-*`, `ring-*` (box-shadow), `line-clamp-*`, `aspect-*`, `container` and arbitrary values with care. These are the usual sources of differences.
- Name classes by component part (`.hero`, `.hero__title` or module classes), not by appearance.

## UI primitives per framework

Lovable's shadcn/ui primitives sit on Radix, which provides focus management, keyboard behavior and ARIA. Keep that behavior:

| Need | React / Next.js | Vue 3 | Angular |
| --- | --- | --- | --- |
| Primitives with the same behavior | Keep the used shadcn/ui files (Radix) | shadcn-vue on Reka UI | spartan/ui (brain + helm) or Angular CDK (overlay, a11y, dialog) |
| Dialog / Sheet | Radix Dialog | Reka Dialog | CDK Dialog or Angular Material dialog |
| Accordion / Tabs / Collapsible | Radix | Reka | CDK Accordion, or a small accessible component |
| Carousel (Embla) | embla-carousel-react | embla-carousel-vue | embla-carousel (core) in a directive, or an accessible custom component |
| Toasts (sonner) | sonner | vue-sonner | ngx-sonner or Angular Material snackbar |
| Charts (recharts) | recharts | a Vue chart library with the same chart types, styled to match | ngx-echarts or Chart.js wrapper, styled to match |

Migrate only the primitives in use (`uiComponents.used`). Do not wrap primitives in extra layers without a reason.

## Icons, fonts, animation and dark mode

- **Icons:** keep the same set and icon names. lucide-react → `lucide-vue-next` (Vue) / `lucide-angular` (Angular). Keep sizes and stroke widths. Never introduce a second icon library.
- **Fonts:** load the same families and weights from the same source. In Next.js use `next/font` with the same family, weights and `display`. Self-host only with the user's agreement. If the original configured fonts but never loaded them, keep what is actually rendered, and report it.
- **Animation:** keep keyframes, durations, easings and delays. framer-motion → `motion` (React) / `motion-v` or `@vueuse/motion` (Vue) / Angular animations or CSS. Keep scroll-triggered reveals with IntersectionObserver equivalents (`@vueuse/core` `useIntersectionObserver`; a directive in Angular). Respect `prefers-reduced-motion` wherever the original animates.
- **Dark mode:** keep the mechanism (class on `<html>`, storage key, system default). next-themes → `next-themes` (Next.js) or a small theme provider or composable or service using the same `localStorage` key and class. Avoid a flash of the wrong theme: set the class before first paint, as the original did.

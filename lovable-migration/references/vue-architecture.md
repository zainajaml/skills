# Vue 3 target

Use this when the user picks Vue. Moving from React means rewriting every component as a single-file component. Translate behavior; do not wrap React code.

## Scaffold

- `npm create vue@latest <dir>`: TypeScript (if chosen), Vue Router (if more than one route), ESLint + Prettier, Vitest; Pinia only when shared state justifies it. Use the current stable Vue 3 and Vite.
- Keep the `@/` → `src/` alias. Tailwind: same major version and config as the original, with `content` including `./index.html` and `./src/**/*.{vue,ts}`.
- Lint: `eslint-plugin-vue` (recommended rules) and `eslint-plugin-vuejs-accessibility`. Type check with `vue-tsc --noEmit`.

## Structure

```text
src/
├── app/
│   ├── App.vue              <RouterView /> inside the layout
│   └── router.ts            routes (lazy pages)
├── features/<feature>/
│   ├── components/          SFCs: HeroSection.vue, ServiceCard.vue
│   ├── composables/         only for reusable feature logic
│   ├── data.ts
│   └── pages/<Feature>Page.vue
├── components/layout/  components/ui/
├── composables/             shared: useTheme, useMediaQuery, useScrollSpy
├── data/  config/site.ts  types/  lib/
├── styles/globals.css
├── assets/
└── main.ts
public/
```

## Translating React to Vue

| React (Lovable) | Vue 3 |
| --- | --- |
| Function component + JSX | `<script setup lang="ts">` SFC + template |
| Props interface | `defineProps<Props>()`, with `withDefaults` for defaults |
| Callback props (`onSelect`) | `defineEmits` events |
| `children` | default slot; named slots for regions |
| `useState` | `ref` / `reactive` |
| `useEffect(fn, [])` / cleanup | `onMounted` / `onBeforeUnmount`; `watch` for dependencies |
| `useMemo` | `computed` |
| Context | `provide` / `inject`, or a composable with module-level state; Pinia for real global state |
| `className` + `cn()` | `:class` arrays/objects; keep tailwind-merge where class conflicts were resolved by `cn()` |
| `{cond && <X/>}` / `.map()` | `v-if` / `v-for` with `:key` |
| `dangerouslySetInnerHTML` | `v-html` (only for trusted static content) |
| lucide-react | lucide-vue-next |
| shadcn/ui (Radix) | shadcn-vue (Reka UI) |
| framer-motion | `<Transition>`/CSS, or `motion-v` / `@vueuse/motion` for complex motion |
| react-hook-form + zod | VeeValidate + zod (`@vee-validate/zod`) |
| next-themes | small `useTheme` composable (same storage key and class) or `@vueuse/core` `useDark` configured to match |

## Routing

- Vue Router with the original paths. Lazy routes: `component: () => import('@/features/about/pages/AboutPage.vue')`.
- Catch-all: `{ path: '/:pathMatch(.*)*', component: NotFoundPage }`.
- `scrollBehavior` reproduces the original: hash anchors (`{ el: to.hash, behavior: 'smooth' }` if it scrolled smoothly), and top on navigation only if the original did that.
- `RouterLink` for internal links, and `<a>` for hashes on the same page if the original used plain anchors.
- SPA fallback on the host, as in the React reference.

## Head and SEO

Per-route title and description with `@unhead/vue` (`useHead`/`useSeoMeta`), or route `meta` plus a `router.afterEach` that sets `document.title` and the description. Keep `index.html` global tags. Nuxt is a different framework: do not switch to it silently. Suggest it only if the user needs server rendering.

## Build and deploy

`npm run build` → `dist/`; `npm run preview` for the parity run.

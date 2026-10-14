# Frontend features and framework branches

## Shared architecture

Map routes/screens to domain features. Route files compose feature screens and route-level loading/metadata; components render; hooks/composables coordinate state; feature API functions express domain operations; one shared HTTP client owns transport. Never make components build table queries, call raw fetch/axios for application APIs, or use ORM/Supabase row types as their contract. Browser-native assets/navigation and third-party SDK requirements are documented exceptions, not an excuse to bypass the API layer.

Use this common shape, adding only directories with real responsibilities:

```text
# inside <frontend-repo>/ (name given by the user, see architecture.md) or the reused existing repo
src/
  features/
    projects/
      components/
      views/
      hooks/          # React/Next only
      composables/    # Vue only
      api/projects.api.ts
      types/
      schemas/
      state/
      constants/
      utils/
      tests/
      index.ts
  shared/
    ui/
    api/client.ts
    api/errors.ts
    config/
    hooks/            # or composables
    lib/
    types/
  assets/
public/
```

Keep shared UI primitives separate from feature components. Shared code must not import feature internals. Split oversized components by behavior and responsibility, preserving keyboard interaction, focus, loading/empty/error states and visual behavior. Preserve useful existing UI libraries and styling; migration does not authorize redesigning the product. Use existing naming consistently and format/lint changed code.

## Next.js

Use the selected Next version's supported routing convention, normally App Router for a new target. Keep routes in `src/app/` with layouts, page files, loading/error/not-found boundaries and route groups as needed. Route files import feature views; do not duplicate routes under features. Keep server/client component boundaries explicit and minimize client-only bundles.

The separate backend owns business rules and persistence. Server components can load data through the backend API. Server actions or route handlers may provide thin session/proxy adapters where needed, but may not become a second business backend. Forward only necessary identity/context, never trust browser identity fields, and never expose service tokens to client bundles. Keep a server-only API adapter separate from the browser transport when origins/auth differ. Avoid module-global per-user state. Define personalized cache/no-store behavior, revalidation and logout invalidation explicitly to prevent cross-user leaks.

Keep assets served by URL in public/; use the framework's supported image/font handling where suitable. Distinguish browser-public build-time variables from server runtime secrets. Static export is valid only if observed features and selected deployment actually support it; do not containerize an SSR app as static HTML by assumption.

## React.js

Choose a documented client runtime, ordinarily Vite with a suitable router unless existing constraints justify another option. React itself does not provide file-based routing. Preserve or select TanStack Router for file-based routes where useful, or React Router with an explicit supported route configuration. State the choice and use its current version conventions; do not invent Next-style automatic routing in a plain React app.

Use `src/app/` for bootstrap/providers/router composition and `src/routes/` for route files when the chosen router supports them. Route components delegate to feature views. Preserve protected routes and authorization-aware navigation without treating client-side guards as security enforcement. Ensure deep links work through hosting rewrites.

If the source is TanStack Start, inventory SSR/server functions (`createServerFn` in `*.functions.ts`, server-only `*.server.ts`), middleware and server endpoints. Lovable's `@lovable.dev/vite-tanstack-config` builds for Cloudflare Workers by default; account for that runtime when moving server code: Workers support only a subset of Node.js APIs, depending on the `nodejs_compat` compatibility flag and compatibility date in the Wrangler configuration, plus Workers-specific bindings (KV, D1, R2, environment bindings). Check which APIs and bindings the existing server code uses and whether the target Node backend has equivalents to the backend and when choosing target hosting. Selecting a browser-only React target requires moving those responsibilities and adapting data loading/hydration. Do not remove the Lovable Vite wrapper, Nitro or route plugin before the replacement build and all dependent features work.

## Vue.js

Use Vue 3 + TypeScript and a compatible runtime, typically Vite plus Vue Router. Keep bootstrap/providers/router in `src/app/`, feature views and SFCs in feature folders, and reusable behavior in composables. Vue Router route configuration is valid; choose supported file-routing tooling only if justified and configured. Do not impose Next.js conventions or silently switch to Nuxt.

Choosing Vue for a React source is a full UI rewrite. Lovable apps commonly use React with shadcn/ui (Radix), Tailwind, lucide-react, TanStack Query and React Hook Form; confirm the actual libraries from `package.json`. State this effort and the visual-parity risk in the plan before the user confirms. Prefer equivalents that preserve design and accessibility (for example shadcn-vue/Reka UI, Tailwind with the same theme tokens, lucide-vue-next, TanStack Query for Vue, VeeValidate with the same schemas) after checking current compatibility, and verify parity screen by screen.

Translate React component/hooks behavior into Vue SFCs/composables rather than wrapping React source. Preserve accessibility, permissions, route params, form semantics, loading states and cache invalidation. Use Pinia for justified global application state and a compatible server-state cache when needed; avoid storing a second copy of every API response.

## Central API client

Own base URL configuration, encoded paths/query, headers, request ID, credential mode, content-type selection, cancellation/timeouts and normalized ApiError in shared/api. Support JSON, no-body responses, multipart, text/blob and streaming intentionally. Do not force a JSON Content-Type on FormData. Separate user-facing messages from diagnostic logs.

Implement the client with interceptors (Axios request/response interceptors, or an equivalent hook chain in a fetch wrapper) so every call goes through the same pipeline:

- **Request interceptors:** base URL, auth header or credentials mode, request ID, JSON vs FormData content type, timeout and abort signal.
- **Response interceptors:** unwrap the backend's success envelope so feature code receives `data` (and `meta` for lists); convert the error envelope into one typed `ApiError` with `status`, `code`, `message`, `details` and `requestId`; trigger the auth refresh flow on 401 as described below; leave blob/stream/no-body responses unwrapped.

Feature `*.api.ts` functions call the client only, never `fetch`/`axios` directly, and never parse envelopes themselves. Keep interceptors few and ordered deliberately, and test them.

Use one deliberate fetch wrapper or existing Axios instance. Deduplicate auth header construction across uploads/queries. Specify auth refresh only if used: single-flight refresh for concurrent 401s, at most one retry, no refresh recursion on login/refresh, revoke/clear state on terminal failure, preserve request bodies safely, and avoid unsafe mutation replay without idempotency guarantees. Handle logout while refresh is pending so a late response cannot restore the session. Retry only appropriate transient/idempotent requests (network errors, 502/503/504, 429 honoring `Retry-After`) with a small maximum (for example 2–3 attempts) and backoff, or leave retries to the server-state library's configured retry; do not blanket-retry payments, uploads or validation failures. Treat cancellation separately from application failure.

Feature `*.api.ts` functions use the client and typed domain DTOs. Hooks/composables own query keys, cache invalidation, optimistic changes and rollback. Include tenant/user identity in cache scope and clear sensitive cached state on logout/tenant switch/role downgrade. Align frontend handling of 401, 403, 404 and expired sessions with the backend contract, including onboarding/no-access redirects.

## Forms, state, assets

Use schema-based frontend validation and reusable accessible form patterns; backend validation remains authoritative. Map API field errors to fields, preserve values on failure, prevent duplicate submissions and handle async validation. Use established libraries when justified by complexity.

Separate local UI state, global application/session state, and remote/server state. Derive state when possible; avoid redundant auth contexts or duplicate route/session gates with different semantics. Centralize a session read model while preserving server enforcement.

Place directly served static assets in the framework's public/static directory; place imported feature/build assets according to the bundler convention. Preserve licensing and references when moving assets. Uploaded user content belongs to the storage system, not public/ or the source repository. Audit hardcoded Lovable/CDN/storage URLs; mirror only authorized application assets and migrate user content with its permissions. Check image/font/base-path and cache behavior after deployment.

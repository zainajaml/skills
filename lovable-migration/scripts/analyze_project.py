#!/usr/bin/env python3
"""Inventory a Lovable (or similar) frontend project before migrating it.

Usage:
  analyze_project.py <project-dir> [--format json|markdown] [--output FILE]

Read-only. Reports the package manager, dependencies by purpose, build and
styling configuration, routes, pages and components (with sizes), unused
shadcn/ui components, assets and their references, fonts, head/SEO tags, theme
and dark mode, interaction patterns, tests and deployment files, Lovable
tooling, environment variable *names*, and every sign of a backend or external
service, ending in a frontend-only classification with evidence.

Never reads .env files and redacts long tokens in evidence lines. Text matches
are leads, not proof: the agent confirms them by reading the code.
Requires Python 3.8+.
"""
import argparse
import json
import os
import re
import sys

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".angular", "coverage",
             ".vercel", ".netlify", ".turbo", ".cache", ".svelte-kit", "out"}
TEXT_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".css", ".scss",
            ".sass", ".less", ".json", ".md", ".mdx", ".toml", ".yml", ".yaml", ".svg", ".txt", ".xml"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".html"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico", ".mp4", ".webm", ".mov",
             ".woff", ".woff2", ".ttf", ".otf", ".eot", ".json", ".lottie", ".pdf", ".mp3"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf", ".eot"}

DEPENDENCY_GROUPS = [
    ("lovable", ["lovable-tagger", "@lovable.dev/"]),
    ("framework", ["react", "react-dom", "next", "vue", "nuxt", "@angular/core", "svelte", "astro",
                   "@tanstack/react-start", "solid-js"]),
    ("router", ["react-router-dom", "react-router", "@tanstack/react-router", "vue-router", "wouter",
                "@angular/router"]),
    ("build", ["vite", "@vitejs/", "webpack", "parcel", "@angular/cli", "@angular-devkit/", "typescript"]),
    ("styling", ["tailwindcss", "@tailwindcss/", "tailwindcss-animate", "tw-animate-css", "postcss", "autoprefixer",
                 "sass", "styled-components", "@emotion/", "bootstrap", "class-variance-authority",
                 "tailwind-merge", "clsx"]),
    ("ui", ["@radix-ui/", "@mui/", "antd", "@chakra-ui/", "@headlessui/", "cmdk", "vaul", "sonner",
            "embla-carousel", "react-day-picker", "input-otp", "react-resizable-panels", "recharts",
            "@angular/material", "@angular/cdk", "vuetify", "primevue", "element-plus", "reka-ui", "radix-vue",
            "swiper", "react-slick", "keen-slider"]),
    ("icons", ["lucide-react", "lucide-vue-next", "lucide-angular", "react-icons", "@heroicons/",
               "@fortawesome/", "@iconify/", "@tabler/icons"]),
    ("forms", ["react-hook-form", "@hookform/", "zod", "yup", "formik", "vee-validate", "@vee-validate/"]),
    ("state", ["@tanstack/react-query", "@tanstack/vue-query", "zustand", "redux", "@reduxjs/", "jotai",
               "recoil", "pinia", "mobx", "valtio"]),
    ("animation", ["framer-motion", "motion", "gsap", "aos", "lottie-react", "lottie-web", "@react-spring/",
                   "react-intersection-observer", "@formkit/auto-animate"]),
    ("theme", ["next-themes"]),
    ("seo", ["react-helmet", "react-helmet-async", "@unhead/", "@vueuse/head"]),
    ("i18n", ["i18next", "react-i18next", "vue-i18n", "@angular/localize", "next-intl"]),
    ("dates", ["date-fns", "dayjs", "moment", "luxon"]),
    ("testing", ["vitest", "jest", "@testing-library/", "@playwright/test", "cypress", "@vue/test-utils",
                 "karma", "jasmine"]),
    ("lint", ["eslint", "@eslint/", "typescript-eslint", "prettier", "eslint-plugin-", "@typescript-eslint/"]),
    ("backend-or-data", ["@supabase/", "firebase", "@firebase/", "aws-amplify", "appwrite", "@clerk/", "@auth0/",
                         "next-auth", "@apollo/client", "graphql-request", "urql", "socket.io-client", "pusher-js",
                         "axios", "ky", "@stripe/", "pocketbase", "convex", "@prisma/client", "drizzle-orm"]),
    ("client-services", ["@emailjs/", "emailjs-com", "@formspree/", "react-ga4", "react-gtm-module",
                         "@vercel/analytics", "@vercel/speed-insights", "posthog-js", "@sentry/", "mixpanel-browser",
                         "@calcom/", "react-calendly", "react-google-recaptcha", "@hcaptcha/", "@react-google-maps/",
                         "leaflet", "react-leaflet", "mapbox-gl", "@googlemaps/"]),
]

BACKEND_PATTERNS = [
    ("supabase-client", r"\bcreateClient\s*\(|@supabase/supabase-js|\bsupabase\s*\.\s*(from|auth|storage|rpc|functions|channel)\b"),
    ("supabase-edge-function", r"functions\.invoke\s*\("),
    ("auth-flow", r"\.auth\.(signIn|signUp|signOut|getSession|getUser|onAuthStateChange)|\bsignInWith\w+\("),
    ("lovable-ai-gateway", r"ai\.gateway\.lovable\.dev|LOVABLE_API_KEY"),
    ("firebase", r"initializeApp\s*\(|getFirestore\s*\(|getAuth\s*\("),
    ("websocket", r"new\s+WebSocket\s*\(|new\s+EventSource\s*\(|io\s*\(\s*['\"`]https?:"),
    ("graphql", r"\bgql`|ApolloClient\s*\("),
]
NETWORK_PATTERNS = [
    ("fetch-call", r"\bfetch\s*\("),
    ("axios-call", r"\baxios(\.\w+)?\s*\("),
    ("form-action", r"<form[^>]*\baction\s*=\s*['\"{]"),
    ("beacon", r"navigator\.sendBeacon\s*\("),
]
INTERACTION_PATTERNS = {
    "useState": r"\buseState\s*[<(]",
    "useEffect": r"\buseEffect\s*\(",
    "useReducer/useContext": r"\buse(Reducer|Context)\s*\(",
    "localStorage/sessionStorage": r"\b(localStorage|sessionStorage)\.",
    "IntersectionObserver/inView": r"IntersectionObserver|useInView|whileInView",
    "timers": r"\bset(Interval|Timeout)\s*\(",
    "scroll-listeners": r"addEventListener\(\s*['\"]scroll|scrollIntoView|window\.scrollTo",
    "matchMedia/useIsMobile": r"matchMedia\s*\(|useIsMobile|useMediaQuery",
    "framer-motion": r"<motion\.|from ['\"](framer-motion|motion/react)['\"]",
    "forms": r"<form\b|useForm\s*\(|onSubmit\s*=",
    "toasts": r"\btoast\s*[.(]|<Toaster|<Sonner",
    "dialogs/sheets": r"<(Dialog|Sheet|Drawer|AlertDialog|Popover|DropdownMenu|NavigationMenu)\b",
    "accordion/tabs/carousel": r"<(Accordion|Tabs|Carousel|Collapsible)\b",
    "theme-toggle": r"useTheme\s*\(|ThemeProvider|classList\.(toggle|add)\(\s*['\"]dark",
    "document-head": r"document\.title\s*=|<Helmet|useHead\s*\(|<title>",
    "query-hooks": r"\buse(Query|Mutation|InfiniteQuery)\s*\(",
}
SERVICE_HOSTS = [
    ("supabase", r"supabase\.(co|in)$", "backend"),
    ("lovable", r"(^|\.)lovable\.(dev|app)$", "lovable"),
    ("formspree", r"formspree\.io$", "client-service"),
    ("emailjs", r"emailjs\.com$", "client-service"),
    ("web3forms", r"web3forms\.com$", "client-service"),
    ("getform", r"getform\.io$", "client-service"),
    ("zapier/make webhook", r"(hooks\.zapier\.com|hook\.\w+\.make\.com)$", "client-service"),
    ("google-analytics/tag-manager", r"(google-analytics|googletagmanager)\.com$", "client-service"),
    ("google-maps", r"(maps\.google|maps\.googleapis)\.com$", "client-service"),
    ("google-fonts", r"fonts\.(googleapis|gstatic)\.com$", "asset"),
    ("youtube/vimeo embed", r"(youtube\.com|youtu\.be|vimeo\.com)$", "asset"),
    ("calendly", r"calendly\.com$", "client-service"),
    ("unsplash/pexels images", r"(images\.unsplash\.com|unsplash\.com|pexels\.com)$", "asset"),
]
TOKEN = re.compile(r"[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}|[A-Za-z0-9_\-]{32,}")
URL = re.compile(r"https?://([A-Za-z0-9.-]+)(?::\d+)?[^\s\"'`)<>]*")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not (d.startswith(".") and d != ".lovable"))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


def is_env_file(rel):
    base = os.path.basename(rel)
    return base == ".env" or (base.startswith(".env.") and not base.endswith((".example", ".sample", ".template")))


def read(full, limit=1_500_000):
    try:
        if os.path.getsize(full) > limit:
            return None
        with open(full, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def redact(line):
    return TOKEN.sub("<redacted>", line.strip())[:160]


def group_dependencies(deps):
    grouped = {}
    for name, version in sorted(deps.items()):
        group = "other"
        for candidate, patterns in DEPENDENCY_GROUPS:
            if any(name == p or (p.endswith(("/", "-")) and name.startswith(p)) for p in patterns):
                group = candidate
                break
        grouped.setdefault(group, {})[name] = version
    return grouped


def find_routes(files, is_next):
    routes = []
    for rel, text in files.items():
        if not rel.endswith((".tsx", ".jsx", ".ts", ".js")):
            continue
        for match in re.finditer(r"<Route\b([^>]*?)/?>", text):
            attrs = match.group(1)
            path = re.search(r"\bpath\s*=\s*[\"'{`]+([^\"'}`]+)", attrs)
            element = re.search(r"\belement\s*=\s*\{\s*<\s*([A-Z][\w.]*)", attrs)
            index = re.search(r"\bindex\b", attrs)
            if path or index:
                routes.append({"path": path.group(1) if path else "(index)", "component": element.group(1) if element else None,
                               "file": rel, "line": text.count("\n", 0, match.start()) + 1, "kind": "react-router"})
        for match in re.finditer(r"\bpath\s*:\s*[\"'`]([^\"'`]+)[\"'`]\s*,?\s*(?:element\s*:\s*<\s*([A-Z][\w.]*)|component\s*:\s*([A-Z]\w*)|loadComponent)?", text):
            routes.append({"path": match.group(1), "component": match.group(2) or match.group(3), "file": rel,
                           "line": text.count("\n", 0, match.start()) + 1, "kind": "route-object"})
        for match in re.finditer(r"createFileRoute\(\s*[\"'`]([^\"'`]+)", text):
            routes.append({"path": match.group(1), "component": None, "file": rel,
                           "line": text.count("\n", 0, match.start()) + 1, "kind": "tanstack-file-route"})
    for rel in files if is_next else []:
        m = re.match(r"^(?:src/)?app/(.*?)(?:/)?page\.(tsx|jsx|ts|js)$", rel)
        if m:
            segment = "/" + re.sub(r"\([^)]*\)/?", "", m.group(1)).rstrip("/")
            routes.append({"path": segment if segment != "/" else "/", "component": None, "file": rel, "line": 1,
                           "kind": "next-app-router"})
        m = re.match(r"^(?:src/)?pages/(.*)\.(tsx|jsx|ts|js)$", rel)
        if m and not os.path.basename(rel).startswith("_") and not m.group(1).startswith("api/"):
            path = "/" + re.sub(r"(^|/)index$", "", m.group(1))
            routes.append({"path": path, "component": None, "file": rel, "line": 1, "kind": "next-pages-router"})
    for route in routes:
        route["dynamic"] = bool(re.search(r"[:$\[]|\*", route["path"]))
        route["catchAll"] = route["path"] in ("*", "/*", "$") or route["path"].endswith("*")
    unique, seen = [], set()
    for route in routes:
        key = (route["path"], route["file"], route["line"])
        if key not in seen:
            seen.add(key)
            unique.append(route)
    return unique


def lazy_imports(files):
    mapping = {}
    for rel, text in files.items():
        for match in re.finditer(r"const\s+(\w+)\s*=\s*(?:React\.)?lazy\(\s*\(\)\s*=>\s*import\(\s*[\"']([^\"']+)", text):
            mapping[match.group(1)] = {"module": match.group(2), "file": rel}
    return mapping


def head_tags(html):
    if not html:
        return {}
    meta = []
    for match in re.finditer(r"<meta\b([^>]*)>", html, re.I):
        attrs = dict((k.lower(), v) for k, _, v in re.findall(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", match.group(1)))
        key = attrs.get("name") or attrs.get("property") or attrs.get("http-equiv") or ("charset" if "charset" in attrs else None)
        if key:
            meta.append({"key": key, "content": (attrs.get("content") or attrs.get("charset") or "")[:200]})
    links = [{"rel": rel, "href": href} for rel, href in
             re.findall(r"<link\b[^>]*rel=[\"']([^\"']+)[\"'][^>]*href=[\"']([^\"']+)[\"']", html, re.I)]
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    lang = re.search(r"<html[^>]*\blang=[\"']([^\"']+)", html, re.I)
    return {"title": title.group(1).strip() if title else None, "lang": lang.group(1) if lang else None,
            "meta": meta, "links": links, "jsonLd": len(re.findall(r"application/ld\+json", html, re.I)),
            "inlineScripts": len(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html, re.I)),
            "externalScripts": re.findall(r"<script[^>]*\bsrc=[\"']([^\"']+)", html, re.I)}


def analyze(root):
    root = os.path.abspath(root)
    files, sizes, env_files, all_paths = {}, {}, [], []
    for rel, full in walk(root):
        all_paths.append(rel)
        try:
            sizes[rel] = os.path.getsize(full)
        except OSError:
            continue
        if is_env_file(rel):
            env_files.append(rel)
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext in TEXT_EXT and os.path.basename(rel) not in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock"):
            text = read(full)
            if text is not None:
                files[rel] = text

    package = {}
    if "package.json" in files:
        try:
            package = json.loads(files["package.json"])
        except ValueError:
            package = {}
    deps = dict(package.get("dependencies") or {})
    dev_deps = dict(package.get("devDependencies") or {})
    all_deps = dict(deps, **dev_deps)
    lockfiles = [f for f in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock") if f in all_paths]
    manager = {"package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lockb": "bun",
               "bun.lock": "bun"}
    config_names = ("vite.config", "next.config", "nuxt.config", "angular.json", "tsconfig", "tailwind.config",
                    "postcss.config", "components.json", "eslint.config", ".eslintrc", ".prettierrc", "prettier.config",
                    "vitest.config", "jest.config", "playwright.config", "cypress.config", "vercel.json",
                    "netlify.toml", "_redirects", "Dockerfile", "nginx.conf", "wrangler", "index.html")
    configs = [p for p in all_paths if "/" not in p.lstrip("./") and os.path.basename(p).startswith(config_names)]
    configs += [p for p in all_paths if p.startswith(("public/_redirects", ".github/workflows/"))]

    code = {r: t for r, t in files.items() if os.path.splitext(r)[1] in CODE_EXT}
    styles = {r: t for r, t in files.items() if os.path.splitext(r)[1] in STYLE_EXT}
    line_counts = {r: t.count("\n") + 1 for r, t in code.items()}
    source_code = {r: n for r, n in line_counts.items() if r.startswith(("src/", "app/", "pages/", "components/"))}

    ui_dir = next((d for d in ("src/components/ui/", "components/ui/") if any(p.startswith(d) for p in all_paths)), None)
    ui_components = []
    if ui_dir:
        for rel in sorted(p for p in code if p.startswith(ui_dir)):
            name = os.path.splitext(os.path.basename(rel))[0]
            pattern = re.compile(r"[\"'](@/components/ui/|\./|\.\./ui/|\.\./components/ui/|~/components/ui/)" + re.escape(name) + r"[\"']")
            users = [r for r, t in code.items() if r != rel and pattern.search(t)]
            ui_components.append({"name": name, "file": rel, "lines": line_counts[rel], "usedBy": len(users)})

    pages_dirs = [d for d in ("src/pages/", "pages/", "src/views/", "src/routes/", "src/app/", "app/") if any(p.startswith(d) for p in code)]
    pages = [{"file": r, "lines": n} for r, n in sorted(source_code.items()) if r.startswith(tuple(pages_dirs))]
    components = [{"file": r, "lines": n} for r, n in sorted(source_code.items())
                  if "/components/" in "/" + r and not (ui_dir and r.startswith(ui_dir))]
    largest = sorted(({"file": r, "lines": n} for r, n in source_code.items()), key=lambda x: -x["lines"])[:15]

    text_blob_files = {r: t for r, t in files.items() if not r.startswith("public/") or r.endswith((".html", ".css", ".json", ".xml", ".webmanifest"))}
    assets = []
    for rel in all_paths:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in ASSET_EXT or not rel.startswith(("public/", "src/assets/", "assets/", "static/")):
            continue
        if rel.endswith(".json") and not rel.startswith(("public/", "src/assets/")):
            continue
        base = os.path.basename(rel)
        referenced = any(base in t for r, t in text_blob_files.items() if r != rel)
        assets.append({"file": rel, "bytes": sizes.get(rel, 0), "referenced": referenced,
                       "large": sizes.get(rel, 0) > 500_000})

    index_html = files.get("index.html") or files.get("public/index.html") or files.get("src/index.html")
    fonts = {
        "googleFonts": sorted({m for t in list(files.values()) for m in re.findall(r"fonts\.googleapis\.com/css2?\?family=([^\"'&)\s]+)", t)}),
        "fontFaceRules": [r for r, t in styles.items() if "@font-face" in t],
        "localFontFiles": [p for p in all_paths if os.path.splitext(p)[1].lower() in FONT_EXT],
        "fontFamilyConfig": [redact(line) for r, t in files.items() if r.startswith("tailwind.config")
                             for line in t.splitlines() if re.search(r"fontFamily|sans:|serif:|mono:|display:", line)][:10],
    }

    tailwind_text = next((t for r, t in files.items() if r.startswith("tailwind.config")), "")
    css_vars_root = sum(len(re.findall(r"--[\w-]+\s*:", block)) for t in styles.values() for block in re.findall(r":root\s*{([^}]*)}", t))
    css_vars_dark = sum(len(re.findall(r"--[\w-]+\s*:", block)) for t in styles.values() for block in re.findall(r"\.dark\s*{([^}]*)}", t))
    theme = {
        "tailwindDarkMode": (re.search(r"darkMode\s*:\s*([^,\n]+)", tailwind_text).group(1).strip()
                             if re.search(r"darkMode\s*:", tailwind_text) else None),
        "tailwindV4CssConfig": any("@import \"tailwindcss\"" in t or "@theme" in t for t in styles.values()),
        "darkVariantUsages": sum(t.count("dark:") for t in code.values()),
        "cssVariablesRoot": css_vars_root,
        "cssVariablesDark": css_vars_dark,
        "nextThemes": "next-themes" in all_deps,
        "styleFiles": sorted(styles),
        "breakpointsCustomized": bool(re.search(r"screens\s*:", tailwind_text)),
        "customAnimations": sorted(set(re.findall(r"[\"']?([\w-]+)[\"']?\s*:\s*{\s*(?:from|['\"]?0%)", tailwind_text)))[:30],
    }

    interactions = {}
    for name, pattern in INTERACTION_PATTERNS.items():
        hits = [r for r, t in code.items() if r.startswith(("src/", "app/", "pages/", "components/")) and re.search(pattern, t)
                and not (ui_dir and r.startswith(ui_dir))]
        if hits:
            interactions[name] = {"files": len(hits), "examples": hits[:8]}

    evidence, hosts = [], {}
    for rel, text in files.items():
        if rel.startswith(("node_modules", "public/")) and not rel.endswith(".html"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in BACKEND_PATTERNS:
                if re.search(pattern, line):
                    evidence.append({"kind": kind, "severity": "backend", "file": rel, "line": number, "text": redact(line)})
            if os.path.splitext(rel)[1] in CODE_EXT:
                for kind, pattern in NETWORK_PATTERNS:
                    if re.search(pattern, line):
                        evidence.append({"kind": kind, "severity": "network", "file": rel, "line": number, "text": redact(line)})
            for match in URL.finditer(line):
                host = match.group(1).lower()
                if host in ("localhost", "127.0.0.1", "www.w3.org", "schema.org", "json.schemastore.org") or rel.endswith(".md"):
                    continue
                entry = hosts.setdefault(host, {"count": 0, "files": []})
                entry["count"] += 1
                if rel not in entry["files"] and len(entry["files"]) < 5:
                    entry["files"].append(rel)
    host_report = []
    for host, info in sorted(hosts.items()):
        label, category = None, "unknown"
        for name, pattern, cat in SERVICE_HOSTS:
            if re.search(pattern, host):
                label, category = name, cat
                break
        host_report.append({"host": host, "service": label, "category": category, **info})

    env_names = sorted({g for t in code.values() for m in re.finditer(r"import\.meta\.env\.(\w+)|process\.env\.(\w+)", t)
                        for g in m.groups() if g and g not in ("MODE", "DEV", "PROD", "SSR", "BASE_URL", "NODE_ENV")})
    lovable = {
        "dependencies": sorted(d for d in all_deps if d == "lovable-tagger" or d.startswith("@lovable.dev/")),
        "componentTagger": any("componentTagger" in t for r, t in files.items() if r.startswith("vite.config")),
        "lovableFolder": any(p.startswith(".lovable/") for p in all_paths),
        "readmeMentionsLovable": "lovable.dev" in (files.get("README.md") or ""),
        "placeholderSvg": "public/placeholder.svg" in all_paths,
        "lovableMetaInIndexHtml": bool(index_html and re.search(r"lovable", index_html, re.I)),
        "supabaseFolder": any(p.startswith("supabase/") for p in all_paths),
        "supabaseIntegration": any(p.startswith("src/integrations/supabase/") for p in all_paths),
    }

    backend_kinds = sorted({e["kind"] for e in evidence if e["severity"] == "backend"})
    backend_deps = sorted(d for d in all_deps if any(d == p or (p.endswith(("/", "-")) and d.startswith(p))
                                                     for p in dict(DEPENDENCY_GROUPS)["backend-or-data"]))
    backend_hosts = [h["host"] for h in host_report if h["category"] == "backend"]
    lovable["hostReferences"] = [{"host": h["host"], "files": h["files"]} for h in host_report if h["category"] == "lovable"]
    service_hosts = [h["host"] for h in host_report if h["category"] == "client-service"]
    unknown_network = [e for e in evidence if e["severity"] == "network"]
    if backend_kinds or lovable["supabaseFolder"] or lovable["supabaseIntegration"] or \
            any(d.startswith(("@supabase/", "firebase", "@firebase/", "@clerk/", "@auth0/", "next-auth", "appwrite", "pocketbase", "convex"))
                for d in backend_deps):
        classification = "backend-dependent"
    elif unknown_network or service_hosts or backend_deps:
        classification = "frontend-with-external-calls"
    else:
        classification = "frontend-only"

    framework = next((name for name, key in (("next", "next"), ("tanstack-start", "@tanstack/react-start"), ("nuxt", "nuxt"),
                                             ("angular", "@angular/core"), ("vue", "vue"), ("react", "react"),
                                             ("svelte", "svelte")) if key in all_deps), "unknown")
    routes = find_routes(code, framework == "next")
    return {
        "project": root,
        "name": package.get("name"),
        "framework": framework,
        "language": "typescript" if any(r.endswith((".ts", ".tsx")) for r in code) else "javascript",
        "packageManager": [manager[l] for l in lockfiles] or None,
        "lockfiles": lockfiles,
        "scripts": package.get("scripts") or {},
        "engines": package.get("engines"),
        "dependencies": group_dependencies(deps),
        "devDependencies": group_dependencies(dev_deps),
        "configFiles": sorted(set(configs)),
        "routes": routes,
        "lazyImports": lazy_imports(code),
        "pages": pages,
        "components": components,
        "largestFiles": largest,
        "uiComponents": {"directory": ui_dir, "total": len(ui_components),
                         "unused": [c["name"] for c in ui_components if c["usedBy"] == 0],
                         "used": [c["name"] for c in ui_components if c["usedBy"] > 0]},
        "assets": {"count": len(assets), "totalBytes": sum(a["bytes"] for a in assets),
                   "large": [a for a in assets if a["large"]],
                   "possiblyUnreferenced": [a["file"] for a in assets if not a["referenced"]],
                   "files": assets},
        "fonts": fonts,
        "head": head_tags(index_html),
        "seoFiles": [p for p in all_paths if p in ("public/robots.txt", "public/sitemap.xml", "public/manifest.json",
                                                   "public/site.webmanifest", "public/favicon.ico")],
        "theme": theme,
        "interactions": interactions,
        "envVarNames": env_names,
        "envFilesPresent": env_files,
        "tests": sorted(p for p in code if re.search(r"\.(test|spec)\.|(^|/)(e2e|__tests__|tests?)/", p)),
        "lovable": lovable,
        "externalHosts": host_report,
        "backendEvidence": [e for e in evidence if e["severity"] == "backend"][:60],
        "networkEvidence": unknown_network[:60],
        "classification": {
            "result": classification,
            "backendSignals": backend_kinds,
            "backendDependencies": backend_deps,
            "backendHosts": backend_hosts,
            "clientServiceHosts": service_hosts,
            "networkCalls": len(unknown_network),
            "note": "text matches are leads; confirm each by reading the code before deciding scope",
        },
        "size": {"codeFiles": len(source_code), "codeLines": sum(source_code.values()), "routes": len(routes),
                 "pages": len(pages), "components": len(components), "uiComponents": len(ui_components)},
    }


def fonts_summary(fonts):
    parts = []
    if fonts["googleFonts"]:
        parts.append("Google Fonts: " + ", ".join(fonts["googleFonts"]))
    if fonts["localFontFiles"]:
        parts.append("%d local font files" % len(fonts["localFontFiles"]))
    if fonts["fontFaceRules"]:
        parts.append("@font-face in " + ", ".join(fonts["fontFaceRules"]))
    configured = sorted({name for line in fonts["fontFamilyConfig"] for name in re.findall(r"[\"']([A-Z][\w ]+)[\"']", line)})
    if configured:
        parts.append("configured: " + ", ".join(configured))
        if not (fonts["googleFonts"] or fonts["localFontFiles"] or fonts["fontFaceRules"]):
            parts.append("**no font loading found, so browsers fall back**")
    return "; ".join(parts) or "system fonts"


def markdown(report):
    c = report["classification"]
    lines = ["# Project analysis: %s" % (report["name"] or os.path.basename(report["project"])), ""]
    lines += ["| Item | Finding |", "| --- | --- |"]
    rows = [
        ("Classification", "**%s**" % c["result"]),
        ("Framework / language", "%s / %s" % (report["framework"], report["language"])),
        ("Package manager", ", ".join(report["packageManager"] or ["unknown"]) +
         (" (multiple lockfiles)" if len(report["lockfiles"]) > 1 else "")),
        ("Size", "%(codeFiles)d code files, %(codeLines)d lines, %(routes)d routes, %(pages)d page files, "
                 "%(components)d components, %(uiComponents)d ui primitives" % report["size"]),
        ("Router", ", ".join(report["dependencies"].get("router", {})) or "none"),
        ("Styling", ", ".join(list(report["dependencies"].get("styling", {})) + list(report["devDependencies"].get("styling", {}))) or "none"),
        ("UI libraries", ", ".join(report["dependencies"].get("ui", {})) or "none"),
        ("Icons", ", ".join(report["dependencies"].get("icons", {})) or "none"),
        ("State / data", ", ".join(report["dependencies"].get("state", {})) or "none"),
        ("Dark mode", "darkMode=%s, %d `dark:` usages, %d dark CSS variables" % (
            report["theme"]["tailwindDarkMode"], report["theme"]["darkVariantUsages"], report["theme"]["cssVariablesDark"])),
        ("Fonts", fonts_summary(report["fonts"])),
        ("Assets", "%d files, %.1f MB, %d large, %d possibly unreferenced" % (
            report["assets"]["count"], report["assets"]["totalBytes"] / 1e6, len(report["assets"]["large"]),
            len(report["assets"]["possiblyUnreferenced"]))),
        ("Unused ui primitives", "%d of %d" % (len(report["uiComponents"]["unused"]), report["uiComponents"]["total"])),
        ("Head", "title: %s; %d meta tags; JSON-LD blocks: %d" % (report["head"].get("title"), len(report["head"].get("meta", [])),
                                                                   report["head"].get("jsonLd", 0))),
        ("Env variable names", (", ".join(report["envVarNames"]) or "none") +
         ("; env files present (not read): " + ", ".join(report["envFilesPresent"]) if report["envFilesPresent"] else "")),
        ("Tests", "%d files" % len(report["tests"])),
        ("Lovable tooling", ", ".join(k for k, v in report["lovable"].items() if v and k != "hostReferences") or "none"),
        ("Lovable URLs in the app", ", ".join("%s (%s)" % (h["host"], ", ".join(h["files"]))
                                             for h in report["lovable"]["hostReferences"]) or "none"),
    ]
    lines += ["| %s | %s |" % row for row in rows]
    lines += ["", "## Routes", "", "| Path | Component | Defined in |", "| --- | --- | --- |"]
    lines += ["| `%s` | %s | %s:%d |" % (r["path"], r["component"] or "-", r["file"], r["line"]) for r in report["routes"]] or ["| none found | | |"]
    lines += ["", "## Largest files", ""] + ["- %s (%d lines)" % (f["file"], f["lines"]) for f in report["largestFiles"][:10]]
    if c["result"] != "frontend-only":
        lines += ["", "## Backend and network evidence", ""]
        lines += ["- Backend signals: %s" % (", ".join(c["backendSignals"]) or "none"),
                  "- Backend dependencies: %s" % (", ".join(c["backendDependencies"]) or "none"),
                  "- Backend hosts: %s" % (", ".join(c["backendHosts"]) or "none"),
                  "- Client service hosts: %s" % (", ".join(c["clientServiceHosts"]) or "none")]
        lines += ["- `%s:%d` %s: `%s`" % (e["file"], e["line"], e["kind"], e["text"])
                  for e in (report["backendEvidence"] + report["networkEvidence"])[:25]]
    lines += ["", "_%s_" % c["note"], ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output")
    args = parser.parse_args()
    if not os.path.isdir(args.project):
        sys.stderr.write("error: %s is not a directory\n" % args.project)
        return 1
    report = analyze(args.project)
    text = markdown(report) if args.format == "markdown" else json.dumps(report, indent=2) + "\n"
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(text)
        print(json.dumps({"written": args.output, "classification": report["classification"]["result"]}))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

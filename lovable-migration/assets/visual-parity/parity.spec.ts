// For every route and viewport: HTTP status, page title, meta description, language and
// heading outline, runtime errors, and a full-page screenshot compared with the baseline
// captured from the original site. Errors that the original also had are not counted.
import { test, expect, type Page } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

type RouteSpec = {
  path: string;          // concrete URL path, e.g. "/", "/about", "/blog/first-post"
  name?: string;         // file-safe name; defaults to the path
  mask?: string[];       // selectors to mask (embedded maps, videos, live clocks)
  hide?: string[];       // selectors hidden before capture (cookie banners, chat widgets)
  waitFor?: string;      // selector that must be visible before capture
  fullPage?: boolean;    // default true
  actions?: { click?: string; hover?: string; fill?: [string, string]; press?: string }[]; // state to reach first
  projects?: string[];   // limit to some viewports, e.g. ["mobile"] for a mobile menu
};

const routesFile = resolve(process.env.ROUTES_FILE ?? 'routes.json');
const routes: RouteSpec[] = JSON.parse(readFileSync(routesFile, 'utf8'));
const settleMs = Number(process.env.SETTLE_MS ?? 600);

const slug = (route: RouteSpec) =>
  (route.name ?? (route.path.replace(/^\/|\/$/g, '').replace(/[^\w-]+/g, '_') || 'home')).slice(0, 80);

async function revealLazyContent(page: Page) {
  // Scroll through the page so lazy images and on-scroll reveal animations run, then return to top.
  await page.evaluate(async () => {
    const step = Math.max(200, Math.floor(window.innerHeight / 2));
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 80));
    }
    window.scrollTo(0, 0);
  });
  await page.evaluate(() => document.fonts.ready);
}

for (const route of routes) {
  test(slug(route), async ({ page }, testInfo) => {
    test.skip(!!route.projects && !route.projects.includes(testInfo.project.name), 'route limited to other viewports');
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
    page.on('requestfailed', (r) => errors.push(`requestfailed: ${new URL(r.url()).pathname} ${r.failure()?.errorText ?? ''}`));

    const response = await page.goto(route.path, { waitUntil: 'networkidle' });
    expect(response?.status() ?? 0, `HTTP status of ${route.path}`).toBeLessThan(400);
    if (route.waitFor) await page.locator(route.waitFor).first().waitFor();
    for (const action of route.actions ?? []) {
      if (action.click) await page.locator(action.click).first().click();
      if (action.hover) await page.locator(action.hover).first().hover();
      if (action.fill) await page.locator(action.fill[0]).first().fill(action.fill[1]);
      if (action.press) await page.keyboard.press(action.press);
    }
    await revealLazyContent(page);
    for (const selector of route.hide ?? []) {
      await page.locator(selector).evaluateAll((els) => els.forEach((el) => ((el as HTMLElement).style.visibility = 'hidden')));
    }
    await page.waitForTimeout(settleMs);

    const facts = await page.evaluate(() => ({
      title: document.title,
      description: document.querySelector('meta[name="description"]')?.getAttribute('content') ?? null,
      lang: document.documentElement.lang || null,
      headings: Array.from(document.querySelectorAll('h1,h2,h3')).map((h) => `${h.tagName}:${(h.textContent ?? '').trim().slice(0, 60)}`),
    }));

    const factsFile = resolve('baseline', testInfo.project.name, `${slug(route)}.facts.json`);
    const updating = testInfo.config.updateSnapshots === 'all' || !existsSync(factsFile);
    if (updating) {
      mkdirSync(dirname(factsFile), { recursive: true });
      writeFileSync(factsFile, JSON.stringify({ ...facts, errors }, null, 2));
    } else {
      const baseline = JSON.parse(readFileSync(factsFile, 'utf8'));
      expect.soft(facts.title, 'page title').toBe(baseline.title);
      expect.soft(facts.description, 'meta description').toBe(baseline.description);
      expect.soft(facts.lang, 'html lang').toBe(baseline.lang);
      expect.soft(facts.headings, 'h1-h3 outline').toEqual(baseline.headings);
      const newErrors = errors.filter((e) => !(baseline.errors as string[]).includes(e));
      expect.soft(newErrors, 'runtime errors not present in the original').toEqual([]);
    }

    await expect(page).toHaveScreenshot(`${slug(route)}.png`, {
      fullPage: route.fullPage ?? true,
      mask: (route.mask ?? []).map((selector) => page.locator(selector)),
    });
  });
}

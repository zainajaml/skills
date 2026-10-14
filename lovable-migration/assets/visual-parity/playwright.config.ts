// Visual and behavioral parity check between the original and the migrated site.
// Copy this folder to a temporary directory outside both projects; see references/validation.md.
//
//   BASE_URL=http://localhost:4173 npx playwright test --update-snapshots=all   # baseline from the ORIGINAL
//   BASE_URL=http://localhost:4174 npx playwright test                         # compare the MIGRATED site
//
// Optional: ROUTES_FILE (default routes.json), MAX_DIFF_RATIO (default 0.01),
// COLOR_SCHEME=light|dark, SETTLE_MS (default 600).
import { defineConfig } from '@playwright/test';

const baseURL = process.env.BASE_URL;
if (!baseURL) throw new Error('Set BASE_URL to the site under test');

export default defineConfig({
  testDir: '.',
  testMatch: 'parity.spec.ts',
  snapshotPathTemplate: '{testDir}/baseline/{projectName}/{arg}{ext}',
  outputDir: 'results',
  fullyParallel: true,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'report' }]],
  use: {
    baseURL,
    browserName: 'chromium',
    colorScheme: process.env.COLOR_SCHEME === 'dark' ? 'dark' : 'light',
    deviceScaleFactor: 1,
  },
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: Number(process.env.MAX_DIFF_RATIO ?? 0.01),
      animations: 'disabled',
      caret: 'hide',
    },
  },
  projects: [
    { name: 'mobile', use: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true } },
    { name: 'tablet', use: { viewport: { width: 768, height: 1024 }, hasTouch: true } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
  ],
});

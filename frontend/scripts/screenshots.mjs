/**
 * Capture the screenshots the README uses.
 *
 * Run against a live pair of servers, so what lands in docs/img is the real
 * interface reading the real API — never a mock-up. If the pipeline has not
 * produced an artefact, the shot will show the "not measured yet" panel,
 * which is the honest picture of that state.
 *
 *   uv run uvicorn churn.api:app          # :8000
 *   npm run dev                           # :3000
 *   node scripts/screenshots.mjs
 */
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const BASE = process.env.UI_URL ?? "http://localhost:3000";
const OUT = "../docs/img";

const SHOTS = [
  { name: "ui-dashboard", path: "/dashboard", wait: 2500 },
  { name: "ui-worklist", path: "/worklist", wait: 1500 },
  { name: "ui-customer", path: "/customers/1908", wait: 2500 },
  { name: "ui-evaluations", path: "/evaluations", wait: 3500, fullPage: true },
  { name: "ui-investigation", path: "/investigations/1908", wait: 1500 },
];

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2, // retina: the type stays crisp in the README
  colorScheme: "light",
});

await mkdir(OUT, { recursive: true });

// The dev-server overlay is not part of the product. Hidden for the capture
// rather than switched off in next.config, so nothing about how the app runs
// changes to make a screenshot look better.
await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });

for (const shot of SHOTS) {
  await page.goto(`${BASE}${shot.path}`, { waitUntil: "networkidle" });
  // Charts animate in and metrics stagger; wait for the page to settle rather
  // than catching it mid-entrance.
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.waitForTimeout(shot.wait);
  await page.screenshot({
    path: `${OUT}/${shot.name}.png`,
    fullPage: shot.fullPage ?? false,
  });
  console.log(`saved ${shot.name}.png  (${shot.path})`);
}

await browser.close();

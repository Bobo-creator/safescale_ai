// Times /api/analyze (10 runs) and /api/explain (5 runs) from a real browser on the deployed site.
// Run from web/: node ../evaluation/app_latency/measure.mjs https://safescale-ai.vercel.app
import { writeFileSync } from "node:fs";
import { createRequire } from "node:module";

// Resolve Playwright from web/ (the working directory), where it is installed.
const { chromium } = createRequire(`${process.cwd()}/package.json`)("@playwright/test");

const base = process.argv[2] ?? "https://safescale-ai.vercel.app";
const queries = [
  "Rechargeable children's night light using a 2000 mAh lithium-ion battery, USB-C charging, ABS plastic housing, and LED lighting.",
  "Wooden baby crib with adjustable mattress height and a drop-down side rail.",
  "Six-drawer wooden dresser for a child's bedroom, 48 inches tall.",
  "Folding electric bicycle with a 48 V lithium battery pack and hydraulic disc brakes.",
  "Electric space heater, 1500 W ceramic element, tip-over switch, for bedrooms.",
  "Children's hooded sweatshirt with a drawstring, cotton, sizes 2T to 5T.",
  "Magnetic building tiles toy set for ages 3 and up, with small neodymium magnets.",
  "Portable butane camping stove with a piezo igniter.",
  "Self-balancing hoverboard scooter with a lithium-ion battery and LED lights.",
  "Glass French press coffee maker, 1 liter, with a stainless steel plunger.",
];

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(base);
const time = (path, query) =>
  page.evaluate(
    async ({ path, query }) => {
      const t = performance.now();
      const r = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, k: 25, method: "vector" }),
      });
      await r.json();
      return { status: r.status, ms: Math.round(performance.now() - t) };
    },
    { path, query },
  );

const analyze = [];
for (const q of queries) analyze.push(await time("/api/analyze", q));
const explain = [];
for (const q of queries.slice(0, 5)) explain.push(await time("/api/explain", q));
await browser.close();

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};
const result = {
  base,
  measured_at: new Date().toISOString(),
  analyze: { runs: analyze, median_ms: median(analyze.map((r) => r.ms)) },
  explain: { runs: explain, median_ms: median(explain.map((r) => r.ms)) },
};
writeFileSync(new URL("./results.json", import.meta.url), JSON.stringify(result, null, 1) + "\n");
console.log(JSON.stringify({ analyze: analyze.map((r) => `${r.status}:${r.ms}`), explain: explain.map((r) => `${r.status}:${r.ms}`), median_analyze_ms: result.analyze.median_ms, median_explain_ms: result.explain.median_ms }, null, 1));

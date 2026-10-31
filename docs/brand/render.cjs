// Renders the brand pages in docs/brand/ to PNGs, offline, with the installed Google Chrome.
// Usage: NODE_PATH=<node_modules> node docs/brand/render.cjs [--scale 2] [--out DIR] [name ...]
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..", "..");
const JOBS = {
  banner: { page: "banner.html", out: "docs/img/banner.png", w: 1280, h: 400 },
  "devto-cover": { page: "devto-cover.html", out: "docs/img/devto-cover.png", w: 1000, h: 420 },
  "social-preview": { page: "social-preview.html", out: "docs/img/social-preview.png", w: 1280, h: 640 },
  sweep: { page: "sweep.html", out: "docs/img/sweep.png", w: 1200, h: 0 },
  "how-it-works": { page: "how-it-works.html", out: "docs/img/diagrams/how-it-works.png", w: 1600, h: 0 },
  causes: { page: "causes.html", out: "docs/img/diagrams/causes.png", w: 1600, h: 0 },
  "certificate-checks": { page: "certificate-checks.html", out: "docs/img/diagrams/certificate-checks.png", w: 1600, h: 0 },
};

function args() {
  const a = process.argv.slice(2);
  const opt = { scale: 1, out: null, names: [] };
  for (let i = 0; i < a.length; i++) {
    if (a[i] === "--scale") opt.scale = Number(a[++i]);
    else if (a[i] === "--out") opt.out = a[++i];
    else opt.names.push(a[i]);
  }
  if (!opt.names.length) opt.names = Object.keys(JOBS);
  return opt;
}

(async () => {
  const opt = args();
  const browser = await chromium.launch({ channel: "chrome" });
  for (const name of opt.names) {
    const job = JOBS[name];
    if (!job) throw new Error("unknown page: " + name);
    const ctx = await browser.newContext({
      viewport: { width: job.w, height: job.h || 200 },
      deviceScaleFactor: opt.scale,
    });
    const page = await ctx.newPage();
    await page.route("**/*", (r) => (r.request().url().startsWith("file:") ? r.continue() : r.abort()));
    await page.goto("file://" + path.join(__dirname, job.page));
    await page.evaluate(() => document.fonts.ready);
    const out = opt.out ? path.join(opt.out, path.basename(job.out)) : path.join(ROOT, job.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await page.screenshot({ path: out, fullPage: !job.h, clip: job.h ? { x: 0, y: 0, width: job.w, height: job.h } : undefined });
    console.log(out);
    await ctx.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });

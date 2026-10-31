// Screenshots of the running morgue (http://127.0.0.1:8666) with the installed Google Chrome.
// Only requests to the morgue itself are allowed. Usage: NODE_PATH=<node_modules> node docs/brand/shoot.cjs
const path = require("path");
const { chromium } = require("playwright");

const BASE = "http://127.0.0.1:8666";
const ROOT = path.resolve(__dirname, "..", "..");
const SHOTS = [
  { url: "/", out: "morgue.png" },
  { url: "/w/order-1042", out: "certificate-retry-loop.png" },
  { url: "/w/order-1047", out: "certificate-changed-code.png" },
  { url: "/w/order-1048", out: "certificate-waiting-signal.png" },
  { url: "/w/order-1050", out: "certificate-undead-child.png" },
];

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.route("**/*", (r) => (r.request().url().startsWith(BASE + "/") ? r.continue() : r.abort()));
  for (const s of SHOTS) {
    await page.goto(BASE + s.url);
    const sub = await page.$eval(".cert .sub", (e) => e.textContent).catch(() => "");
    if (sub && !sub.includes("written by gemma4")) throw new Error(s.url + " is not a model certificate yet: " + sub.trim());
    const out = path.join(ROOT, "docs", "img", s.out);
    await page.screenshot({ path: out, fullPage: true });
    console.log(out);
  }
  await browser.close();
})().catch((e) => { console.error(e.message); process.exit(1); });

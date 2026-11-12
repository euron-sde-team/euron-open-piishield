/**
 * Curated README screenshots and tour frames from a freshly seeded stack.
 *
 *   make up && make demo
 *   cd scripts/qa && QA_BASE=http://localhost:5510 node screenshots.mjs
 *   ./make-tour.sh        (stitches the frames into docs/assets/tour.gif)
 *
 * Writes docs/assets/screenshots/NN-name.png and scripts/qa/output/tour/NN.png.
 *
 * PIIShield has no session cookie: the dashboard keeps its bearer token in localStorage
 * (zustand persist, key "piishield.auth"), so this reuses qa.mjs's own sign-in approach
 * (sign in once through the API, seed that same localStorage key plus
 * "piishield.project" before every page visit) rather than a cookie.
 */
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.QA_BASE ?? "http://localhost:5510";
const DEMO_EMAIL = process.env.QA_EMAIL ?? "priya.nair@verdantpay.example";
const PASSWORD = process.env.PIISHIELD_DEMO_PASSWORD ?? process.env.QA_PASSWORD ?? "Demo-Owner-Pass-1";
const CHROME = process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH) ? process.env.CHROME_PATH : undefined;
const SHOTS = path.resolve(HERE, "../../docs/assets/screenshots");
const TOUR = path.resolve(HERE, "output/tour");
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const PHONE = { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 };

const SAMPLE_TEXT =
  "Customer Priya Nair can be reached at priya.nair@verdantpay.example or 98765 43210. " +
  "Her PAN is ABCPD1234E and the refund card on file is 4111 1111 1111 1111.";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let tourIndex = 0;

async function settle(page, ms = 900) {
  await page.waitForNetworkIdle({ idleTime: 400, timeout: 20_000 }).catch(() => {});
  await sleep(ms);
}

async function shot(page, name, { tour = true, fullPage = true } = {}) {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage });
  if (tour) await page.screenshot({ path: path.join(TOUR, `${String(++tourIndex).padStart(2, "0")}.png`) });
  console.log(`saved ${name}`);
}

async function signIn(email) {
  for (let i = 0; i < 6; i++) {
    const resp = await fetch(`${BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password: PASSWORD }),
    });
    if (resp.status === 429) {
      await sleep(Number(resp.headers.get("retry-after") ?? "10") * 1000);
      continue;
    }
    if (!resp.ok) throw new Error(`sign-in for ${email} failed (${resp.status}): run make demo first`);
    return resp.json();
  }
  throw new Error(`sign-in for ${email} kept hitting the rate limit`);
}

async function api(token, url) {
  const resp = await fetch(`${BASE}${url}`, { headers: { authorization: `Bearer ${token}` } });
  if (!resp.ok) throw new Error(`GET ${url}: ${resp.status} ${await resp.text()}`);
  return resp.json();
}

async function seedAuth(page, session, projectId) {
  await page.evaluateOnNewDocument(
    (session, projectId) => {
      localStorage.setItem("theme", "light");
      localStorage.setItem("piishield.auth", JSON.stringify({ state: { token: session.token, user: session.user }, version: 1 }));
      if (projectId) {
        localStorage.setItem("piishield.project", JSON.stringify({ state: { selectedProjectId: projectId }, version: 1 }));
      }
    },
    session,
    projectId,
  );
}

async function goto(page, urlPath) {
  await page.goto(`${BASE}${urlPath}`, { waitUntil: "networkidle0", timeout: 30_000 });
  await settle(page);
}

async function clickButtonByText(page, text) {
  const buttons = await page.$$("button");
  for (const b of buttons) {
    const t = ((await b.evaluate((el) => el.textContent)) ?? "").trim();
    if (t === text || t.includes(text)) {
      await b.click();
      return true;
    }
  }
  return false;
}

async function main() {
  await mkdir(SHOTS, { recursive: true });
  await mkdir(TOUR, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });

  const session = await signIn(DEMO_EMAIL);
  const projects = await api(session.token, "/api/v1/projects");
  if (!projects.length) throw new Error("the demo has no projects: run make demo");
  const projectId = projects[0].id;

  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport(DESKTOP);
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await seedAuth(page, session, projectId);

  // 1. Overview: real seeded totals and the findings-by-category breakdown.
  await goto(page, "/");
  await shot(page, "01-overview");

  // 2. Scan Center: run a real scan so the findings table is populated, not an empty form.
  await goto(page, "/scan");
  const textarea = await page.$("textarea");
  if (textarea) {
    await textarea.click();
    await textarea.type(SAMPLE_TEXT, { delay: 4 });
    await sleep(200);
    const clicked = (await clickButtonByText(page, "Protect")) || (await clickButtonByText(page, "Scan only"));
    if (clicked) await settle(page, 1200);
  }
  await shot(page, "02-scan-center");

  // 3. Review Queue: low-confidence findings pending a decision.
  await goto(page, "/review");
  await shot(page, "03-review-queue");

  // 4. Documents.
  await goto(page, "/documents");
  await shot(page, "04-documents");

  // 5. Database Scan.
  await goto(page, "/database-scan");
  await shot(page, "05-database-scan");

  // 6. AI Gateway.
  await goto(page, "/ai-gateway");
  await shot(page, "06-ai-gateway");

  // 7. Token Vault.
  await goto(page, "/vault");
  await shot(page, "07-token-vault");

  // 8. Policies.
  await goto(page, "/policies");
  await shot(page, "08-policies");

  // 9. Audit Log: real seeded history.
  await goto(page, "/audit");
  await shot(page, "09-audit-log");

  await page.close();

  // 10. Dark mode: Overview again, for the one mandatory dark capture. A fresh page so
  // next-themes reads "theme=dark" from localStorage before it ever mounts (setting it
  // after navigation is too late: next-themes only applies the class on load).
  const darkPage = await ctx.newPage();
  await darkPage.setViewport(DESKTOP);
  await darkPage.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
  await darkPage.evaluateOnNewDocument(
    (session, projectId) => {
      localStorage.setItem("theme", "dark");
      localStorage.setItem("piishield.auth", JSON.stringify({ state: { token: session.token, user: session.user }, version: 1 }));
      if (projectId) {
        localStorage.setItem("piishield.project", JSON.stringify({ state: { selectedProjectId: projectId }, version: 1 }));
      }
    },
    session,
    projectId,
  );
  await goto(darkPage, "/");
  await shot(darkPage, "10-overview-dark");
  await darkPage.close();

  // 11. Phone width: Overview, light mode.
  const phonePage = await ctx.newPage();
  await phonePage.setViewport(PHONE);
  await phonePage.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await seedAuth(phonePage, session, projectId);
  await phonePage.evaluateOnNewDocument(() => {
    try {
      localStorage.setItem("theme", "light");
    } catch {}
  });
  await goto(phonePage, "/");
  await shot(phonePage, "11-overview-phone", { fullPage: false });
  await phonePage.close();

  await browser.close();
  console.log(`\nwrote ${tourIndex} tour frames to ${TOUR}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});

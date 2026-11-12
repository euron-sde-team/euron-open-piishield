/**
 * Browser QA (make qa): visits every dashboard page as the signed-in demo owner, plus
 * the public login/signup pages, in light and dark at desktop (1440) and phone (390)
 * width. Saves a screenshot of each and fails on console errors, failed or 4xx/5xx
 * requests, broken images, error states, and horizontal overflow.
 *
 *   make qa
 *   QA_BASE=http://localhost:5510 QA_OUT=./output node qa.mjs
 *   QA_PAGES=/scan,/vault QA_THEMES=dark QA_SIZES=phone node qa.mjs
 *
 * Needs the seeded stack (make up && make demo). PIIShield has no session cookie: the
 * dashboard keeps its bearer token in localStorage (zustand persist, key
 * "piishield.auth"), so this script signs in once through the API and seeds that same
 * localStorage key (plus "piishield.project" for the selected project) before every
 * page visit, rather than injecting a cookie. Uses Puppeteer's bundled Chromium;
 * CHROME_PATH overrides it.
 */
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer";

const BASE = process.env.QA_BASE ?? "http://localhost:5510";
const OUT = process.env.QA_OUT ?? path.resolve("output");
const PASSWORD = process.env.PIISHIELD_DEMO_PASSWORD ?? process.env.QA_PASSWORD ?? "Demo-Owner-Pass-1";
const CHROME = process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH) ? process.env.CHROME_PATH : undefined;
const DEMO_EMAIL = process.env.QA_EMAIL ?? "priya.nair@verdantpay.example";

const LIST_PAGES = ["/", "/scan", "/review", "/documents", "/database-scan", "/ai-gateway", "/vault", "/policies", "/audit", "/keys", "/settings"];

const ANONYMOUS_PAGES = ["/login", "/signup"];

const ONLY = process.env.QA_PAGES ? new Set(process.env.QA_PAGES.split(",")) : null;
const THEMES = (process.env.QA_THEMES ?? "light,dark").split(",");
const SIZES = {
  desktop: { width: 1440, height: 900 },
  phone: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
const SIZE_KEYS = (process.env.QA_SIZES ?? "desktop,phone").split(",");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function slug(p) {
  return p.replace(/^\//, "").replace(/[/:?=&]/g, "-") || "home";
}

/** Sign in through the API once; returns the raw API response body (token + user). */
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

/** Seed the two localStorage keys the dashboard reads, matching zustand persist's wire
 * format exactly ({ state, version }), then reload so the app picks them up. */
async function signInBrowser(page, session, projectId) {
  await page.evaluateOnNewDocument(
    (session, projectId) => {
      localStorage.setItem("piishield.auth", JSON.stringify({ state: { token: session.token, user: session.user }, version: 1 }));
      if (projectId) {
        localStorage.setItem("piishield.project", JSON.stringify({ state: { selectedProjectId: projectId }, version: 1 }));
      }
    },
    session,
    projectId,
  );
}

async function visit(browser, { urlPath, theme, sizeKey, session, projectId }) {
  const page = await browser.newPage();
  const problems = [];
  const consoleErrors = [];
  const failedRequests = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  page.on("requestfailed", (req) => failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText ?? "failed"})`));
  page.on("response", (res) => {
    const status = res.status();
    if (status >= 400) failedRequests.push(`${res.request().method()} ${res.url()} -> ${status}`);
  });

  await page.setViewport(SIZES[sizeKey]);
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: theme }]);

  if (session) await signInBrowser(page, session, projectId);

  const resp = await page.goto(`${BASE}${urlPath}`, { waitUntil: "networkidle0", timeout: 30_000 });
  await sleep(300);

  if (!resp || resp.status() >= 400) problems.push(`page responded ${resp ? resp.status() : "no response"}`);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  if (overflow) problems.push("horizontal overflow");

  const brokenImages = await page.evaluate(() =>
    Array.from(document.images)
      .filter((img) => img.src && !img.complete)
      .map((img) => img.src),
  );
  if (brokenImages.length) problems.push(`broken images: ${brokenImages.join(", ")}`);

  const bodyText = await page.evaluate(() => document.body.innerText.trim());
  if (!bodyText) problems.push("empty page body");

  const file = `${slug(urlPath)}--${theme}--${sizeKey}.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: sizeKey === "desktop" });

  if (consoleErrors.length) problems.push(`console errors: ${consoleErrors.join(" | ")}`);
  if (failedRequests.length) problems.push(`failed/4xx/5xx requests: ${failedRequests.join(" | ")}`);

  await page.close();
  return { urlPath, theme, sizeKey, file, problems };
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await puppeteer.launch({ headless: true, executablePath: CHROME, args: ["--no-sandbox", "--disable-dev-shm-usage"] });

  const session = await signIn(DEMO_EMAIL);
  const projects = await api(session.token, "/api/v1/projects");
  if (!projects.length) throw new Error("the demo has no projects: run make demo");
  const projectId = projects[0].id;

  const jobs = [];
  for (const theme of THEMES) {
    for (const sizeKey of SIZE_KEYS) {
      for (const urlPath of ANONYMOUS_PAGES) {
        if (ONLY && !ONLY.has(urlPath)) continue;
        jobs.push({ urlPath, theme, sizeKey, session: null, projectId: null });
      }
      for (const urlPath of LIST_PAGES) {
        if (ONLY && !ONLY.has(urlPath)) continue;
        jobs.push({ urlPath, theme, sizeKey, session, projectId });
      }
    }
  }

  const results = [];
  for (const job of jobs) {
    console.log(`-> ${job.urlPath} (${job.theme}, ${job.sizeKey})`);
    const result = await visit(browser, job);
    results.push(result);
    if (result.problems.length) console.log(`   PROBLEMS: ${result.problems.join(" / ")}`);
  }

  await browser.close();

  const failed = results.filter((r) => r.problems.length);
  console.log(`\n${results.length} page views, ${failed.length} with problems. Screenshots in ${OUT}`);
  if (failed.length) {
    for (const f of failed) console.log(`  ${f.urlPath} (${f.theme}, ${f.sizeKey}): ${f.problems.join("; ")}`);
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});

import { expect, type Page } from "@playwright/test";

export const OWNER = {
  email: process.env.E2E_EMAIL || "priya.nair@verdantpay.example",
  password: process.env.E2E_PASSWORD || process.env.PIISHIELD_DEMO_PASSWORD || "Demo-Owner-Pass-1",
};

/** A per-run suffix so suites can run repeatedly without colliding on created names. */
export const RUN = process.env.E2E_RUN || Date.now().toString(36).slice(-5);

/** Open a dashboard page with the shared owner session from global setup. */
export async function asOwner(page: Page, path = "/"): Promise<void> {
  await page.goto(path);
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
}

/** Sign in through the real form (for the auth journey itself, not the shared session). */
export async function signIn(page: Page, email = OWNER.email, password = OWNER.password): Promise<void> {
  await page.goto("/login");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
}

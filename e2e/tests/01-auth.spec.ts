import { expect, test } from "@playwright/test";

import { OWNER, signIn } from "../helpers";

// This suite signs in through the real form, so it gets its own storage state (not the
// shared owner session from global setup), to prove the login journey itself works.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("sign in", () => {
  test("a correct email and password reaches the dashboard", async ({ page }) => {
    await signIn(page);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  });

  test("a wrong password shows an inline error, not a crash", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(OWNER.email);
    await page.locator("#password").fill("definitely-wrong");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/incorrect|invalid|wrong/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("an expired session redirects to login with an explanation, not a silent bounce", async ({ page }) => {
    await page.goto("/login?reason=expired");
    await expect(page.getByText(/session expired/i)).toBeVisible();
  });

  test("signing out clears the session and returns to login", async ({ page }) => {
    await signIn(page);
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});

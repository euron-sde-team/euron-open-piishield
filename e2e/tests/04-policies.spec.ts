import { expect, test } from "@playwright/test";

import { asOwner } from "../helpers";

/**
 * AC10: a required category with no masking method is refused, both client side (a
 * warning banner, Save disabled in spirit by the toast) and, if that were ever
 * bypassed, server side (the API's own required_category_unmasked error). This proves
 * the client-side guard; the server-side refusal is covered by the API's own
 * integration tests (test_policy_guards or equivalent).
 */
test.describe("policies", () => {
  test.beforeEach(async ({ page }) => {
    await asOwner(page, "/policies");
  });

  test("marking a category required with no method warns and blocks save", async ({ page }) => {
    await page.getByRole("checkbox", { name: "Personal" }).click();

    await expect(page.getByText(/will refuse this policy/i)).toBeVisible();
    await page.getByRole("button", { name: "Save policy" }).click();
    await expect(page.getByText(/set a masking method for/i)).toBeVisible();
  });

  test("choosing a method for every required category allows a real save", async ({ page }) => {
    // The demo project's policy already requires financial and government_id with a
    // method each (see euron-open-source-program memory / PLAN.md's demo seed), so
    // saving with no changes must succeed outright.
    await page.getByRole("button", { name: "Save policy" }).click();
    await expect(page.getByText(/policy saved/i)).toBeVisible();
  });

  test("custom recognizers tab lists and can create a per-project pattern", async ({ page }) => {
    await page.getByRole("tab", { name: "Custom recognizers" }).click();
    const name = `e2e-loyalty-${Date.now().toString(36).slice(-5)}`;
    await page.locator("#rec-name").fill(name);
    await page.locator("#rec-category").fill("personal");
    await page.locator("#rec-pattern").fill("LOY-\\d{6}");
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  });
});

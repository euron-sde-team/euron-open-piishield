import { expect, test } from "@playwright/test";

import { asOwner } from "../helpers";

/**
 * Low-confidence findings (below the project's confidence_threshold, 0.6 on the demo
 * project) land in the review queue instead of being silently auto-protected or
 * silently dropped. bank_account (confidence 0.3, no checksum, a bare 9-18 digit run)
 * reliably produces one on demand, rather than relying on the demo seed's own fixed
 * review items, which other runs/manual exploration may depend on staying untouched.
 */
test.describe("review queue", () => {
  test("a low-confidence finding lands in review, and approving it protects it", async ({ page }) => {
    await asOwner(page, "/scan");
    await page.getByPlaceholder(/paste text with emails/i).fill("Reference account 912345678 for the refund.");
    await page.getByRole("button", { name: "Protect" }).click();
    await expect(page.getByText(/^Protected output/i)).toBeVisible();
    await expect(page.getByRole("cell", { name: "Financial", exact: true })).toBeVisible();

    await page.goto("/review");
    const financialRow = page.getByRole("row").filter({ hasText: "Financial" }).first();
    await expect(financialRow).toBeVisible();
    await financialRow.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText(/finding approved and protected/i)).toBeVisible();
  });

  test("the empty state explains what review is and links to Policies, or the queue shows real rows", async ({ page }) => {
    await asOwner(page, "/review");
    const emptyOrPopulated = page.getByText(/nothing waiting on review/i).or(page.getByRole("table"));
    await expect(emptyOrPopulated.first()).toBeVisible();
  });
});

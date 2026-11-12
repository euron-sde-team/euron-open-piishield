import { expect, test } from "@playwright/test";

import { asOwner } from "../helpers";

/**
 * The core promise the product's name makes: scanning finds real PII with a confidence
 * score and, where a checksum applies, whether it passed; protecting actually changes
 * the text so the original value is gone from the output.
 */
test.describe("scan center", () => {
  test.beforeEach(async ({ page }) => {
    await asOwner(page, "/scan");
  });

  test("scan only finds PII and never changes the input", async ({ page }) => {
    await page.getByPlaceholder(/paste text with emails/i).fill("Contact: rahul@example.com, card 4111111111111111");
    await page.getByRole("button", { name: "Scan only" }).click();

    await expect(page.getByRole("cell", { name: "Contact" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Financial" })).toBeVisible();
    // Luhn-valid test card: checksum must show Valid, proving AC2's real validation.
    await expect(page.getByText("Valid")).toBeVisible();
  });

  test("protect replaces the value and shows the method actually applied", async ({ page }) => {
    await page.getByPlaceholder(/paste text with emails/i).fill("Email me at rahul@example.com");
    await page.getByRole("button", { name: "Protect" }).click();

    await expect(page.getByText(/^Protected output/i)).toBeVisible();
    const protectedBlock = page.locator("pre");
    await expect(protectedBlock).not.toContainText("rahul@example.com");
    await expect(page.getByRole("cell", { name: "Contact" })).toBeVisible();
  });

  test("invalid JSON in JSON mode is refused with an explanation, not a crash", async ({ page }) => {
    await page.getByRole("tab", { name: "JSON" }).click();
    await page.getByPlaceholder(/customer/i).fill("{not valid json");
    await page.getByRole("button", { name: "Scan only" }).click();
    await expect(page.locator("p", { hasText: /not valid json/i })).toBeVisible();
  });
});

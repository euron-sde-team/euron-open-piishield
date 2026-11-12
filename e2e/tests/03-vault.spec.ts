import { expect, test } from "@playwright/test";

import { asOwner, RUN } from "../helpers";

/**
 * AC5/AC6: detokenize is a separate permission from being an owner or holding a write
 * key, and the real value never appears anywhere except an authorized detokenize
 * response. The owner signed in for this suite has vault access (see helpers/global
 * setup, the demo owner), so this proves the happy path works end to end; the
 * permission-denial path is proven by the SDKs' own live integration tests
 * (sdks/python/tests/integration/test_live_api.py, sdks/node/test/integration), which
 * run against an API key with no vault grant.
 *
 * The AI gateway's protect always tokenizes every category regardless of the project's
 * own masking policy (ai_gateway/service.py hardcodes method_overrides to tokenize), so
 * it is the simplest, deterministic way to get a guaranteed placeholder here, rather
 * than the scan screen's protect, which uses the project's configured default method.
 */
test.describe("token vault", () => {
  test("the AI gateway's protect/restore round trip, and a direct vault detokenize, both return the original value", async ({ page }) => {
    const email = `rahul.${RUN}@example.com`;

    await asOwner(page, "/ai-gateway");
    await page.getByPlaceholder(/summarize this customer/i).fill(`Contact me at ${email}`);
    await page.getByRole("button", { name: "Protect prompt" }).click();
    await expect(page.getByText(/^Protected prompt$/i)).toBeVisible();

    const protectedPre = page.locator("pre").first();
    await expect(protectedPre).not.toContainText(email);
    const placeholder = (await protectedPre.textContent())?.match(/\[[A-Z_]+_\d+\]/)?.[0];
    expect(placeholder, "the gateway should have returned a tokenize placeholder").toBeTruthy();

    // Step 2 of the gateway's own flow: paste the (simulated) model's response back and
    // restore it, for this application only, never the model.
    await page.getByRole("button", { name: /restore for my app/i }).click();
    await expect(page.getByText(/placeholder\(s\) restored/i)).toBeVisible();
    const restoredPre = page.locator("pre").nth(1);
    await expect(restoredPre).toContainText(email);

    // Separately, the SAME placeholder is also reachable through the dedicated vault
    // screen with the gateway's own full scope_id, read back from the audit log (the
    // gateway UI only ever shows a truncated prefix of it).
    const scopePrefix = (await page.getByText(/^scope /).textContent())?.replace(/^scope /, "").replace(/\.\.\.$/, "");
    const fullScopeId = await page.evaluate(async (prefix) => {
      const raw = localStorage.getItem("piishield.auth");
      const token = raw ? (JSON.parse(raw).state?.token as string | undefined) : undefined;
      const resp = await fetch(`/api/v1/audit?limit=10&action=ai_gateway.protect`, { headers: { authorization: `Bearer ${token}` } });
      const body = (await resp.json()) as { items: { details?: { scope_id?: string } }[] };
      return body.items.find((i) => i.details?.scope_id?.startsWith(prefix ?? ""))?.details?.scope_id;
    }, scopePrefix);
    expect(fullScopeId, "could not resolve the full scope_id from the audit log").toBeTruthy();

    await page.goto("/vault");
    await page.locator("#vault-placeholder").fill(placeholder!);
    await page.locator("#vault-scope").fill(fullScopeId!);
    await page.getByRole("button", { name: "Detokenize" }).click();

    await expect(page.getByText("Contact")).toBeVisible();
    await expect(page.getByText("••••••••••••")).toBeVisible();
    await page.getByRole("button", { name: "Reveal" }).click();
    await expect(page.getByText(email)).toBeVisible();
  });
});

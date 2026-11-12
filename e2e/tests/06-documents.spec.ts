import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { asOwner } from "../helpers";

/**
 * The real API (documents/router.py) returns the protected file's raw bytes directly,
 * never a JSON findings report, on a successful upload. An earlier version of the
 * frontend called response.json() unconditionally, which throws on that binary body,
 * silently discarding the protected file and showing nothing to download; this proves
 * the fixed upload path actually offers a real, downloadable protected file.
 */
test.describe("documents", () => {
  test("uploading a CSV with a real email returns a downloadable protected file", async ({ page }) => {
    const dir = await mkdtemp(path.join(tmpdir(), "piishield-e2e-"));
    const csvPath = path.join(dir, "customers.csv");
    await writeFile(csvPath, "name,email\nJane Doe,jane.doe@example.com\n");

    await asOwner(page, "/documents");
    const [fileChooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: "Choose file" }).click()]);
    await fileChooser.setFiles(csvPath);

    await expect(page.getByText(/protected file ready/i)).toBeVisible();
    const downloadLink = page.getByRole("link", { name: /download/i });
    await expect(downloadLink).toBeVisible();

    const [download] = await Promise.all([page.waitForEvent("download"), downloadLink.click()]);
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    const content = await readFile(downloadPath!, "utf8");
    expect(content).not.toContain("jane.doe@example.com");
    expect(content).toContain("name,email");
  });
});

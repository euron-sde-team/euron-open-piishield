/**
 * The Node SDK against a real, running PIIShield API. Set TEST_API_URL, TEST_API_KEY and
 * TEST_PROJECT_ID to run; skipped otherwise, matching the sibling projects' pattern.
 */

import { beforeAll, describe, expect, it } from "vitest";

import { PIIShield, VaultPermissionError } from "../../src/index.js";

const API_URL = process.env.TEST_API_URL ?? "";
const API_KEY = process.env.TEST_API_KEY ?? "";
const PROJECT_ID = process.env.TEST_PROJECT_ID ?? "";

describe.skipIf(!API_URL || !API_KEY || !PROJECT_ID)("live API", () => {
  let shield: PIIShield;

  beforeAll(() => {
    shield = new PIIShield({ apiUrl: API_URL, apiKey: API_KEY, projectId: PROJECT_ID });
  });

  it("scan finds PII in text", async () => {
    const result = await shield.scan("Email: rahul@example.com");
    expect(result.findings.some((f) => f.recognizer === "email" && f.category === "contact")).toBe(true);
  });

  it("mask full_mask replaces the value", async () => {
    const result = await shield.mask("Email: rahul@example.com", { method: "full_mask" });
    expect(result.protectedText).not.toContain("rahul@example.com");
  });

  it("tokenize is scope consistent", async () => {
    const first = await shield.tokenize("rahul@example.com", { scopeId: "node-it-session" });
    const second = await shield.tokenize("rahul@example.com", { scopeId: "node-it-session" });
    expect(first.protectedText).toBe(second.protectedText);
  });

  it("detokenize without the vault grant rejects with VaultPermissionError", async () => {
    const result = await shield.tokenize("rahul@example.com", { scopeId: "node-it-session-2" });
    const placeholder = result.findings.find((f) => f.placeholder)?.placeholder;
    if (!placeholder) return; // server did not return a placeholder to detokenize
    await expect(shield.detokenize(placeholder, "node-it-session-2")).rejects.toBeInstanceOf(VaultPermissionError);
  });

  it("protect then restore round trips a PAN", async () => {
    // ABCPE1234F is structurally valid (4th letter P = person; see
    // piishield.detectors.checksums.pan_entity_ok); ABCDE1234F is not a real PAN shape
    // ("D" is not a valid entity-type letter) and the checksum-validated recognizer
    // correctly finds nothing for it.
    const protected_ = await shield.protect("My PAN is ABCPE1234F. Explain my tax record.");
    expect(protected_.protectedText).not.toContain("ABCPE1234F");
    const modelResponse = protected_.protectedText.replace("Explain", "Explained");
    const restored = await shield.restore(protected_.scopeId, modelResponse);
    expect(restored.restoredText).toContain("ABCPE1234F");
  });
});

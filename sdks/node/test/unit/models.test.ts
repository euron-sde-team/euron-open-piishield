import { describe, expect, it } from "vitest";

import { Finding, ProtectResult, ProtectionResult, ScanResult } from "../../src/index.js";

describe("Finding.fromApi", () => {
  it("parses every field", () => {
    const f = Finding.fromApi({
      category: "email",
      start: 1,
      end: 5,
      confidence: 0.8,
      checksum_valid: null,
      recognizer: "email_regex",
      method: "full_mask",
      placeholder: null,
      in_review: false,
    });
    expect(f.start).toBe(1);
    expect(f.end).toBe(5);
    expect(f.recognizer).toBe("email_regex");
    expect(f.method).toBe("full_mask");
  });

  it("keeps unknown fields in raw", () => {
    const f = Finding.fromApi({ category: "email", start: 0, end: 1, confidence: 0.5, future_field: "x" });
    expect(f.raw.future_field).toBe("x");
  });
});

describe("ScanResult.fromApi", () => {
  it("defaults to an empty findings list", () => {
    const result = ScanResult.fromApi({});
    expect(result.findings).toEqual([]);
  });
});

describe("ProtectionResult.fromApi", () => {
  it("reads protected and scope_id, never an original-value field", () => {
    const result = ProtectionResult.fromApi({ protected: "[REDACTED]", findings: [], scope_id: "s1" });
    expect(Object.keys(result)).not.toContain("value");
    expect(Object.keys(result)).not.toContain("original");
    expect(result.protectedText).toBe("[REDACTED]");
    expect(result.scopeId).toBe("s1");
  });
});

describe("ProtectResult.fromApi", () => {
  it("reads protected_prompt and scope_id as separate fields", () => {
    const result = ProtectResult.fromApi({ protected_prompt: "safe to send", scope_id: "tm_1", findings: [] });
    expect(result.scopeId).toBe("tm_1");
    expect(result.protectedText).not.toBe(result.scopeId);
  });
});

import { describe, expect, it } from "vitest";

import { isPolicyDraftValid, knownCategories, MASKING_METHODS, unmaskedRequiredCategories } from "@/lib/policy";

describe("unmaskedRequiredCategories", () => {
  it("flags a required category with no configured masking method (AC10 mirror)", () => {
    const draft = { requiredCategories: ["financial", "government_id"], maskingMethod: { financial: "tokenize" } };
    expect(unmaskedRequiredCategories(draft)).toEqual(["government_id"]);
  });

  it("is empty when every required category has a method", () => {
    const draft = { requiredCategories: ["contact"], maskingMethod: { contact: "partial_mask" } };
    expect(unmaskedRequiredCategories(draft)).toEqual([]);
  });

  it("ignores categories that are not required even without a method", () => {
    const draft = { requiredCategories: [], maskingMethod: {} };
    expect(unmaskedRequiredCategories(draft)).toEqual([]);
  });
});

describe("isPolicyDraftValid", () => {
  it("mirrors unmaskedRequiredCategories being empty", () => {
    expect(isPolicyDraftValid({ requiredCategories: ["government_id"], maskingMethod: {} })).toBe(false);
    expect(
      isPolicyDraftValid({ requiredCategories: ["government_id"], maskingMethod: { government_id: "redact" } }),
    ).toBe(true);
  });
});

describe("known lists", () => {
  it("exposes the suggested category chips and the four masking methods", () => {
    expect(knownCategories()).toContain("contact");
    expect(knownCategories()).toContain("credential");
    expect(knownCategories()).toContain("financial");
    expect(knownCategories()).toContain("government_id");
    expect(knownCategories()).toContain("personal");
    expect(MASKING_METHODS).toEqual(["full_mask", "partial_mask", "redact", "tokenize"]);
  });
});

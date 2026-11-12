import { describe, expect, it } from "vitest";

import { categoryLabel, formatConfidence, initials, methodLabel, slugify } from "@/lib/format";

describe("initials", () => {
  it("takes the first letter of the first and last word", () => {
    expect(initials("Priya Nair")).toBe("PN");
    expect(initials("Madonna")).toBe("M");
    expect(initials("")).toBe("?");
    expect(initials(undefined)).toBe("?");
    expect(initials("  ")).toBe("?");
  });
});

describe("formatConfidence", () => {
  it("rounds to a whole percent", () => {
    expect(formatConfidence(0.95)).toBe("95%");
    expect(formatConfidence(0.001)).toBe("0%");
    expect(formatConfidence(1)).toBe("100%");
  });
});

describe("methodLabel and categoryLabel", () => {
  it("labels known masking methods", () => {
    expect(methodLabel("full_mask")).toBe("Full mask");
    expect(methodLabel("tokenize")).toBe("Tokenize");
  });

  it("falls back to a spaced, capitalized label for an unknown method", () => {
    expect(methodLabel("something_new")).toBe("something new");
  });

  it("capitalizes a free-form category key", () => {
    expect(categoryLabel("bank_account")).toBe("Bank account");
    expect(categoryLabel("pan")).toBe("Pan");
  });
});

describe("slugify", () => {
  it("derives a valid project slug from a display name", () => {
    expect(slugify("Customer Support")).toBe("customer-support");
    expect(slugify("  Verdant Pay!! ")).toBe("verdant-pay");
    expect(slugify("A/B Testing Team")).toBe("a-b-testing-team");
  });

  it("returns empty for a name with no usable characters", () => {
    expect(slugify("!!!")).toBe("");
  });

  it("prefixes a slug that would otherwise start with a hyphen", () => {
    // Extremely unlikely after the leading/trailing hyphen trim, but guarded anyway.
    expect(slugify("---")).toBe("");
  });

  it("truncates to 64 characters", () => {
    const long = "a".repeat(100);
    expect(slugify(long).length).toBeLessThanOrEqual(64);
  });
});

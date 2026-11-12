import { describe, expect, it } from "vitest";

import { buildHighlightSegments, type SpanFinding } from "@/lib/highlight";

function finding(partial: Partial<SpanFinding> & Pick<SpanFinding, "start" | "end">): SpanFinding {
  return { category: "email", confidence: 0.9, recognizer: "email", checksum_valid: null, ...partial };
}

describe("buildHighlightSegments", () => {
  it("returns the whole text as one plain segment when there are no findings", () => {
    const segments = buildHighlightSegments("hello world", []);
    expect(segments).toEqual([{ text: "hello world", findings: [] }]);
  });

  it("returns nothing for empty text", () => {
    expect(buildHighlightSegments("", [])).toEqual([]);
  });

  it("splits plain text around a single finding", () => {
    const text = "Contact jane@example.com today";
    const f = finding({ start: 8, end: 24 });
    const segments = buildHighlightSegments(text, [f]);
    expect(segments).toEqual([
      { text: "Contact ", findings: [] },
      { text: "jane@example.com", findings: [f] },
      { text: " today", findings: [] },
    ]);
  });

  it("drops out-of-bounds and zero-length spans", () => {
    const text = "short";
    const bad1 = finding({ start: -1, end: 2 });
    const bad2 = finding({ start: 3, end: 3 });
    const bad3 = finding({ start: 2, end: 100 });
    expect(buildHighlightSegments(text, [bad1, bad2, bad3])).toEqual([{ text: "short", findings: [] }]);
  });

  it("merges overlapping spans into one segment carrying both findings", () => {
    const text = "0123456789";
    const a = finding({ category: "email", start: 2, end: 6 });
    const b = finding({ category: "phone", start: 4, end: 8 });
    const segments = buildHighlightSegments(text, [a, b]);
    expect(segments).toEqual([
      { text: "01", findings: [] },
      { text: "234567", findings: [a, b] },
      { text: "89", findings: [] },
    ]);
  });

  it("merges adjacent (touching) spans into one segment", () => {
    const text = "abcdef";
    const a = finding({ start: 0, end: 3 });
    const b = finding({ start: 3, end: 6 });
    const segments = buildHighlightSegments(text, [a, b]);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toEqual({ text: "abcdef", findings: [a, b] });
  });

  it("sorts out-of-order findings before building segments", () => {
    const text = "0123456789";
    const a = finding({ category: "a", start: 6, end: 8 });
    const b = finding({ category: "b", start: 0, end: 2 });
    const segments = buildHighlightSegments(text, [a, b]);
    expect(segments.map((s) => s.text)).toEqual(["01", "2345", "67", "89"]);
    expect(segments[0]!.findings).toEqual([b]);
    expect(segments[2]!.findings).toEqual([a]);
  });
});

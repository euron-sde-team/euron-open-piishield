import { describe, expect, it } from "vitest";

import type { AuditEntry, ReviewItem } from "@/lib/api/types";
import { auditDetailSummary, hasSummarizableDetails } from "@/lib/audit";
import { pendingOnly, sortByCreatedDesc } from "@/lib/review";

function reviewItem(partial: Partial<ReviewItem>): ReviewItem {
  return {
    id: "1",
    project_id: "p1",
    category: "email",
    start: 0,
    end: 5,
    confidence: 0.5,
    recognizer: "email",
    already_protected: false,
    status: "pending",
    created_at: "2026-01-01T00:00:00Z",
    decided_at: null,
    ...partial,
  };
}

function auditEntry(partial: Partial<AuditEntry>): AuditEntry {
  return {
    id: "1",
    created_at: "2026-01-01T00:00:00Z",
    actor_kind: "user",
    actor_label: "someone",
    action: "scan",
    project_id: "p1",
    finding_count: 1,
    categories: ["email"],
    details: {},
    ...partial,
  };
}

describe("pendingOnly", () => {
  it("keeps only items whose status is pending, even if the API over-returns", () => {
    const items = [reviewItem({ id: "a", status: "pending" }), reviewItem({ id: "b", status: "approved" }), reviewItem({ id: "c", status: "dismissed" })];
    expect(pendingOnly(items).map((i) => i.id)).toEqual(["a"]);
  });
});

describe("sortByCreatedDesc", () => {
  it("sorts newest first without mutating the input", () => {
    const items = [
      reviewItem({ id: "old", created_at: "2026-01-01T00:00:00Z" }),
      reviewItem({ id: "new", created_at: "2026-02-01T00:00:00Z" }),
    ];
    const sorted = sortByCreatedDesc(items);
    expect(sorted.map((i) => i.id)).toEqual(["new", "old"]);
    expect(items.map((i) => i.id)).toEqual(["old", "new"]);
  });
});

describe("auditDetailSummary", () => {
  it("picks known, non-sensitive fields out of the open details object", () => {
    const entry = auditEntry({ details: { source: "text", scope_id: "abc123", unrelated: "ignored" } });
    expect(auditDetailSummary(entry)).toEqual([
      { key: "source", value: "text" },
      { key: "scope_id", value: "abc123" },
    ]);
    expect(hasSummarizableDetails(entry)).toBe(true);
  });

  it("is empty when details has nothing recognizable", () => {
    const entry = auditEntry({ details: { something_else: 1 } });
    expect(auditDetailSummary(entry)).toEqual([]);
    expect(hasSummarizableDetails(entry)).toBe(false);
  });

  it("never surfaces an original value: only whitelisted keys are read", () => {
    const entry = auditEntry({ details: { original_value: "4111111111111111", source: "text" } });
    const summary = auditDetailSummary(entry);
    expect(summary.some((s) => s.value.includes("4111111111111111"))).toBe(false);
  });
});

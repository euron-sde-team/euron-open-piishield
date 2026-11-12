import { describe, expect, it } from "vitest";

import { APIError, PIIShield, PIIShieldConnectionError, PolicyViolationError, VaultPermissionError } from "../../src/index.js";
import { API_KEY, BASE, FakeApi, PROJECT_ID, errorBody, finding, json, protectTextResponse, scanResponse } from "./fake.js";

function setup(options: Partial<ConstructorParameters<typeof PIIShield>[0]> = {}) {
  const api = new FakeApi();
  const shield = new PIIShield({ apiUrl: BASE, apiKey: API_KEY, projectId: PROJECT_ID, fetch: api.fetch, ...options });
  return { api, shield };
}

describe("options", () => {
  it("are validated", () => {
    expect(() => new PIIShield({ apiUrl: "piishield.test", apiKey: API_KEY, projectId: PROJECT_ID })).toThrow(/http/);
    expect(() => new PIIShield({ apiUrl: BASE, apiKey: "", projectId: PROJECT_ID })).toThrow(/apiKey/);
    expect(new PIIShield({ apiUrl: `${BASE}//`, apiKey: API_KEY, projectId: PROJECT_ID }).apiUrl).toBe(BASE);
  });
});

describe("scan", () => {
  it("calls the dedicated scan route and parses findings", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/detectors/scan", () =>
      json(200, scanResponse([finding("contact", 0, 10, 0.95, { recognizer: "email" })])),
    );
    const result = await shield.scan("rahul@x.com");
    const sent = JSON.parse(api.last("POST", "/api/v1/detectors/scan").body);
    expect(sent).toEqual({ project_id: PROJECT_ID, text: "rahul@x.com" });
    expect(api.last("POST", "/api/v1/detectors/scan").headers.authorization).toBe(`Bearer ${API_KEY}`);
    expect(result.findings).toHaveLength(1);
    expect(result.findings[0]!.category).toBe("contact");
    expect(result.findings[0]!.recognizer).toBe("email");
    expect(result.findings[0]!.start).toBe(0);
    expect(result.findings[0]!.end).toBe(10);
  });

  it("scanJson wraps the payload", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/json", () => json(200, { protected: {}, findings: [], review_count: 0, scope_id: "s" }));
    const payload = { customer: { email: "a@b.com" }, tags: ["x", "y"] };
    await shield.scanJson(payload);
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/json").body);
    expect(sent.payload).toEqual(payload);
    expect(sent.project_id).toBe(PROJECT_ID);
  });
});

describe("mask", () => {
  it("sends method_overrides and project_id", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(200, protectTextResponse("Hello [REDACTED]")));
    const result = await shield.mask("Hello Rahul", { method: "redact", categories: ["personal"] });
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/text").body);
    expect(sent).toEqual({
      project_id: PROJECT_ID,
      text: "Hello Rahul",
      method_overrides: { personal: "redact" },
    });
    expect(result.protectedText).toBe("Hello [REDACTED]");
  });

  it("defaults to full_mask when no method given", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(200, protectTextResponse("***")));
    await shield.mask("secret", { categories: ["contact"] });
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/text").body);
    expect(sent.method_overrides).toEqual({ contact: "full_mask" });
  });
});

describe("convenience wrappers", () => {
  it("redact applies method override redact", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(200, protectTextResponse("x")));
    await shield.redact("some text", ["contact"]);
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/text").body);
    expect(sent.method_overrides).toEqual({ contact: "redact" });
  });

  it("anonymize applies method override full_mask", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(200, protectTextResponse("x")));
    await shield.anonymize("some text", ["contact"]);
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/text").body);
    expect(sent.method_overrides).toEqual({ contact: "full_mask" });
  });

  it("tokenize applies method override tokenize and forwards scopeId", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(200, protectTextResponse("x", [], { scope_id: "req-1" })));
    await shield.tokenize("some text", { scopeId: "req-1", categories: ["contact"] });
    const sent = JSON.parse(api.last("POST", "/api/v1/protect/text").body);
    expect(sent.method_overrides).toEqual({ contact: "tokenize" });
    expect(sent.scope_id).toBe("req-1");
  });
});

describe("tokenize scope consistency (AC4)", () => {
  it("sends the same scope_id on both calls and the SDK never rewrites it", async () => {
    const { api, shield } = setup();
    api.on(
      "POST",
      "/api/v1/protect/text",
      () => json(200, protectTextResponse("[EMAIL_001]", [], { scope_id: "session-42" })),
      () => json(200, protectTextResponse("[EMAIL_001]", [], { scope_id: "session-42" })),
    );
    const first = await shield.tokenize("a@example.com", { scopeId: "session-42" });
    const second = await shield.tokenize("a@example.com", { scopeId: "session-42" });
    expect(api.count("POST", "/api/v1/protect/text")).toBe(2);
    expect(first.protectedText).toBe(second.protectedText);
    expect(first.scopeId).toBe("session-42");
    expect(second.scopeId).toBe("session-42");
  });
});

describe("detokenize and the vault permission model", () => {
  it("sends placeholder and scope_id", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/vault/detokenize", () =>
      json(200, { placeholder: "[EMAIL_001]", value: "a@example.com", category: "contact" }),
    );
    const result = await shield.detokenize("[EMAIL_001]", "session-42");
    const sent = JSON.parse(api.last("POST", "/api/v1/vault/detokenize").body);
    expect(sent).toEqual({ project_id: PROJECT_ID, placeholder: "[EMAIL_001]", scope_id: "session-42" });
    expect(result.value).toBe("a@example.com");
  });

  it("rejects with VaultPermissionError on 403 vault_access_required, never a value or hint of it", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/vault/detokenize", () => json(403, errorBody("vault_access_required", "forbidden")));
    await expect(shield.detokenize("[EMAIL_001]", "s1")).rejects.toBeInstanceOf(VaultPermissionError);
    try {
      await shield.detokenize("[EMAIL_001]", "s1");
      expect.fail("should have thrown");
    } catch (error) {
      expect((error as Error).message).not.toContain("@");
      expect((error as VaultPermissionError).status).toBe(403);
    }
  });

  it("a different 403 code stays a plain APIError, not VaultPermissionError", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/detectors/scan", () => json(403, errorBody("insufficient_role")));
    await expect(shield.scan("x")).rejects.toBeInstanceOf(APIError);
    try {
      await shield.scan("x");
    } catch (error) {
      expect(error).not.toBeInstanceOf(VaultPermissionError);
    }
  });
});

describe("policy violation", () => {
  it("rejects with PolicyViolationError on 422 required_category_unmasked", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/protect/text", () => json(422, errorBody("required_category_unmasked", "financial must be masked")));
    await expect(shield.mask("card 4111111111111111")).rejects.toBeInstanceOf(PolicyViolationError);
  });
});

describe("dependency unavailable and transport failures", () => {
  it("a 503 maps to PIIShieldConnectionError", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/detectors/scan", () => json(503, errorBody("dependency_unavailable")));
    await expect(shield.scan("x")).rejects.toBeInstanceOf(PIIShieldConnectionError);
  });

  it("a network failure maps to PIIShieldConnectionError, not a bare fetch error", async () => {
    const shield = new PIIShield({
      apiUrl: BASE,
      apiKey: API_KEY,
      projectId: PROJECT_ID,
      fetch: () => Promise.reject(new TypeError("fetch failed")),
    });
    await expect(shield.scan("x")).rejects.toBeInstanceOf(PIIShieldConnectionError);
  });
});

describe("AI gateway", () => {
  it("separates protectedText from scopeId", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/ai-gateway/protect", () =>
      json(200, {
        protected_prompt: "My PAN is [PAN_001]. Explain my tax record.",
        scope_id: "scope-abc123",
        findings: [finding("pan", 10, 20, 0.9)],
      }),
    );
    const result = await shield.protect("My PAN is ABCDE1234F. Explain my tax record.");
    expect(result.protectedText).not.toContain("ABCDE1234F");
    expect(result.scopeId).toBe("scope-abc123");
  });

  it("restore sends scope_id and model_response", async () => {
    const { api, shield } = setup();
    api.on("POST", "/api/v1/ai-gateway/restore", () =>
      json(200, { restored_response: "Your PAN ABCDE1234F is valid.", placeholders_restored: 1 }),
    );
    const result = await shield.restore("scope-abc123", "Your PAN [PAN_001] is valid.");
    const sent = JSON.parse(api.last("POST", "/api/v1/ai-gateway/restore").body);
    expect(sent).toEqual({ project_id: PROJECT_ID, scope_id: "scope-abc123", model_response: "Your PAN [PAN_001] is valid." });
    expect(result.restoredText).toBe("Your PAN ABCDE1234F is valid.");
  });
});

describe("policies and audit logs", () => {
  it("getPolicy parses the response", async () => {
    const { api, shield } = setup();
    api.on("GET", `/api/v1/projects/${PROJECT_ID}/policy`, () =>
      json(200, {
        id: "p1",
        project_id: PROJECT_ID,
        required_categories: ["financial"],
        masking_method: { financial: "tokenize" },
        partial_mask_reveal: 4,
        confidence_threshold: 0.6,
        retention_days: 90,
      }),
    );
    const policy = await shield.getPolicy();
    expect(policy.requiredCategories).toEqual(["financial"]);
  });

  it("audit log entries never carry a value or original field", async () => {
    const { api, shield } = setup();
    api.on("GET", "/api/v1/audit", () =>
      json(200, {
        items: [
          {
            id: "log1",
            created_at: "2026-11-12T00:00:00Z",
            actor_kind: "api_key",
            actor_label: "api-key:ci",
            action: "protect_text",
            project_id: PROJECT_ID,
            finding_count: 2,
            categories: ["contact"],
            details: {},
          },
        ],
        next_cursor: null,
      }),
    );
    const page = await shield.getAuditLogs();
    expect(page.items[0]!.action).toBe("protect_text");
    expect(Object.keys(page.items[0]!)).not.toContain("value");
    expect(Object.keys(page.items[0]!)).not.toContain("original");
  });
});

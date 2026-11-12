import { describe, expect, it } from "vitest";

import { ApiError, errorMessage, isErrorEnvelope, isVaultForbidden, parseApiError, validationMessages } from "@/lib/api/errors";

describe("parseApiError", () => {
  it("reads the PIIShield envelope with structured details", () => {
    const err = parseApiError(403, {
      error: { code: "forbidden", type: "forbidden_error", message: "You do not have vault access", details: { project_id: "x" } },
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(err.code).toBe("forbidden");
    expect(err.isForbidden).toBe(true);
    expect(err.details).toEqual({ project_id: "x" });
    expect(errorMessage(err)).toContain("vault access");
  });

  it("falls back to an actionable message for non-envelope bodies", () => {
    expect(parseApiError(500, "<html>").message).toMatch(/Retry/);
    expect(parseApiError(403, null).isForbidden).toBe(true);
    expect(parseApiError(0, null).isNetwork).toBe(true);
  });

  it("understands FastAPI's raw validation shape", () => {
    const err = parseApiError(422, { detail: [{ loc: ["query", "project_id"], msg: "Input should be a valid UUID" }] });
    expect(err.code).toBe("validation_error");
    expect(errorMessage(err)).toBe("project_id: Input should be a valid UUID");
  });
});

describe("validation and messages", () => {
  it("drops the location prefix and joins fields", () => {
    expect(validationMessages({ errors: [{ loc: ["body", "name"], msg: "required" }, { loc: [], msg: "bad" }] })).toEqual([
      "name: required",
      "bad",
    ]);
    expect(validationMessages({})).toEqual([]);
  });

  it("tells people to sign in again on 401, except for wrong credentials", () => {
    expect(errorMessage(new ApiError({ status: 401, code: "session_expired", message: "x" }))).toMatch(/Sign in again/);
    expect(errorMessage(new ApiError({ status: 401, code: "invalid_credentials", message: "Email or password is incorrect" }))).toBe(
      "Email or password is incorrect",
    );
  });

  it("maps network failures and unknown throwables", () => {
    expect(errorMessage(new TypeError("fetch failed"))).toMatch(/Cannot reach/);
    expect(errorMessage(new Error("boom"))).toBe("boom");
    expect(isErrorEnvelope({ error: { code: "x" } })).toBe(false);
  });

  it("flags a 403 as vault-forbidden but not other statuses", () => {
    expect(isVaultForbidden(new ApiError({ status: 403, code: "forbidden", message: "x" }))).toBe(true);
    expect(isVaultForbidden(new ApiError({ status: 404, code: "not_found", message: "x" }))).toBe(false);
    expect(isVaultForbidden(new Error("x"))).toBe(false);
  });
});

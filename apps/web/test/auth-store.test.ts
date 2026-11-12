import { beforeEach, describe, expect, it } from "vitest";

import { getAuthToken, useAuthStore } from "@/lib/auth-store";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null });
  });

  it("starts signed out", () => {
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(getAuthToken()).toBeNull();
  });

  it("setSession stores the bearer token and user together", () => {
    const user = { id: "u1", org_id: "o1", email: "priya@example.com", name: "Priya Nair", role: "owner", vault_access: true };
    useAuthStore.getState().setSession({ token: "jwt-abc", user });
    expect(useAuthStore.getState().token).toBe("jwt-abc");
    expect(useAuthStore.getState().user).toEqual(user);
    expect(getAuthToken()).toBe("jwt-abc");
  });

  it("clearSession wipes both the token and the user", () => {
    const user = { id: "u1", org_id: "o1", email: "priya@example.com", name: "Priya Nair", role: "owner", vault_access: true };
    useAuthStore.getState().setSession({ token: "jwt-abc", user });
    useAuthStore.getState().clearSession();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(getAuthToken()).toBeNull();
  });
});

import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "./auth-store";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: true });
  });

  it("starts unauthenticated and loading", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(true);
    expect(state.user).toBeNull();
  });

  it("sets user and marks authenticated", () => {
    const user = {
      rid: "ri.user.1",
      email: "admin@test.com",
      display_name: "Admin",
      role: "admin" as const,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      last_login_at: null,
    };
    useAuthStore.getState().setUser(user);
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
    expect(state.user?.email).toBe("admin@test.com");
  });

  it("clears user on null", () => {
    useAuthStore.getState().setUser({
      rid: "ri.user.1",
      email: "a@b.com",
      display_name: "A",
      role: "admin",
      is_active: true,
      created_at: "",
      last_login_at: null,
    });
    useAuthStore.getState().setUser(null);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("logs out", () => {
    useAuthStore.getState().setUser({
      rid: "ri.user.1",
      email: "a@b.com",
      display_name: "A",
      role: "admin",
      is_active: true,
      created_at: "",
      last_login_at: null,
    });
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });
});

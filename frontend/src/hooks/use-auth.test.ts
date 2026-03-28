import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAuth } from "./use-auth";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockMe = vi.fn();
const mockLogin = vi.fn();
const mockLogout = vi.fn();
const mockRefresh = vi.fn();

vi.mock("@/lib/api/setting", () => ({
  settingApi: {
    get me() { return mockMe; },
    get login() { return mockLogin; },
    get logout() { return mockLogout; },
    get refresh() { return mockRefresh; },
  },
}));

const mockSetUser = vi.fn();
const mockSetLoading = vi.fn();
const mockClearAuth = vi.fn();

let mockStoreState = { user: null as unknown, isAuthenticated: false, isLoading: true };

vi.mock("@/stores/auth-store", () => ({
  useAuthStore: () => ({
    ...mockStoreState,
    setUser: mockSetUser,
    setLoading: mockSetLoading,
    logout: mockClearAuth,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockStoreState = { user: null, isAuthenticated: false, isLoading: true };
});

describe("useAuth", () => {
  it("checks auth on mount by calling me()", async () => {
    mockMe.mockResolvedValue({ data: { rid: "ri.user.1", email: "admin@test.com" } });

    renderHook(() => useAuth());

    await waitFor(() => {
      expect(mockMe).toHaveBeenCalled();
    });
    expect(mockSetUser).toHaveBeenCalledWith({ rid: "ri.user.1", email: "admin@test.com" });
  });

  it("sets user to null when me() fails", async () => {
    mockMe.mockRejectedValue(new Error("Unauthorized"));

    renderHook(() => useAuth());

    await waitFor(() => {
      expect(mockMe).toHaveBeenCalled();
    });
    expect(mockSetUser).toHaveBeenCalledWith(null);
  });

  it("returns isLoading, isAuthenticated, and user from store", () => {
    mockMe.mockResolvedValue({ data: null });

    const { result } = renderHook(() => useAuth());

    expect(result.current).toHaveProperty("isLoading");
    expect(result.current).toHaveProperty("isAuthenticated");
    expect(result.current).toHaveProperty("user");
    expect(result.current).toHaveProperty("login");
    expect(result.current).toHaveProperty("logout");
  });
});

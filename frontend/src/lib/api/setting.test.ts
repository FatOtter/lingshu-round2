import { describe, it, expect, vi, beforeEach } from "vitest";
import { settingApi } from "./setting";
import { apiClient } from "./client";

vi.mock("./client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("settingApi", () => {
  it("login posts email and password", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { user: { rid: "ri.user.1" }, access_token: "tok" } });

    const result = await settingApi.login("admin@test.com", "secret");

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/auth/login", { email: "admin@test.com", password: "secret" });
    expect(result.data.access_token).toBe("tok");
  });

  it("logout posts to logout endpoint", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: null });

    await settingApi.logout();

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/auth/logout");
  });

  it("queryUsers posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 10, has_next: false } });

    await settingApi.queryUsers({ pagination: { page: 1, page_size: 10 } });

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/users/query", { pagination: { page: 1, page_size: 10 } });
  });

  it("createUser posts user data", async () => {
    const data = { email: "user@test.com", display_name: "User", password: "pass123" };
    vi.mocked(apiClient.post).mockResolvedValue({ data: { rid: "ri.user.2", ...data } });

    const result = await settingApi.createUser(data);

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/users", data);
    expect(result.data.email).toBe("user@test.com");
  });

  it("deleteUser sends delete by rid", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({ data: null });

    await settingApi.deleteUser("ri.user.2");

    expect(apiClient.delete).toHaveBeenCalledWith("/setting/v1/users/ri.user.2");
  });

  it("queryTenants posts with params", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: [], pagination: { total: 0, page: 1, page_size: 5, has_next: false } });

    await settingApi.queryTenants({ pagination: { page: 1, page_size: 5 } });

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/tenants/query", { pagination: { page: 1, page_size: 5 } });
  });

  it("ssoConfig fetches SSO configuration", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { enabled: true, provider_name: "okta", authorization_url: "https://okta.example.com" } });

    const result = await settingApi.ssoConfig();

    expect(apiClient.get).toHaveBeenCalledWith("/setting/v1/auth/sso/config");
    expect(result.data.enabled).toBe(true);
  });

  it("me fetches current user", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { rid: "ri.user.1", email: "admin@test.com" } });

    const result = await settingApi.me();

    expect(apiClient.get).toHaveBeenCalledWith("/setting/v1/auth/me");
    expect(result.data.email).toBe("admin@test.com");
  });

  it("changePassword posts current and new password", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: null });

    await settingApi.changePassword("old-pass", "new-pass");

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/auth/change-password", {
      current_password: "old-pass",
      new_password: "new-pass",
    });
  });

  it("createTenant posts tenant data", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { rid: "ri.tenant.1" } });

    await settingApi.createTenant({ display_name: "Acme Corp" });

    expect(apiClient.post).toHaveBeenCalledWith("/setting/v1/tenants", { display_name: "Acme Corp" });
  });
});

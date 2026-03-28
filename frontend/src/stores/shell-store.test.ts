import { describe, it, expect, beforeEach } from "vitest";
import { useShellStore } from "./shell-store";

describe("useShellStore", () => {
  beforeEach(() => {
    useShellStore.setState({ isOpen: false, width: 400, sessionId: null });
  });

  it("starts closed", () => {
    expect(useShellStore.getState().isOpen).toBe(false);
  });

  it("opens", () => {
    useShellStore.getState().open();
    expect(useShellStore.getState().isOpen).toBe(true);
  });

  it("closes", () => {
    useShellStore.getState().open();
    useShellStore.getState().close();
    expect(useShellStore.getState().isOpen).toBe(false);
  });

  it("toggles", () => {
    useShellStore.getState().toggle();
    expect(useShellStore.getState().isOpen).toBe(true);
    useShellStore.getState().toggle();
    expect(useShellStore.getState().isOpen).toBe(false);
  });

  it("sets session id", () => {
    useShellStore.getState().setSessionId("sess-1");
    expect(useShellStore.getState().sessionId).toBe("sess-1");
  });
});

import { describe, it, expect, beforeEach } from "vitest";
import { useTabStore } from "./tab-store";

describe("useTabStore", () => {
  beforeEach(() => {
    useTabStore.setState({ tabs: [], activeTabId: null });
  });

  it("opens a tab", () => {
    useTabStore.getState().openTab({
      id: "tab-1",
      title: "ObjectType",
      path: "/ontology/object-types/ri.obj.1",
      module: "ontology",
    });
    const state = useTabStore.getState();
    expect(state.tabs).toHaveLength(1);
    expect(state.activeTabId).toBe("tab-1");
    expect(state.tabs[0].isDirty).toBe(false);
  });

  it("activates existing tab instead of duplicating", () => {
    const tab = {
      id: "tab-1",
      title: "ObjectType",
      path: "/ontology/object-types/ri.obj.1",
      module: "ontology",
    };
    useTabStore.getState().openTab(tab);
    useTabStore.getState().openTab({
      id: "tab-2",
      title: "LinkType",
      path: "/ontology/link-types/ri.lnk.1",
      module: "ontology",
    });
    useTabStore.getState().openTab(tab);
    expect(useTabStore.getState().tabs).toHaveLength(2);
    expect(useTabStore.getState().activeTabId).toBe("tab-1");
  });

  it("closes a tab", () => {
    useTabStore.getState().openTab({
      id: "tab-1",
      title: "Test",
      path: "/test",
      module: "test",
    });
    useTabStore.getState().openTab({
      id: "tab-2",
      title: "Test2",
      path: "/test2",
      module: "test",
    });
    useTabStore.getState().closeTab("tab-1");
    expect(useTabStore.getState().tabs).toHaveLength(1);
    expect(useTabStore.getState().tabs[0].id).toBe("tab-2");
  });

  it("marks tab as dirty", () => {
    useTabStore.getState().openTab({
      id: "tab-1",
      title: "Test",
      path: "/test",
      module: "test",
    });
    useTabStore.getState().markDirty("tab-1", true);
    expect(useTabStore.getState().tabs[0].isDirty).toBe(true);
  });

  it("closes other tabs", () => {
    useTabStore.getState().openTab({ id: "t1", title: "A", path: "/a", module: "m" });
    useTabStore.getState().openTab({ id: "t2", title: "B", path: "/b", module: "m" });
    useTabStore.getState().openTab({ id: "t3", title: "C", path: "/c", module: "m" });
    useTabStore.getState().closeOtherTabs("t2");
    expect(useTabStore.getState().tabs).toHaveLength(1);
    expect(useTabStore.getState().tabs[0].id).toBe("t2");
  });

  it("closes all tabs", () => {
    useTabStore.getState().openTab({ id: "t1", title: "A", path: "/a", module: "m" });
    useTabStore.getState().openTab({ id: "t2", title: "B", path: "/b", module: "m" });
    useTabStore.getState().closeAllTabs();
    expect(useTabStore.getState().tabs).toHaveLength(0);
    expect(useTabStore.getState().activeTabId).toBeNull();
  });
});

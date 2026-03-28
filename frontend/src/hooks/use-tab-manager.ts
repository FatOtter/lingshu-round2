"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTabStore, type Tab } from "@/stores/tab-store";

export function useTabManager() {
  const router = useRouter();
  const { tabs, activeTabId, openTab, closeTab, activateTab, markDirty, closeAllTabs, closeOtherTabs } =
    useTabStore();

  const open = useCallback(
    (tab: Omit<Tab, "isDirty">) => {
      openTab(tab);
      router.push(tab.path);
    },
    [openTab, router],
  );

  const close = useCallback(
    (id: string) => {
      const tab = tabs.find((t) => t.id === id);
      if (tab?.isDirty) {
        // Could show confirmation dialog - for now just close
      }
      closeTab(id);
      // Navigate to next active tab
      const remaining = tabs.filter((t) => t.id !== id);
      if (remaining.length > 0) {
        const idx = tabs.findIndex((t) => t.id === id);
        const next = remaining[Math.min(idx, remaining.length - 1)];
        router.push(next.path);
      }
    },
    [tabs, closeTab, router],
  );

  const activate = useCallback(
    (id: string) => {
      const tab = tabs.find((t) => t.id === id);
      if (tab) {
        activateTab(id);
        router.push(tab.path);
      }
    },
    [tabs, activateTab, router],
  );

  return {
    tabs,
    activeTabId,
    open,
    close,
    activate,
    markDirty,
    closeAllTabs,
    closeOtherTabs,
  };
}

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Tab {
  id: string;
  title: string;
  path: string;
  module: string;
  isDirty: boolean;
}

interface TabState {
  tabs: Tab[];
  activeTabId: string | null;
  openTab: (tab: Omit<Tab, "isDirty">) => void;
  closeTab: (id: string) => void;
  activateTab: (id: string) => void;
  markDirty: (id: string, isDirty: boolean) => void;
  closeAllTabs: () => void;
  closeOtherTabs: (id: string) => void;
}

const MAX_TABS = 20;

export const useTabStore = create<TabState>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeTabId: null,

      openTab: (tab) => {
        const { tabs } = get();
        const existing = tabs.find((t) => t.id === tab.id);
        if (existing) {
          set({ activeTabId: tab.id });
          return;
        }

        let newTabs = [...tabs, { ...tab, isDirty: false }];
        // LRU eviction
        if (newTabs.length > MAX_TABS) {
          const cleanTabs = newTabs.filter((t) => !t.isDirty);
          if (cleanTabs.length > 0) {
            newTabs = newTabs.filter((t) => t.id !== cleanTabs[0].id);
          }
        }
        set({ tabs: newTabs, activeTabId: tab.id });
      },

      closeTab: (id) => {
        const { tabs, activeTabId } = get();
        const newTabs = tabs.filter((t) => t.id !== id);
        let newActiveId = activeTabId;
        if (activeTabId === id) {
          const idx = tabs.findIndex((t) => t.id === id);
          newActiveId = newTabs[Math.min(idx, newTabs.length - 1)]?.id ?? null;
        }
        set({ tabs: newTabs, activeTabId: newActiveId });
      },

      activateTab: (id) => set({ activeTabId: id }),

      markDirty: (id, isDirty) =>
        set((state) => ({
          tabs: state.tabs.map((t) => (t.id === id ? { ...t, isDirty } : t)),
        })),

      closeAllTabs: () => set({ tabs: [], activeTabId: null }),

      closeOtherTabs: (id) =>
        set((state) => ({
          tabs: state.tabs.filter((t) => t.id === id),
          activeTabId: id,
        })),
    }),
    {
      name: "lingshu-tabs",
      partialize: (state) => ({
        tabs: state.tabs.map((t) => ({ ...t, isDirty: false })),
        activeTabId: state.activeTabId,
      }),
    },
  ),
);

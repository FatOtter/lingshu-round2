import { create } from "zustand";

interface ShellState {
  isOpen: boolean;
  width: number;
  sessionId: string | null;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setWidth: (width: number) => void;
  setSessionId: (sessionId: string | null) => void;
}

const MIN_WIDTH = 320;
const MAX_WIDTH_RATIO = 0.8;
const DEFAULT_WIDTH = 400;

export const useShellStore = create<ShellState>((set) => ({
  isOpen: false,
  width: DEFAULT_WIDTH,
  sessionId: null,

  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),

  setWidth: (width: number) =>
    set({
      width: Math.max(MIN_WIDTH, Math.min(width, window.innerWidth * MAX_WIDTH_RATIO)),
    }),

  setSessionId: (sessionId: string | null) => set({ sessionId }),
}));

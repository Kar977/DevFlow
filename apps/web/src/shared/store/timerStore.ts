import { create } from "zustand";

type ActiveSession = {
  taskId: string;
  taskTitle: string;
  startedAt: string;
};

type TimerState = {
  activeSession: ActiveSession | null;
  elapsedSeconds: number;
};

type TimerActions = {
  startSession: (session: ActiveSession) => void;
  stopSession: () => void;
};

// Private — not in Zustand state
let _intervalId: ReturnType<typeof setInterval> | null = null;

export const useTimerStore = create<TimerState & TimerActions>((set) => ({
  activeSession: null,
  elapsedSeconds: 0,

  startSession: (session) => {
    if (_intervalId) clearInterval(_intervalId);
    set({ activeSession: session, elapsedSeconds: 0 });
    _intervalId = setInterval(() => {
      set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 }));
    }, 1000);
  },

  stopSession: () => {
    if (_intervalId) { clearInterval(_intervalId); _intervalId = null; }
    set({ activeSession: null, elapsedSeconds: 0 });
  },
}));

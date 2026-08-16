import { create } from "zustand";

type ActiveSession = {
  taskId: string;
  taskTitle: string;
  startedAt: string;
};

type TimerState = {
  activeSession: ActiveSession | null;
  elapsedSeconds: number;
  // Server-configured "forgotten timer" threshold, in seconds, for whichever
  // session is active — null when no session is active or the value hasn't
  // been hydrated yet. See useLongRunningTimer, which is the only reader.
  longRunningThresholdSeconds: number | null;
};

type TimerActions = {
  startSession: (
    session: ActiveSession,
    longRunningThresholdSeconds?: number | null
  ) => void;
  stopSession: () => void;
};

// Private — not in Zustand state
let _intervalId: ReturnType<typeof setInterval> | null = null;

export const useTimerStore = create<TimerState & TimerActions>((set) => ({
  activeSession: null,
  elapsedSeconds: 0,
  longRunningThresholdSeconds: null,

  startSession: (session, longRunningThresholdSeconds = null) => {
    if (_intervalId) clearInterval(_intervalId);
    set({ activeSession: session, elapsedSeconds: 0, longRunningThresholdSeconds });
    _intervalId = setInterval(() => {
      set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 }));
    }, 1000);
  },

  stopSession: () => {
    if (_intervalId) { clearInterval(_intervalId); _intervalId = null; }
    set({ activeSession: null, elapsedSeconds: 0, longRunningThresholdSeconds: null });
  },
}));

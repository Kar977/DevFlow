import { create } from "zustand";

type ActiveSession = {
  taskId: string;
  taskTitle: string;
  startedAt: string;
};

type TimerState = {
  activeSession: ActiveSession | null;
  elapsedSeconds: number;
  _intervalId: ReturnType<typeof setInterval> | null;
};

type TimerActions = {
  startSession: (session: ActiveSession) => void;
  stopSession: () => void;
};

export const useTimerStore = create<TimerState & TimerActions>((set, get) => ({
  activeSession: null,
  elapsedSeconds: 0,
  _intervalId: null,

  startSession: (session) => {
    const existing = get()._intervalId;
    if (existing) clearInterval(existing);

    const intervalId = setInterval(() => {
      set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 }));
    }, 1000);

    set({ activeSession: session, elapsedSeconds: 0, _intervalId: intervalId });
  },

  stopSession: () => {
    const id = get()._intervalId;
    if (id) clearInterval(id);
    set({ activeSession: null, elapsedSeconds: 0, _intervalId: null });
  },
}));

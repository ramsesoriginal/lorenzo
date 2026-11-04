export type TimerState = {
  duration: number;
  remaining: number;
  deadline: number | null;
  started: boolean;
};
const maximum = 1440 * 60_000;
export const freshTimer = (minutes = 25): TimerState => ({
  duration: minutes * 60_000,
  remaining: minutes * 60_000,
  deadline: null,
  started: false,
});
export function remainingTime(state: TimerState, now: number) {
  return state.deadline === null
    ? state.remaining
    : Math.max(0, Math.min(state.duration, state.deadline - now));
}
export function storedTimer(source: string | null): TimerState {
  try {
    const value = JSON.parse(source ?? 'null') as TimerState | null;
    if (
      value &&
      Number.isSafeInteger(value.duration) &&
      value.duration >= 60_000 &&
      value.duration <= maximum &&
      value.duration % 60_000 === 0 &&
      Number.isSafeInteger(value.remaining) &&
      value.remaining >= 0 &&
      value.remaining <= value.duration &&
      typeof value.started === 'boolean' &&
      (value.deadline === null ||
        (value.started && Number.isSafeInteger(value.deadline) && value.deadline > 0))
    )
      return value;
  } catch {
    /* A damaged local timer must not prevent writing. */
  }
  return freshTimer();
}

export function writingTimer(api: string, account: string, tenant: string) {
  const key = `lorenzo:writing-timer:${JSON.stringify([api, account, tenant])}`;
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Writing timer';
  const form = document.createElement('form');
  form.className = 'stack';
  const label = document.createElement('label');
  label.className = 'stack-tight';
  const minutes = document.createElement('input');
  minutes.type = 'number';
  minutes.className = 'text-input';
  minutes.min = '1';
  minutes.max = '1440';
  minutes.step = '1';
  minutes.required = true;
  label.append('Minutes', minutes);
  const clock = document.createElement('p');
  clock.setAttribute('role', 'timer');
  clock.setAttribute('aria-label', 'Time remaining');
  clock.setAttribute('aria-live', 'off');
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const warning = document.createElement('p');
  const help = document.createElement('p');
  help.textContent =
    'A personal timer for this browser tab. It continues while you write or browse this library.';
  const actions = document.createElement('div');
  actions.className = 'row';
  const action = document.createElement('button');
  action.type = 'submit';
  action.className = 'btn btn-primary';
  const reset = document.createElement('button');
  reset.type = 'button';
  reset.className = 'btn';
  reset.textContent = 'Reset timer';
  actions.append(action, reset);
  form.append(label, clock, actions, status, warning, help);
  panel.append(summary, form);
  const unavailable = () => {
    warning.textContent = 'This timer works here, but cannot be restored after reloading this tab.';
  };
  let state = freshTimer();
  try {
    state = storedTimer(sessionStorage.getItem(key));
  } catch {
    unavailable();
  }
  minutes.value = String(state.duration / 60_000);
  if (state.started && state.deadline === null)
    status.textContent = state.remaining ? 'Timer paused.' : 'Time elapsed.';
  const persist = () => {
    try {
      sessionStorage.setItem(key, JSON.stringify(state));
    } catch {
      unavailable();
    }
  };
  const draw = () => {
    const remaining = remainingTime(state, Date.now());
    if (state.deadline !== null && remaining === 0) {
      state = { ...state, deadline: null, remaining: 0 };
      status.textContent = 'Time elapsed.';
      persist();
    }
    const seconds = Math.ceil(remaining / 1000);
    const value = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    if (clock.textContent !== value) clock.textContent = value;
    minutes.disabled = state.started && state.remaining !== 0;
    action.textContent =
      state.deadline !== null
        ? 'Pause timer'
        : state.started && state.remaining > 0
          ? 'Resume timer'
          : 'Start timer';
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (state.deadline !== null) {
      state = { ...state, remaining: remainingTime(state, Date.now()), deadline: null };
      status.textContent = state.remaining ? 'Timer paused.' : 'Time elapsed.';
    } else {
      if (!state.started || state.remaining === 0) {
        if (!form.reportValidity()) return;
        state = freshTimer(Number(minutes.value));
      }
      const resuming = state.started;
      state = { ...state, started: true, deadline: Date.now() + state.remaining };
      status.textContent = resuming ? 'Timer resumed.' : 'Timer started.';
    }
    persist();
    draw();
  });
  reset.addEventListener('click', () => {
    state = freshTimer(state.duration / 60_000);
    minutes.value = String(state.duration / 60_000);
    status.textContent = 'Timer reset.';
    persist();
    draw();
  });
  draw();
  const ticker = setInterval(() => {
    if (!panel.isConnected) {
      clearInterval(ticker);
      return;
    }
    draw();
  }, 1000);
  return panel;
}

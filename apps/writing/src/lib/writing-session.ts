import { countSources } from './manuscript-count';

export type WritingSession = { id: string; target: number; net: number; active: boolean };
export function readSession(source: string | null): WritingSession | null {
  try {
    const state = JSON.parse(source ?? 'null') as WritingSession | null;
    if (
      state &&
      typeof state.id === 'string' &&
      state.id.length > 0 &&
      state.id.length <= 64 &&
      Number.isSafeInteger(state.target) &&
      state.target > 0 &&
      state.target <= 100_000_000 &&
      Number.isSafeInteger(state.net) &&
      typeof state.active === 'boolean'
    )
      return state;
  } catch {
    /* A damaged local goal must not prevent writing. */
  }
  return null;
}

export function writingSession(
  api: string,
  account: string,
  tenant: string,
  sources: () => string[],
) {
  const key = `lorenzo:writing-session:${JSON.stringify([api, account, tenant])}`;
  const element = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Writing session';
  const form = document.createElement('form');
  form.className = 'stack';
  const label = document.createElement('label');
  label.className = 'stack-tight';
  const target = document.createElement('input');
  target.type = 'number';
  target.className = 'text-input';
  target.min = '1';
  target.max = '100000000';
  target.step = '1';
  target.required = true;
  label.append('Session word target', target);
  const progress = document.createElement('p');
  const remaining = document.createElement('p');
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const warning = document.createElement('p');
  const help = document.createElement('p');
  help.textContent =
    'Counts editing in this tab, including unsaved changes. Moving writing or loading a revision adds no words.';
  const start = document.createElement('button');
  start.type = 'submit';
  start.className = 'btn btn-primary';
  const finish = document.createElement('button');
  finish.type = 'button';
  finish.className = 'btn';
  finish.textContent = 'Finish session';
  const actions = document.createElement('div');
  actions.className = 'row';
  actions.append(start, finish);
  form.append(label, progress, remaining, actions, status, warning, help);
  element.append(summary, form);
  const unavailable = () => {
    warning.textContent =
      'Session progress works here, but cannot be restored after reloading this tab.';
  };
  let state: WritingSession | null = null;
  try {
    state = readSession(sessionStorage.getItem(key));
  } catch {
    unavailable();
  }
  target.value = String(state?.target ?? 500);
  let baseline: number | undefined;
  let pending: string[] | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const persist = () => {
    try {
      sessionStorage.setItem(key, JSON.stringify(state));
    } catch {
      unavailable();
    }
  };
  const draw = () => {
    target.disabled = Boolean(state?.active);
    start.disabled = Boolean(state?.active);
    start.textContent = state ? 'Start new session' : 'Start session';
    finish.disabled = !state?.active;
    progress.textContent = state
      ? `Session progress · ${state.net > 0 ? '+' : ''}${state.net} ${Math.abs(state.net) === 1 ? 'word' : 'words'}`
      : 'Start from the draft you have now.';
    remaining.textContent = state
      ? state.net >= state.target
        ? 'Session target reached.'
        : `${state.target - state.net} words to your session target.`
      : '';
  };
  const flush = () => {
    clearTimeout(timer);
    if (!state?.active || !pending) return;
    const count = countSources(pending);
    if (baseline !== undefined) state.net += count - baseline;
    baseline = count;
    pending = undefined;
    persist();
    draw();
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (state?.active || !form.reportValidity()) return;
    baseline = countSources(sources());
    pending = undefined;
    state = { id: crypto.randomUUID(), target: Number(target.value), net: 0, active: true };
    persist();
    draw();
    status.textContent = 'Session started.';
  });
  finish.addEventListener('click', () => {
    flush();
    if (!state) return;
    state.active = false;
    persist();
    draw();
    status.textContent = 'Session finished.';
  });
  window.addEventListener(
    'pagehide',
    () => {
      if (element.isConnected) flush();
    },
    { once: true },
  );
  draw();
  return {
    element,
    rebase() {
      flush();
      baseline = state?.active ? countSources(sources()) : undefined;
    },
    changed() {
      if (!state?.active) return;
      pending = sources();
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (element.isConnected) flush();
      }, 200);
    },
  };
}

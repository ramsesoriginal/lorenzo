import { client, unwrap } from './api';

export type GoalContext = { tenant: string; id: string; scope: 'direct' | 'assembled' };

export function lengthGoal(panel: HTMLDetailsElement, context?: GoalContext) {
  let count = 0;
  if (!context) return (_count: number) => {};
  const path = { tenant_id: context.tenant, id: context.id, scope: context.scope };
  const form = document.createElement('form');
  form.className = 'stack';
  const label = document.createElement('label');
  label.className = 'stack-tight';
  const input = document.createElement('input');
  input.type = 'number';
  input.min = '1';
  input.max = '100000000';
  input.step = '1';
  input.required = true;
  input.className = 'text-input';
  label.append('Personal word target', input);
  const progress = document.createElement('p');
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const save = document.createElement('button');
  save.type = 'submit';
  save.className = 'btn btn-primary';
  save.textContent = 'Save target';
  const clear = document.createElement('button');
  clear.type = 'button';
  clear.className = 'btn';
  clear.textContent = 'Clear target';
  const reload = document.createElement('button');
  reload.type = 'button';
  reload.className = 'btn';
  reload.textContent = 'Reload saved target';
  reload.hidden = true;
  form.append(label, progress, save, clear, status, reload);
  let loaded = false;
  let busy = false;
  let version = 0;
  let target: number | null = null;
  const draw = () => {
    progress.textContent =
      target === null
        ? 'Set a target for yourself.'
        : count >= target
          ? `Target reached Â· ${target} words`
          : `${target - count} words remaining Â· target ${target}`;
    clear.disabled = busy || target === null;
    save.disabled = busy;
    reload.disabled = busy;
    input.disabled = busy;
  };
  const accept = (goal: { target_words: number | null; version: number }) => {
    version = goal.version;
    target = goal.target_words;
    input.value = target === null ? '' : String(target);
    reload.hidden = true;
    loaded = true;
    draw();
  };
  const load = async () => {
    if (busy) return;
    busy = true;
    draw();
    try {
      const result = await client.GET(
        '/tenants/{tenant_id}/writing/entries/{id}/length-goals/{scope}',
        {
          params: { path },
        },
      );
      if (!panel.isConnected) return;
      if ([403, 404].includes(result.response.status)) {
        loaded = true;
        form.remove();
        return;
      }
      accept(await unwrap(result));
      panel.append(form);
      status.textContent = '';
    } catch (error) {
      if (!panel.isConnected) return;
      panel.append(form);
      status.textContent =
        error instanceof Error ? error.message : 'Your target could not be read.';
      reload.hidden = false;
    } finally {
      busy = false;
      draw();
      save.disabled = !loaded;
    }
  };
  const put = async (value: number | null) => {
    if (busy || !loaded) return;
    busy = true;
    draw();
    try {
      const result = await client.PUT(
        '/tenants/{tenant_id}/writing/entries/{id}/length-goals/{scope}',
        {
          params: { path, header: { 'if-match': `"${version}"` } },
          body: { target_words: value },
        },
      );
      if (!panel.isConnected) return;
      if (result.response.status === 412) {
        status.textContent =
          'Your target changed elsewhere. Reload the saved target before trying again.';
        reload.hidden = false;
        return;
      }
      accept(await unwrap(result));
      status.textContent = value === null ? 'Target cleared.' : 'Target saved.';
    } catch (error) {
      if (panel.isConnected)
        status.textContent =
          error instanceof Error ? error.message : 'Your target could not be saved.';
    } finally {
      busy = false;
      draw();
    }
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (form.reportValidity()) void put(Number(input.value));
  });
  clear.addEventListener('click', () => void put(null));
  reload.addEventListener('click', () => void load());
  panel.addEventListener('toggle', () => {
    if (panel.open && !loaded) void load();
  });
  return (value: number) => {
    count = value;
    draw();
  };
}

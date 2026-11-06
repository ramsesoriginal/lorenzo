// The list `?` opens (ADR 0414): the keys, and the switch that turns the single-key ones off.

import { closeDialog, fadeOnDismiss, openDialog } from './dialog';

export type ShortcutsOptions = {
  /** What G then a letter does, with the letters, e.g. { chord: 'G S', name: 'Go to Sessions' }. */
  places(): { chord: string; name: string }[];
  singleKeys(): boolean;
  setSingleKeys(on: boolean): void;
  /** "Ctrl K" or "⌘ K". */
  paletteKeys: string;
};

function row(keys: string, name: string): HTMLElement {
  const line = document.createElement('div');
  const key = document.createElement('kbd');
  const text = document.createElement('span');

  line.className = 'menu-item';
  key.textContent = keys;
  text.className = 'grow';
  text.textContent = name;
  line.append(text, key);

  return line;
}

export function mountShortcuts(options: ShortcutsOptions): { open(): void } {
  const dialog = document.createElement('dialog');
  const title = document.createElement('h2');
  const grip = document.createElement('div');

  dialog.setAttribute('aria-labelledby', 'shell-shortcuts-title');
  grip.className = 'sheet-grip';
  grip.setAttribute('aria-hidden', 'true');
  title.id = 'shell-shortcuts-title';
  title.textContent = 'Keyboard shortcuts';

  const where = document.createElement('div');
  const switchLabel = document.createElement('label');
  const checkbox = document.createElement('input');
  const track = document.createElement('span');
  const switchText = document.createElement('span');
  const close = document.createElement('button');
  const actions = document.createElement('div');

  switchLabel.className = 'row-tight';
  checkbox.type = 'checkbox';
  checkbox.setAttribute('role', 'switch');
  const wrap = document.createElement('span');

  wrap.className = 'switch';
  track.className = 'switch-track';
  wrap.append(checkbox, track);
  switchText.textContent =
    'Single-key shortcuts (G then a letter, ?). Ctrl and Cmd shortcuts always work.';
  switchLabel.append(wrap, switchText);
  checkbox.addEventListener('change', () => options.setSingleKeys(checkbox.checked));

  close.type = 'button';
  close.className = 'btn btn-secondary';
  close.textContent = 'Close';
  close.addEventListener('click', () => closeDialog(dialog));
  actions.className = 'dialog-actions';
  actions.append(close);

  dialog.append(grip, title, where, switchLabel, actions);
  document.body.append(dialog);
  fadeOnDismiss(dialog);

  return {
    open() {
      checkbox.checked = options.singleKeys();
      where.replaceChildren(
        row(options.paletteKeys, 'Search, go to an app, run a command'),
        row('?', 'This list'),
        ...options.places().map((place) => row(place.chord, place.name)),
      );
      openDialog(dialog);
    },
  };
}

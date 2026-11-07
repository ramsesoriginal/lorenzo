// The Appearance dialog (D22, ADR 0416, screen 33): the theme, the density of lists and tables, and
// motion, each a choice of a few that is applied and kept as soon as it is made.

import {
  readDensity,
  readMotion,
  readThemeChoice,
  setDensity,
  setMotion,
  setThemeChoice,
} from './appearance';
import { closeDialog, fadeOnDismiss, openDialog } from './dialog';
import type { Density, Motion, ThemeChoice } from './pure';

type Choice<T extends string> = { value: T; label: string };

const THEMES: Choice<ThemeChoice>[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

const DENSITY_CHOICES: Choice<Density>[] = [
  { value: 'comfortable', label: 'Comfortable' },
  { value: 'compact', label: 'Compact' },
  { value: 'dense', label: 'Dense' },
];

const MOTIONS: Choice<Motion>[] = [
  { value: 'system', label: 'System' },
  { value: 'reduced', label: 'Reduced' },
];

/** On a phone or a coarse pointer every row is at least 44px, so density is not offered (D22). */
function densityOffered(): boolean {
  return !(window.matchMedia?.('(max-width: 720px), (pointer: coarse)').matches ?? false);
}

function text(tag: string, className: string, content: string): HTMLElement {
  const element = document.createElement(tag);

  element.className = className;
  element.textContent = content;

  return element;
}

/** A row of buttons of which one is chosen: radios in a group, moved with the arrows. */
function segmented<T extends string>(
  label: string,
  choices: Choice<T>[],
  current: () => T,
  choose: (value: T) => void,
): HTMLElement {
  const group = document.createElement('div');
  const buttons = new Map<T, HTMLButtonElement>();

  group.className = 'segmented-control';
  group.setAttribute('role', 'radiogroup');
  group.setAttribute('aria-label', label);

  const paint = () => {
    for (const [value, button] of buttons) {
      const on = value === current();

      button.setAttribute('aria-checked', String(on));
      button.tabIndex = on ? 0 : -1;
    }
  };

  for (const choice of choices) {
    const button = document.createElement('button');

    button.type = 'button';
    button.setAttribute('role', 'radio');
    button.textContent = choice.label;
    button.addEventListener('click', () => {
      choose(choice.value);
      paint();
    });
    button.addEventListener('keydown', (event) => {
      const at = choices.findIndex((other) => other.value === choice.value);
      const next =
        event.key === 'ArrowRight' || event.key === 'ArrowDown'
          ? choices[(at + 1) % choices.length]
          : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
            ? choices[(at + choices.length - 1) % choices.length]
            : undefined;

      if (!next) return;

      event.preventDefault();
      choose(next.value);
      paint();
      buttons.get(next.value)?.focus();
    });
    buttons.set(choice.value, button);
    group.append(button);
  }

  group.addEventListener('appearance:paint', paint);
  paint();

  return group;
}

export function mountAppearance(themeKey: string): { open(): void } {
  const dialog = document.createElement('dialog');
  const body = document.createElement('div');
  const done = document.createElement('button');
  const actions = document.createElement('div');
  const grip = document.createElement('div');
  const title = text('h2', '', 'Appearance');

  dialog.setAttribute('aria-labelledby', 'shell-appearance-title');
  dialog.className = 'appearance';
  grip.className = 'sheet-grip';
  grip.setAttribute('aria-hidden', 'true');
  title.id = 'shell-appearance-title';
  body.className = 'stack';
  done.type = 'button';
  done.className = 'btn btn-primary';
  done.textContent = 'Done';
  done.addEventListener('click', () => closeDialog(dialog));
  actions.className = 'dialog-actions';
  actions.append(done);
  dialog.append(grip, title, body, actions);
  document.body.append(dialog);
  fadeOnDismiss(dialog);

  return {
    open() {
      // Built each time it is opened, so what it shows is what is kept now.
      const parts: HTMLElement[] = [
        text('div', 'field-label', 'Theme'),
        segmented(
          'Theme',
          THEMES,
          () => readThemeChoice(themeKey),
          (value) => setThemeChoice(themeKey, value),
        ),
      ];

      if (densityOffered()) {
        parts.push(
          text('div', 'field-label', 'Density of lists and tables'),
          segmented('Density of lists and tables', DENSITY_CHOICES, readDensity, setDensity),
          text(
            'p',
            'caption',
            'The starting point for every list. It changes the height of a row, never the size of the text. Not offered on a phone.',
          ),
        );
      }

      parts.push(
        text('div', 'field-label', 'Motion'),
        segmented('Motion', MOTIONS, readMotion, setMotion),
        text('p', 'caption', 'Remembered on this device.'),
      );
      body.replaceChildren(...parts);
      openDialog(dialog);
    },
  };
}

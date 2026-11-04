// The buttons over a text: formatting (the actions of `@lorenzo/lorenzoscript-editor`) and the
// two that start a link or a picture at the caret. Every button is an atlas icon named for readers
// by its label; a press never takes the focus from the text, or the caret and selection are lost.

import { ACTIONS, type ActionName } from '@lorenzo/lorenzoscript-editor';
import { openLink } from './entryPickerText';
import { type IconName, iconButton } from './icons';

/** The formatting actions Bench offers, with the icon each is drawn as. */
const FORMATS: readonly [ActionName, IconName][] = [
  ['bold', 'bold'],
  ['italic', 'italic'],
  ['heading', 'heading'],
  ['quote', 'quote'],
  ['bullets', 'list'],
  ['numbers', 'list-numbered'],
  ['code', 'code'],
];

/**
 * The toolbar for a text. `target` gives the textarea to act on, making one active first if the
 * text is drawn as blocks and none is being written.
 */
export function textToolbar(target: () => HTMLTextAreaElement | null): HTMLElement {
  const bar = document.createElement('div');
  bar.className = 'text-toolbar';
  bar.setAttribute('role', 'toolbar');
  bar.setAttribute('aria-label', 'Insert');
  const add = (b: HTMLButtonElement, act: (area: HTMLTextAreaElement) => void) => {
    b.addEventListener('click', () => {
      const area = target();
      if (!area) return;
      act(area);
      area.focus();
      // The picker and the preview follow what is typed.
      area.dispatchEvent(new Event('input'));
    });
    b.addEventListener('mousedown', (ev) => ev.preventDefault());
    bar.append(b);
  };
  for (const [name, glyph] of FORMATS) {
    const action = ACTIONS[name];
    add(
      iconButton(glyph, action.title, () => {}, 'btn quiet'),
      (area) => {
        const next = action.run({
          text: area.value,
          start: area.selectionStart,
          end: area.selectionEnd,
        });
        area.value = next.text;
        area.setSelectionRange(next.start, next.end);
      },
    );
  }
  for (const [label, glyph, image] of [
    ['Link to an entry', 'entity-link', false],
    ['Show a picture', 'picture', true],
  ] as const) {
    add(
      iconButton(glyph, label, () => {}, 'btn quiet'),
      (area) => {
        const made = openLink(area.value, area.selectionStart, area.selectionEnd, image);
        area.value = made.text;
        area.setSelectionRange(made.caret, made.caret);
      },
    );
  }
  return bar;
}

// The entry picker: typing `[[` in a text offers the entries by name, and choosing one writes the
// link. It is a list under the field (not at the caret: a textarea does not say where that is),
// driven from the keyboard without leaving the text: arrows move, Enter or Tab choose, Escape closes.

import type { Bench } from '../core/bench';
import { applyPick, choices, type PickerContext, pickerContext } from './entryPickerText';

// One list for the page, like the link card: the editors are drawn again when things change.
let list: HTMLElement | null = null;

export function hidePicker() {
  list?.remove();
  list = null;
}

export function attachEntryPicker(area: HTMLTextAreaElement, bench: Bench): void {
  let context: PickerContext | null = null;
  let offered: ReturnType<typeof choices> = [];
  let on = 0;

  const pick = (index: number) => {
    const entry = offered[index];
    const here = context;
    if (!entry || !here) return;
    const made = applyPick(area.value, area.selectionStart, here, entry.name);
    area.value = made.text;
    area.setSelectionRange(made.caret, made.caret);
    hidePicker();
    context = null;
    area.dispatchEvent(new Event('input')); // the preview follows what is typed
  };

  const draw = () => {
    if (!context || !offered.length) {
      hidePicker();
      return;
    }
    hidePicker();
    list = document.createElement('ul');
    list.className = 'entry-picker';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', 'Entries to link');
    offered.forEach((entry, i) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(i === on));
      if (i === on) li.className = 'on';
      li.textContent = entry.name;
      // Pressing must not take the focus from the text.
      li.addEventListener('mousedown', (ev) => ev.preventDefault());
      li.addEventListener('click', () => pick(i));
      list?.append(li);
    });
    document.body.append(list);
    const at = area.getBoundingClientRect();
    list.style.left = `${at.left}px`;
    list.style.top = `${at.bottom + 2}px`;
    list.style.minWidth = `${Math.min(at.width, 320)}px`;
  };

  const update = () => {
    context = pickerContext(area.value, area.selectionStart);
    offered = context ? choices(bench.listing(), context.query) : [];
    on = 0;
    draw();
  };

  area.addEventListener('input', update);
  area.addEventListener('click', update);
  area.addEventListener('blur', hidePicker);
  area.addEventListener('keydown', (ev) => {
    if (!list) return;
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      on = (on + (ev.key === 'ArrowDown' ? 1 : offered.length - 1)) % offered.length;
      draw();
    } else if (ev.key === 'Enter' || ev.key === 'Tab') {
      ev.preventDefault();
      pick(on);
    } else if (ev.key === 'Escape') {
      ev.preventDefault();
      ev.stopPropagation();
      hidePicker();
    }
  });
  // Moving the caret with the arrows changes where the person is in the text.
  area.addEventListener('keyup', (ev) => {
    if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight' || ev.key === 'Home' || ev.key === 'End')
      update();
  });
}

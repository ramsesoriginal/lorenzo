// A text field that offers suggestions as you type: it waits for a pause in the typing, asks
// `search`, lists what comes back, and hands the picked one to `onPick`. Escape and a click
// elsewhere close the list.
import { cloneTemplate, requiredIn } from '../../lib/template';

export type Suggestion<T> = { label: string; value: T };

export type ComboboxOptions<T> = {
  search(query: string): Promise<Suggestion<T>[]>;
  // The list closes after this; the field keeps what was typed unless this changes it.
  onPick(value: T): void;
  // How long a pause in typing is, 200 ms unless given.
  delayMs?: number;
  // Ends the field's listeners with its owner's.
  signal?: AbortSignal;
};

export type RenderedCombobox = {
  input: HTMLInputElement;
  close(): void;
};

const required = requiredIn('Combobox');

let lists = 0;

// `root` is the <Combobox /> field, or whatever contains one.
export function renderCombobox<T>(
  root: HTMLElement,
  options: ComboboxOptions<T>,
): RenderedCombobox {
  const box = root.matches('[data-combobox]')
    ? root
    : required<HTMLElement>(root, '[data-combobox]');
  const input = required<HTMLInputElement>(box, '[data-input]');
  const list = required<HTMLUListElement>(box, '[data-suggestions]');
  const template = required<HTMLTemplateElement>(box, '[data-suggestion-template]');

  // Without an owner's signal the field ends its own listeners when it leaves the page.
  const controller = new AbortController();
  const signal = options.signal ?? controller.signal;

  list.id = `combobox-suggestions-${++lists}`;
  input.setAttribute('aria-controls', list.id);

  let timer: ReturnType<typeof setTimeout> | undefined;
  // Only the newest search paints, so a slow answer can't replace a newer one.
  let latest = 0;

  function close() {
    latest++;
    clearTimeout(timer);
    list.hidden = true;
    list.replaceChildren();
    input.setAttribute('aria-expanded', 'false');
  }

  function open(found: Suggestion<T>[]) {
    list.replaceChildren(
      ...found.map((suggestion) => {
        const item = cloneTemplate<HTMLLIElement>(template, 'li');
        const button = required<HTMLButtonElement>(item, '[data-select]');

        button.textContent = suggestion.label;
        button.addEventListener('click', () => {
          options.onPick(suggestion.value);
          close();
        });

        return item;
      }),
    );
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }

  signal.addEventListener(
    'abort',
    () => {
      latest++;
      clearTimeout(timer);
    },
    { once: true },
  );

  input.addEventListener(
    'input',
    () => {
      clearTimeout(timer);

      const query = input.value.trim();

      if (!query) {
        close();
        return;
      }

      timer = setTimeout(async () => {
        const turn = ++latest;

        try {
          const found = await options.search(query);

          if (turn !== latest) return;

          if (found.length === 0) {
            close();
          } else {
            open(found);
          }
        } catch {
          if (turn === latest) close();
        }
      }, options.delayMs ?? 200);
    },
    { signal },
  );

  input.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape') close();
    },
    { signal },
  );

  document.addEventListener(
    'click',
    (event) => {
      if (!box.isConnected) {
        controller.abort();
      } else if (!box.contains(event.target as Node)) {
        close();
      }
    },
    { signal },
  );

  return { input, close };
}

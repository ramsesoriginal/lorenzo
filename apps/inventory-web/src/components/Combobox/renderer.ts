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
  // Asks `search('')` when the field is focused or clicked while empty, to offer something to
  // pick from before anything is typed: for a list too long to know the names of.
  browseOnFocus?: boolean;
  // What the list says when a search finds nothing, instead of closing: given what was typed.
  emptyMessage?(query: string): string;
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

  function tell(message: string) {
    const note = document.createElement('li');

    note.className = 'combobox-suggestion combobox-empty';
    note.setAttribute('role', 'presentation');
    note.textContent = message;
    list.replaceChildren(note);
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
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

  // Asks, and paints the answer unless a newer question has been asked since.
  async function ask(query: string) {
    const turn = ++latest;

    try {
      const found = await options.search(query);

      if (turn !== latest) return;

      if (found.length > 0) {
        open(found);
      } else if (options.emptyMessage) {
        tell(options.emptyMessage(query));
      } else {
        close();
      }
    } catch {
      if (turn === latest) close();
    }
  }

  input.addEventListener(
    'input',
    () => {
      clearTimeout(timer);

      const query = input.value.trim();

      if (!query) {
        if (options.browseOnFocus) {
          void ask('');
        } else {
          close();
        }
        return;
      }

      timer = setTimeout(() => void ask(query), options.delayMs ?? 200);
    },
    { signal },
  );

  if (options.browseOnFocus) {
    // Focusing the field, or clicking it once it has focus, offers the first few.
    const browse = () => {
      if (!input.value.trim() && list.hidden) void ask('');
    };

    input.addEventListener('focus', browse, { signal });
    input.addEventListener('click', browse, { signal });
  }

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

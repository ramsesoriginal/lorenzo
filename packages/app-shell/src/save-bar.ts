// The explicit save bar (ADR 0412): for a form whose effects cannot be undone. It opens only when
// there is something to save and says how many changes. It rewrites its buttons only when the
// number of changes changes, never on every edit, or a click on Save that follows an edit can be
// lost (found while building the prototypes).

const SVG = 'http://www.w3.org/2000/svg';

export type SaveBarHandlers = {
  /** Save everything. A rejection leaves the changes where they are. */
  save(): void | Promise<void>;
  discard(): void;
  /** Called when saving fails, to say so; the changes are kept. */
  onError?(error: unknown): void;
};

export type SaveBar = {
  /** The number of changes not saved; 0 closes the bar. */
  set(count: number): void;
  count(): number;
};

/** "1 change not saved", "3 changes not saved". */
export function changesText(count: number): string {
  return `${count} ${count === 1 ? 'change' : 'changes'} not saved`;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string) {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;

  return node;
}

export function createSaveBar(
  host: HTMLElement,
  sprite: string,
  handlers: SaveBarHandlers,
): SaveBar {
  let count = 0;
  let drawn = 0;
  let saving = false;

  function draw() {
    const inner = el('div', 'save-bar-in');
    const mark = document.createElementNS(SVG, 'svg');
    const use = document.createElementNS(SVG, 'use');
    const discard = el('button', 'btn btn-secondary', 'Discard');
    const save = el('button', 'btn btn-primary', 'Save changes');

    inner.setAttribute('role', 'region');
    inner.setAttribute('aria-label', 'Unsaved changes');
    mark.setAttribute('class', 'icon');
    mark.setAttribute('aria-hidden', 'true');
    use.setAttribute('href', `${sprite}#icon-pending`);
    mark.append(use);
    discard.type = 'button';
    save.type = 'button';
    discard.addEventListener('click', () => {
      if (!saving) handlers.discard();
    });
    save.addEventListener('click', async () => {
      if (saving) return;
      saving = true;
      save.setAttribute('aria-disabled', 'true');
      save.textContent = 'Saving…';
      try {
        await handlers.save();
      } catch (error) {
        handlers.onError?.(error);
      } finally {
        saving = false;
        save.removeAttribute('aria-disabled');
        save.textContent = 'Save changes';
      }
    });

    const text = el('span', 'grow', changesText(count));

    text.dataset.shellSavebarText = '';
    inner.append(mark, text, discard, save);
    host.replaceChildren(el('div'));
    host.firstElementChild?.append(inner);
  }

  return {
    set(next) {
      count = Math.max(0, Math.floor(next));
      if (count === 0) {
        host.removeAttribute('data-open');
        drawn = 0;

        return;
      }
      host.setAttribute('data-open', '');
      // The same number: the buttons stay. A different one: draw again, with the new words.
      if (count !== drawn) {
        drawn = count;
        draw();
      }
    },
    count: () => count,
  };
}

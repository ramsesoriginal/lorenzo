// A person's saved views of a list (ADR 0532): a name for what the filters were set to, kept in the
// account, so the list can be set the same way again. The page says what its filters are
// (`current`) and how to set them (`apply`); this draws the choice and the saving. Nothing here
// knows the list or the API: the store is given.

/** A view as the store keeps it. */
export type ViewRecord = { id: string; name: string; query: Record<string, unknown> };

/** Where the views are kept; `savedViewStore` in `@lorenzo/api-client` is the usual one. */
export type ViewStore = {
  list(): Promise<ViewRecord[]>;
  save(name: string, query: Record<string, unknown>): Promise<ViewRecord>;
  remove(id: string): Promise<void>;
};

export type SavedViewsOptions = {
  store: ViewStore;
  /** What the filters are now, as the page can set them again. */
  current(): Record<string, unknown>;
  /** Sets the filters to a saved view and shows the list for it. */
  apply(query: Record<string, unknown>): void;
  /** Said when something was saved, removed or went wrong. */
  say?(text: string, failed?: boolean): void;
};

/** Whether a name can be kept: something besides spaces, and not longer than a name may be. */
export function viewNameOf(raw: string): string | null {
  const name = raw.trim().replace(/\s+/g, ' ');

  return name.length > 0 && name.length <= 80 ? name : null;
}

function node<K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text = '') {
  const made = document.createElement(tag);

  if (className) made.className = className;
  if (text) made.textContent = text;

  return made;
}

/** The control: a choice of the views, "Save this view…", and "Delete" for the one chosen. */
export function mountSavedViews(options: SavedViewsOptions): {
  element: HTMLElement;
  refresh(): Promise<void>;
} {
  const root = node('div', 'row saved-views');
  const label = node('label', 'field-inline');
  const choice = node('select', 'text-input');
  const save = node('button', 'btn btn-secondary', 'Save this view…');
  const remove = node('button', 'btn btn-secondary', 'Delete this view');
  const naming = node('form', 'row saved-views-name');
  const name = node('input', 'text-input');
  const confirm = node('button', 'btn btn-primary', 'Save');
  const cancel = node('button', 'btn btn-secondary', 'Cancel');
  const say = options.say ?? (() => {});
  let views: ViewRecord[] = [];

  label.append(node('span', 'field-label', 'Saved views'), choice);
  choice.setAttribute('aria-label', 'Saved views');
  save.type = 'button';
  remove.type = 'button';
  remove.hidden = true;
  cancel.type = 'button';
  name.type = 'text';
  name.maxLength = 80;
  name.setAttribute('aria-label', 'Name of the view');
  name.placeholder = 'A name for this view';
  naming.hidden = true;
  naming.append(name, confirm, cancel);
  root.append(label, save, remove, naming);

  const paint = (chosen = '') => {
    const none = document.createElement('option');

    none.value = '';
    none.textContent = views.length > 0 ? 'Choose a view…' : 'None saved yet';
    choice.replaceChildren(
      none,
      ...views.map((view) => {
        const option = document.createElement('option');

        option.value = view.id;
        option.textContent = view.name;
        return option;
      }),
    );
    choice.value = views.some((view) => view.id === chosen) ? chosen : '';
    remove.hidden = choice.value === '';
  };

  async function refresh() {
    try {
      views = await options.store.list();
    } catch {
      views = [];
    }
    paint(choice.value);
  }

  choice.addEventListener('change', () => {
    remove.hidden = choice.value === '';

    const view = views.find((candidate) => candidate.id === choice.value);

    if (view) options.apply(view.query);
  });
  save.addEventListener('click', () => {
    naming.hidden = false;
    name.value = views.find((view) => view.id === choice.value)?.name ?? '';
    name.focus();
  });
  cancel.addEventListener('click', () => {
    naming.hidden = true;
  });
  naming.addEventListener('submit', (event) => {
    event.preventDefault();

    const wanted = viewNameOf(name.value);

    if (!wanted) {
      say('Give the view a name.', true);
      return;
    }

    void (async () => {
      try {
        const kept = await options.store.save(wanted, options.current());

        views = [...views.filter((view) => view.id !== kept.id), kept].sort((a, b) =>
          a.name.localeCompare(b.name),
        );
        naming.hidden = true;
        paint(kept.id);
        say(`Saved the view “${kept.name}”.`);
      } catch {
        say('Could not save the view. Try again.', true);
      }
    })();
  });
  remove.addEventListener('click', () => {
    const view = views.find((candidate) => candidate.id === choice.value);

    if (!view) return;

    void (async () => {
      try {
        await options.store.remove(view.id);
        views = views.filter((candidate) => candidate.id !== view.id);
        paint();
        say(`Deleted the view “${view.name}”.`);
      } catch {
        say('Could not delete the view. Try again.', true);
      }
    })();
  });

  return { element: root, refresh };
}

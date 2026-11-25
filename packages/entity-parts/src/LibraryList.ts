// The libraries someone can open, each linking to where the app starts in it. With only one there's
// nowhere to choose, so it opens that one.
import type { components } from '@lorenzo/api-client';
import { errorMessage } from './internal/errorMessage';
import { say } from './internal/statusLine';
import { cloneTemplate, requiredIn } from './internal/template';

type TenantSummary = components['schemas']['TenantSummaryOut'];

export type LibraryListDeps = {
  // The libraries the viewer can open.
  list(): Promise<{ items: TenantSummary[] }>;
  // Remembers the one library there is, so the header links there already.
  remember(tenantId: string): void;
  // Where the app starts in a library.
  href(tenantId: string): string;
};

export type RenderedLibraryList = {
  load(): Promise<void>;
};

const required = requiredIn('Library list');

export function renderLibraryList(deps: LibraryListDeps, root: HTMLElement): RenderedLibraryList {
  const loading = required<HTMLElement>(root, '[data-loading]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-library-template]');

  function renderLibrary(library: TenantSummary): HTMLLIElement {
    const item = cloneTemplate<HTMLLIElement>(template, 'li');
    const kind = required<HTMLElement>(item, '[data-kind]');

    required<HTMLAnchorElement>(item, '[data-link]').href = deps.href(library.id);
    required<HTMLElement>(item, '[data-name]').textContent = library.name;
    required<HTMLElement>(item, '[data-role]').textContent = library.role;

    if (library.kind !== 'play') {
      kind.classList.add('pill-warning');
      kind.textContent = library.kind;
      kind.hidden = false;
    }

    return item;
  }

  return {
    async load() {
      root.hidden = false;

      try {
        const { items } = await deps.list();

        loading.hidden = true;

        if (items.length === 0) {
          empty.hidden = false;

          return;
        }

        // Only one place to go - remember it, so the header links there already.
        const [only] = items;

        if (items.length === 1 && only) {
          deps.remember(only.id);
          window.location.href = deps.href(only.id);

          return;
        }

        list.append(...items.map(renderLibrary));
      } catch (cause) {
        loading.hidden = true;
        say(error, errorMessage(cause), true);
      }
    },
  };
}

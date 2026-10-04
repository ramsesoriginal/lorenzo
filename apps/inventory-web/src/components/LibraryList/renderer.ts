// The libraries someone can open, each linking to its board. With only one there's nowhere to
// choose, so it opens that one.

import { errorMessage } from '../../lib/errorMessage';
import { rememberTenant } from '../../lib/lastTenant';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import { listTenants } from '../../lib/tenants';
import type { TenantSummary } from '../../lib/types';

export type RenderedLibraryList = {
  load(): Promise<void>;
};

const required = requiredIn('Library list');

export function renderLibraryList(root: HTMLElement): RenderedLibraryList {
  const loading = required<HTMLElement>(root, '[data-loading]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const error = required<HTMLElement>(root, '[data-error]');
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-library-template]');

  function renderLibrary(library: TenantSummary): HTMLLIElement {
    const item = cloneTemplate<HTMLLIElement>(template, 'li');
    const kind = required<HTMLElement>(item, '[data-kind]');

    required<HTMLAnchorElement>(item, '[data-link]').href = `/board/?tenant=${library.id}`;
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
        const { items } = await listTenants();

        loading.hidden = true;

        if (items.length === 0) {
          empty.hidden = false;

          return;
        }

        // Only one place to go - remember it, so the header links there already.
        if (items.length === 1) {
          rememberTenant(items[0].id);
          window.location.href = `/board/?tenant=${items[0].id}`;

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

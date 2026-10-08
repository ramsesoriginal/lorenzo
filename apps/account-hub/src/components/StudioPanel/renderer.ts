// /studio (ADR 0202): the repositories someone works on, and whichever one is open beside the list.
// What is open is in the address (`?repository=` a link name or id, or `?new=1` for the form that
// makes one), so a link, Back and a reload all land where they were. Only the open one is loaded.

import { onCacheRefreshed } from '../../lib/cache';
import { isEditingIn } from '../../lib/editing';
import { sayError } from '../../lib/statusLine';
import { CREATE_NOT_OPEN, readStudioLocation, STUDIO_NEW_HREF, studioHref } from '../../lib/studio';
import { cloneRoot, requiredIn } from '../../lib/template';
import { canCreateTenants, isRepository } from '../../lib/tenantKind';
import { listMyTenants } from '../../lib/tenants';
import type { MeOut, TenantOut, TenantSummaryOut } from '../../lib/types';
import { renderCreateTenant } from '../CreateTenant/renderer';
import { renderRepository } from '../Repository/renderer';

type View =
  | { type: 'repository'; repository: TenantSummaryOut }
  | { type: 'new' }
  | { type: 'empty' };

const required = requiredIn('Studio panel');

function keyOf(view: View): string {
  return view.type === 'repository' ? `repository:${view.repository.id}` : view.type;
}

// `root` is the <StudioPanel /> block; it shows itself once the list is built.
export async function renderStudioPanel(root: HTMLElement, me: MeOut): Promise<void> {
  const list = required<HTMLElement>(root, '[data-list]');
  const createUnavailable = required<HTMLElement>(root, '[data-create-unavailable]');
  const error = required<HTMLElement>(root, '[data-error]');
  const createView = required<HTMLElement>(root, '[data-create]');
  const emptyView = required<HTMLElement>(root, '[data-empty]');

  const mayCreate = canCreateTenants(me);
  const links = new Map<string, HTMLAnchorElement>();

  let repositories: TenantSummaryOut[] = [];
  let current: View = { type: 'empty' };

  const repositoryRoot = required<HTMLElement>(root, '[data-repository]');
  const repositoryView = renderRepository(repositoryRoot, me.id, {
    onChanged: () => void reload(),
    onRenamed,
  });

  function urlFor(view: View): string {
    if (view.type === 'repository') return studioHref(view.repository.slug);
    if (view.type === 'new') return STUDIO_NEW_HREF;

    return studioHref();
  }

  // What the address asks for, if that exists for this person.
  function viewFromUrl(): View | null {
    const { repository: wanted, create } = readStudioLocation(window.location.search);
    const repository = wanted
      ? repositories.find((r) => r.slug === wanted || r.id === wanted)
      : undefined;

    if (repository) return { type: 'repository', repository };
    if (create && mayCreate) return { type: 'new' };

    return null;
  }

  // The first repository, else somewhere to start.
  function defaultView(): View {
    const first = repositories[0];

    if (first) return { type: 'repository', repository: first };

    return mayCreate ? { type: 'new' } : { type: 'empty' };
  }

  function markSelected(): void {
    for (const [key, link] of links) {
      if (key === keyOf(current)) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  }

  function renderItem(view: View, label: string | null): HTMLElement {
    const item = cloneRoot(root, label === null ? '[data-new-template]' : '[data-item-template]');
    const link = required<HTMLAnchorElement>(item, '[data-link]');

    if (label !== null) link.textContent = label;

    link.href = urlFor(view);
    link.addEventListener('click', (event) => {
      // A modified click is the browser's: a new tab, a new window.
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }

      event.preventDefault();
      navigate(view);
    });
    links.set(keyOf(view), link);

    return item;
  }

  function buildList(): void {
    links.clear();
    list.replaceChildren(
      ...repositories.map((repository) =>
        renderItem({ type: 'repository', repository }, repository.name),
      ),
      ...(mayCreate ? [renderItem({ type: 'new' }, null)] : []),
    );
    markSelected();
  }

  async function refresh(): Promise<void> {
    repositories = (await listMyTenants()).items
      .filter(isRepository)
      .sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }));
    buildList();
  }

  async function show(view: View): Promise<void> {
    current = view;
    markSelected();
    error.hidden = true;
    createView.hidden = view.type !== 'new';
    emptyView.hidden = view.type !== 'empty';

    if (view.type !== 'repository') repositoryView.hide();

    if (view.type === 'new') {
      const form = cloneRoot(root, '[data-create-template]') as HTMLFormElement;

      renderCreateTenant(form, 'repository', (created) => void openCreated(created));
      createView.replaceChildren(form);
    }

    if (view.type === 'repository') await repositoryView.show(view.repository);
  }

  function navigate(view: View): void {
    window.history.pushState(null, '', urlFor(view));
    void show(view);
  }

  // The open repository again with what is loaded now, or somewhere else if it is gone (one just
  // left).
  async function reload(): Promise<void> {
    try {
      const openId = current.type === 'repository' ? current.repository.id : null;

      await refresh();

      const open = openId ? repositories.find((r) => r.id === openId) : undefined;
      const next: View = open
        ? { type: 'repository', repository: open }
        : current.type === 'new' && mayCreate
          ? current
          : (viewFromUrl() ?? defaultView());

      window.history.replaceState(null, '', urlFor(next));
      await show(next);
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // What was just made, open: on its Overview, where a new repository starts.
  async function openCreated(created: TenantOut): Promise<void> {
    try {
      await refresh();

      const repository = repositories.find((r) => r.id === created.id);

      if (repository) navigate({ type: 'repository', repository });
      else await show(defaultView());
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // A saved name or link name: the list and the address follow, without loading anything again.
  function onRenamed(updated: TenantOut): void {
    const repository = repositories.find((r) => r.id === updated.id);

    if (!repository) return;

    repository.name = updated.name;
    repository.slug = updated.slug;

    if (current.type === 'repository' && current.repository.id === repository.id) {
      current = { type: 'repository', repository };
    }

    buildList();
    window.history.replaceState(null, '', urlFor(current));
  }

  createUnavailable.textContent = CREATE_NOT_OPEN;
  createUnavailable.hidden = mayCreate;

  await refresh();

  // The list came from the cache and the API has something different. Where the open one is
  // among them it is drawn again as well, unless someone is typing in it.
  onCacheRefreshed(() => {
    void refresh()
      .then(() => {
        const open = current.type === 'repository' ? current.repository.id : null;
        const repository = repositories.find((r) => r.id === open);

        if (!repository || isEditingIn(repositoryRoot)) return;

        current = { type: 'repository', repository };
        void repositoryView.show(repository);
      })
      .catch(() => {});
  });

  const first = viewFromUrl() ?? defaultView();

  window.history.replaceState(null, '', urlFor(first));
  root.hidden = false;
  window.addEventListener('popstate', () => void show(viewFromUrl() ?? defaultView()));

  // Not waited for: the list is already there while the open one loads.
  void show(first);
}

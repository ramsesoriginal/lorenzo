// /tenants: a tree of the libraries someone belongs to, and whichever one is open beside it. What
// is open is in the address (`?tenant=` a slug, or `?new=library` for the create form), so a link,
// Back and a reload all land where they were. Only the open one is loaded. A repository is run in
// Studio (ADR 0202), so an address that names one, or asks to make one, goes there.

import { onCacheRefreshed } from '../../lib/cache';
import { isEditingIn } from '../../lib/editing';
import { sayError } from '../../lib/statusLine';
import { STUDIO_NEW_HREF, studioHref } from '../../lib/studio';
import { cloneRoot, fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { canCreateTenants, isRepository, type TenantKind } from '../../lib/tenantKind';
import { listMyTenants } from '../../lib/tenants';
import type { MeOut, TenantOut, TenantSummaryOut } from '../../lib/types';
import { renderCreateTenant } from '../CreateTenant/renderer';
import { renderTenant } from '../Tenant/renderer';

type View =
  | { type: 'tenant'; tenant: TenantSummaryOut }
  | { type: 'new'; tenantKind: TenantKind }
  | { type: 'empty' };

const required = requiredIn('Tenants panel');

function keyOf(view: View): string {
  switch (view.type) {
    case 'tenant':
      return `tenant:${view.tenant.id}`;
    case 'new':
      return `new:${view.tenantKind}`;
    case 'empty':
      return 'empty';
  }
}

// `root` is the <TenantsPanel /> block; it shows itself once the tree is built.
export async function renderTenantsPanel(root: HTMLElement, me: MeOut): Promise<void> {
  const librariesGroup = required<HTMLElement>(root, '[data-libraries-group]');
  const librariesList = required<HTMLElement>(root, '[data-libraries]');
  const librariesDetails = required<HTMLDetailsElement>(root, '[data-libraries-details]');
  const createUnavailable = required<HTMLElement>(root, '[data-create-unavailable]');
  const error = required<HTMLElement>(root, '[data-error]');
  const createView = required<HTMLElement>(root, '[data-create]');
  const emptyView = required<HTMLElement>(root, '[data-empty]');
  const setup = required<HTMLElement>(root, '[data-setup]');

  const mayCreate = canCreateTenants(me);
  const links = new Map<string, HTMLAnchorElement>();

  let tenants: TenantSummaryOut[] = [];
  // The repositories, only to send an address that names one to Studio.
  let repositories: TenantSummaryOut[] = [];
  let current: View = { type: 'empty' };

  const tenantRoot = required<HTMLElement>(root, '[data-tenant]');
  const tenantView = renderTenant(tenantRoot, me, {
    onChanged: () => void reload(),
    onRenamed,
  });

  function urlFor(view: View): string {
    const params = new URLSearchParams();

    if (view.type === 'tenant') params.set('tenant', view.tenant.slug);
    if (view.type === 'new') {
      params.set('new', 'library');
    }

    const query = params.toString();

    return query ? `${window.location.pathname}?${query}` : window.location.pathname;
  }

  // What the address asks for, if that exists for this person: a slug or an id.
  function viewFromUrl(): View | null {
    const params = new URLSearchParams(window.location.search);
    const wanted = params.get('tenant');
    const tenant = wanted ? tenants.find((t) => t.slug === wanted || t.id === wanted) : undefined;

    if (tenant) return { type: 'tenant', tenant };

    // A repository is run in Studio (ADR 0202): an address that names one, or asks to make one,
    // goes there.
    const repository = wanted
      ? repositories.find((r) => r.slug === wanted || r.id === wanted)
      : undefined;
    const make = params.get('new');

    if (repository) window.location.replace(studioHref(repository.slug));
    else if (mayCreate && make === 'repository') window.location.replace(STUDIO_NEW_HREF);

    if (mayCreate && make === 'library') return { type: 'new', tenantKind: 'play' };

    return null;
  }

  // The first library, else somewhere to start.
  function defaultView(): View {
    const first = tenants[0];

    if (first) return { type: 'tenant', tenant: first };

    return mayCreate ? { type: 'new', tenantKind: 'play' } : { type: 'empty' };
  }

  function markSelected() {
    for (const [key, link] of links) {
      if (key === keyOf(current)) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    }
  }

  function renderItem(view: View, label: string, isNew: boolean): HTMLElement {
    const item = rootElement(
      fromTemplate(root, isNew ? '[data-new-template]' : '[data-item-template]'),
    );
    const link = required<HTMLAnchorElement>(item, '[data-link]');

    if (isNew) {
      required<HTMLElement>(item, '[data-label]').textContent = label;
    } else {
      link.textContent = label;
    }

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

  function buildTree() {
    links.clear();
    librariesList.replaceChildren(
      ...tenants.map((tenant) => renderItem({ type: 'tenant', tenant }, tenant.name, false)),
      ...(mayCreate ? [renderItem({ type: 'new', tenantKind: 'play' }, 'New library', true)] : []),
    );
    librariesGroup.hidden = tenants.length === 0 && !mayCreate;
    markSelected();
  }

  async function refresh() {
    const all = (await listMyTenants()).items;

    tenants = all.filter((tenant) => !isRepository(tenant));
    repositories = all.filter(isRepository);
    buildTree();
  }

  // Opens the group of libraries once one is selected.
  function openGroupOf(view: View) {
    if (view.type !== 'empty') librariesDetails.open = true;
  }

  async function show(view: View) {
    // Only a change of selection opens a group, so reloading the open tenant after an edit does not
    // reopen one that was closed on purpose.
    if (keyOf(view) !== keyOf(current)) openGroupOf(view);

    current = view;
    markSelected();
    error.hidden = true;
    createView.hidden = view.type !== 'new';
    emptyView.hidden = view.type !== 'empty';
    setup.hidden = !mayCreate;

    if (view.type !== 'tenant') tenantView.hide();

    if (view.type === 'new') {
      const form = cloneRoot(root, '[data-create-template]') as HTMLFormElement;

      renderCreateTenant(form, view.tenantKind, (created) => void openCreated(created));
      createView.replaceChildren(form);
    }

    if (view.type === 'tenant') await tenantView.show(view.tenant);
  }

  function navigate(view: View) {
    window.history.pushState(null, '', urlFor(view));
    void show(view);
  }

  // The open view again with what is loaded now, or somewhere else if it's gone (a library
  // that was just left).
  async function reload() {
    try {
      const openId = current.type === 'tenant' ? current.tenant.id : null;

      await refresh();
      const open = openId ? tenants.find((t) => t.id === openId) : undefined;
      const next: View = open
        ? { type: 'tenant', tenant: open }
        : current.type === 'new' && mayCreate
          ? current
          : (viewFromUrl() ?? defaultView());

      window.history.replaceState(null, '', urlFor(next));
      await show(next);
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // What was just made, open.
  async function openCreated(created: TenantOut) {
    try {
      await refresh();

      const tenant = tenants.find((t) => t.id === created.id);

      if (tenant) {
        navigate({ type: 'tenant', tenant });
      } else {
        await show(defaultView());
      }
    } catch (cause) {
      sayError(error, cause);
    }
  }

  // A saved name or slug: the tree and the address follow, without loading anything again.
  function onRenamed(updated: TenantOut) {
    const tenant = tenants.find((t) => t.id === updated.id);

    if (!tenant) return;

    tenant.name = updated.name;
    tenant.slug = updated.slug;

    if (current.type === 'tenant' && current.tenant.id === tenant.id) {
      current = { type: 'tenant', tenant };
    }

    buildTree();
    window.history.replaceState(null, '', urlFor(current));
  }

  createUnavailable.hidden = mayCreate;

  await refresh();

  // What the tree shows came from the cache, and the API has something different.
  // Where the open library is one of them, it is drawn again as well, unless someone is typing in it.
  onCacheRefreshed(() => {
    void refresh()
      .then(() => {
        const open = current.type === 'tenant' ? current.tenant.id : null;
        const tenant = tenants.find((t) => t.id === open);

        if (!tenant || isEditingIn(tenantRoot)) return;

        current = { type: 'tenant', tenant };
        void tenantView.show(tenant);
      })
      .catch(() => {});
  });

  const first = viewFromUrl() ?? defaultView();

  window.history.replaceState(null, '', urlFor(first));
  root.hidden = false;
  window.addEventListener('popstate', () => void show(viewFromUrl() ?? defaultView()));

  // Not waited for: the tree is already there while the open one loads.
  void show(first);
}

// /tenants: a tree of the libraries and repositories someone belongs to, and whichever one is
// open beside it. What is open is in the address (`?tenant=` a slug, or `?new=library` and
// `?new=repository` for the create forms), so a link, Back and a reload all land where they were.
// Only the open one is loaded.

import { renderCreateTenantForm } from '../../lib/createTenantUi';
import { showError } from '../../lib/errorUi';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { canCreateTenants, splitByKind, type TenantKind } from '../../lib/tenantKind';
import { listMyTenants } from '../../lib/tenants';
import type { MeOut, TenantOut, TenantSummaryOut } from '../../lib/types';
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
  const repositoriesGroup = required<HTMLElement>(root, '[data-repositories-group]');
  const repositoriesList = required<HTMLElement>(root, '[data-repositories]');
  const repositoriesDetails = required<HTMLDetailsElement>(root, '[data-repositories-details]');
  const createUnavailable = required<HTMLElement>(root, '[data-create-unavailable]');
  const error = required<HTMLElement>(root, '[data-error]');
  const createView = required<HTMLElement>(root, '[data-create]');
  const emptyView = required<HTMLElement>(root, '[data-empty]');
  const setup = required<HTMLElement>(root, '[data-setup]');

  const mayCreate = canCreateTenants(me);
  const links = new Map<string, HTMLAnchorElement>();

  let tenants: TenantSummaryOut[] = [];
  let current: View = { type: 'empty' };

  const tenantView = renderTenant(required<HTMLElement>(root, '[data-tenant]'), me, {
    onChanged: () => void reload(),
    onRenamed,
  });

  function urlFor(view: View): string {
    const params = new URLSearchParams();

    if (view.type === 'tenant') params.set('tenant', view.tenant.slug);
    if (view.type === 'new') {
      params.set('new', view.tenantKind === 'repository' ? 'repository' : 'library');
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

    const make = params.get('new');

    if (mayCreate && (make === 'library' || make === 'repository')) {
      return { type: 'new', tenantKind: make === 'repository' ? 'repository' : 'play' };
    }

    return null;
  }

  // The first library, else the first repository, else somewhere to start.
  function defaultView(): View {
    const { libraries, repositories } = splitByKind(tenants);
    const first = libraries[0] ?? repositories[0];

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
    const { libraries, repositories } = splitByKind(tenants);

    links.clear();
    librariesList.replaceChildren(
      ...libraries.map((tenant) => renderItem({ type: 'tenant', tenant }, tenant.name, false)),
      ...(mayCreate
        ? [renderItem({ type: 'new', tenantKind: 'play' }, 'New library', true)]
        : []),
    );
    repositoriesList.replaceChildren(
      ...repositories.map((tenant) => renderItem({ type: 'tenant', tenant }, tenant.name, false)),
      ...(mayCreate
        ? [renderItem({ type: 'new', tenantKind: 'repository' }, 'New repository', true)]
        : []),
    );
    librariesGroup.hidden = libraries.length === 0 && !mayCreate;
    repositoriesGroup.hidden = repositories.length === 0 && !mayCreate;
    markSelected();
  }

  async function refresh() {
    tenants = (await listMyTenants()).items;
    buildTree();
  }

  function fail(cause: unknown) {
    error.hidden = false;
    showError(error, cause);
  }

  // Opens the group the view belongs to, once it is selected, and leaves the other as it was.
  function openGroupOf(view: View) {
    const kind =
      view.type === 'tenant' ? view.tenant.kind : view.type === 'new' ? view.tenantKind : null;

    if (kind === 'repository') repositoriesDetails.open = true;
    else if (kind === 'play') librariesDetails.open = true;
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
      createView.replaceChildren(
        renderCreateTenantForm(view.tenantKind, (created) => void openCreated(created)),
      );
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
      fail(cause);
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
      fail(cause);
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

  const first = viewFromUrl() ?? defaultView();

  window.history.replaceState(null, '', urlFor(first));
  root.hidden = false;
  window.addEventListener('popstate', () => void show(viewFromUrl() ?? defaultView()));

  // Not waited for: the tree is already there while the open one loads.
  void show(first);
}

import { isTenantAdmin } from '../../lib/format';
import { getMe } from '../../lib/me';
import { canCreateTenants, isRepository } from '../../lib/tenantKind';
import { listMyTenants } from '../../lib/tenants';
import { required } from './required';

// Marks the page being shown in the nav. `/profile` and `/profile/` are the same page, so
// trailing slashes don't count.
export function renderNav(root: HTMLElement): void {
  const trimmed = (path: string) => (path.length > 1 ? path.replace(/\/+$/, '') : path);
  const here = trimmed(window.location.pathname);

  for (const link of root.querySelectorAll<HTMLAnchorElement>('nav a[data-path]')) {
    if (trimmed(link.dataset.path ?? '') === here) link.setAttribute('aria-current', 'page');
  }
}

// A link whose page has nothing for you stays hidden (`data-requires` names what it needs).
// Whoever is signed in gets the ones that need only that, and the rest as `GET /me` and
// `GET /tenants` say - the same rules the pages themselves apply. An answer that doesn't
// come leaves its links hidden, rather than showing one that may lead nowhere.
export async function showAllowedLinks(root: HTMLElement): Promise<void> {
  const nav = required<HTMLElement>(root, 'nav');

  function show(requires: string) {
    for (const link of nav.querySelectorAll<HTMLElement>(`[data-requires="${requires}"]`)) {
      link.hidden = false;
    }
  }

  show('signed-in');

  const [me, tenants] = await Promise.allSettled([getMe(), listMyTenants()]);

  // ADR 0175: who may create a library or a repository.
  if (me.status === 'fulfilled' && canCreateTenants(me.value)) show('create-tenant');

  // /beings lists the beings of a repository, or of a library where you GM a campaign.
  const gms = me.status === 'fulfilled' && me.value.campaign_gm_grants.length > 0;
  const inRepository = tenants.status === 'fulfilled' && tenants.value.items.some(isRepository);

  if (gms || inRepository) show('beings');

  // Shelf is where a library's owners and organizers see the repositories it may copy from.
  const administersLibrary =
    tenants.status === 'fulfilled' &&
    tenants.value.items.some((tenant) => !isRepository(tenant) && isTenantAdmin(tenant));

  if (administersLibrary) show('library-admin');

  // Studio is where a repository is run: for anyone who works on one, and for an account that may
  // make one (ADR 0175).
  const mayCreate = me.status === 'fulfilled' && canCreateTenants(me.value);

  if (inRepository || mayCreate) show('repository-work');
}

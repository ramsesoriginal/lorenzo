// /beings: a section of beings for each library you GM a campaign in, and for every repository.

import { campaignRoleFor } from '../../lib/format';
import { getMe } from '../../lib/me';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { isRepository } from '../../lib/tenantKind';
import { listMyTenants, listTenantCampaigns } from '../../lib/tenants';
import { renderBeings } from '../Beings/renderer';

const required = requiredIn('Beings panel');

// `root` is the <BeingsPanel /> block. It is shown once; the first load's failure rejects, for the
// page to show. A change anywhere in it loads it again.
export async function renderBeingsPanel(root: HTMLElement): Promise<void> {
  const error = required<HTMLElement>(root, '[data-error]');
  const empty = required<HTMLElement>(root, '[data-empty]');
  const list = required<HTMLElement>(root, '[data-list]');

  // Only the newest load paints.
  let latest = 0;

  async function load(): Promise<void> {
    const turn = ++latest;
    const me = await getMe();
    const tenants = await listMyTenants();
    const withGmCampaigns = await Promise.all(
      tenants.items.map(async (tenant) => {
        // A repository holds no campaigns, and the API says so with an error if asked: it is
        // listed for reading below, whoever owns it.
        if (isRepository(tenant)) return { tenant, gmCampaigns: [] };

        const campaigns = await listTenantCampaigns(tenant.id);
        const gmCampaigns = campaigns.items.filter((c) => campaignRoleFor(c.id, me) === 'gm');

        return { tenant, gmCampaigns };
      }),
    );
    const eligible = withGmCampaigns.filter(
      ({ tenant, gmCampaigns }) => gmCampaigns.length > 0 || isRepository(tenant),
    );
    const sections = await Promise.all(
      eligible.map(async ({ tenant, gmCampaigns }) => {
        const section = cloneRoot(root, '[data-beings-template]');

        await renderBeings(section, { tenant, gmCampaigns, onChanged: () => void reload() });

        return section;
      }),
    );

    if (turn !== latest) return;

    error.hidden = true;
    empty.hidden = sections.length > 0;
    list.replaceChildren(...sections);
  }

  // After a change: the same again, with what it failed on said in place.
  async function reload(): Promise<void> {
    try {
      await load();
    } catch (cause) {
      sayError(error, cause);
    }
  }

  await load();
  root.hidden = false;
}

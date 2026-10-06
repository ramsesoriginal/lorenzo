// One campaign you run, on /campaigns's "Where you run" (ADR 0179): who is at the table, by name
// (ADR 0176), and the characters each plays.
//
// The names come with the people lists themselves, so a GM who holds only a campaign grant, with no
// library membership to be named through, still sees them.

import { ApiError } from '../../lib/apiError';
import { charactersLine, personLabel, type RunRow, runRoleLabel } from '../../lib/campaigns';
import { sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { listCampaignGms, listCampaignPlayers } from '../../lib/tenants';

const required = requiredIn('Run campaign');

// `root` is the <RunCampaign /> row. It is filled once its people have been read; what can't be read
// is said in its place.
export async function renderRunCampaign(
  root: HTMLElement,
  row: RunRow,
  meId: string,
): Promise<void> {
  required<HTMLElement>(root, '[data-name]').textContent = row.campaignName;
  required<HTMLElement>(root, '[data-meta]').textContent =
    ` in ${row.tenantName} · ${runRoleLabel(row.role)}`;

  // Its administration is on /tenants, with this library open.
  required<HTMLAnchorElement>(root, '[data-manage]').href =
    `/tenants/?tenant=${encodeURIComponent(row.tenantSlug)}`;

  // A line of text for each, or the sentence that there is none.
  function fill(listSelector: string, emptySelector: string, lines: readonly string[]) {
    const list = required<HTMLElement>(root, listSelector);

    required<HTMLElement>(root, emptySelector).hidden = lines.length > 0;
    list.hidden = lines.length === 0;
    list.replaceChildren(
      ...lines.map((text) => {
        const person = rootElement(fromTemplate(root, '[data-person-template]'));

        person.textContent = text;

        return person;
      }),
    );
  }

  try {
    const [players, gms] = await Promise.all([
      listCampaignPlayers(row.tenantId, row.campaignId),
      listCampaignGms(row.tenantId, row.campaignId),
    ]);

    fill(
      '[data-players]',
      '[data-no-players]',
      players.items.map(
        (player) => `${personLabel(player, meId)}: ${charactersLine(player.characters)}`,
      ),
    );
    fill(
      '[data-gms]',
      '[data-no-gms]',
      gms.map((gm) => personLabel(gm, meId)),
    );
    required<HTMLElement>(root, '[data-people]').hidden = false;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      required<HTMLElement>(root, '[data-unavailable]').hidden = false;
    } else {
      sayError(required<HTMLElement>(root, '[data-error]'), e);
    }
  }
}

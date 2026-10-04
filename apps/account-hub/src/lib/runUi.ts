// One campaign you run, on /campaigns's "Where you run" (ADR 0179): who is at
// the table, by name (ADR 0176), and the characters each plays. Read-only: the
// administration of a campaign stays on /tenants, which this links to.
//
// The names come with the people lists themselves, so a GM who holds only a
// campaign grant, with no library membership to be named through, still sees
// them. Like userPicker.ts (ADR 0074), a lib/*.ts module that builds DOM.
import { ApiError } from './apiError';
import { charactersLine, personLabel, type RunRow, runRoleLabel } from './campaigns';
import { errorLine } from './errorUi';
import { listCampaignGms, listCampaignPlayers } from './tenants';

function list(items: readonly string[], emptySentence: string): HTMLElement {
  if (items.length === 0) {
    const none = document.createElement('p');
    none.textContent = emptySentence;
    return none;
  }
  const ul = document.createElement('ul');
  ul.className = 'list';
  for (const text of items) {
    const li = document.createElement('li');
    li.textContent = text;
    ul.append(li);
  }
  return ul;
}

// What one campaign shows if its people can't be read. An administrator who has
// opted out of a campaign's play side is told it is not theirs to see here
// (`GET /me/managed` still lists it: that is the administrative axis); anything
// else is shown as the error it is.
function peopleUnavailable(error: unknown): HTMLElement {
  if (error instanceof ApiError && error.status === 404) {
    const note = document.createElement('p');
    note.textContent = "This campaign's people aren't shown to you.";
    return note;
  }
  return errorLine(error);
}

export async function renderRunCampaign(row: RunRow, meId: string): Promise<HTMLLIElement> {
  const item = document.createElement('li');
  item.className = 'run-campaign';
  const name = document.createElement('strong');
  name.textContent = row.campaignName;
  const meta = document.createElement('span');
  meta.className = 'campaign-meta';
  meta.textContent = ` in ${row.tenantName} · ${runRoleLabel(row.role)}`;
  item.append(name, meta);

  try {
    const [players, gms] = await Promise.all([
      listCampaignPlayers(row.tenantId, row.campaignId),
      listCampaignGms(row.tenantId, row.campaignId),
    ]);
    const playersHeading = document.createElement('h4');
    playersHeading.textContent = 'Players';
    const gmsHeading = document.createElement('h4');
    gmsHeading.textContent = 'GMs';
    item.append(
      playersHeading,
      list(
        players.items.map(
          (player) => `${personLabel(player, meId)}: ${charactersLine(player.characters)}`,
        ),
        'No players yet.',
      ),
      gmsHeading,
      list(
        gms.map((gm) => personLabel(gm, meId)),
        'No GMs yet.',
      ),
    );
  } catch (e) {
    item.append(peopleUnavailable(e));
  }

  const manage = document.createElement('a');
  manage.href = '/tenants';
  manage.textContent = 'Manage in Your libraries and campaigns';
  item.append(manage);
  return item;
}

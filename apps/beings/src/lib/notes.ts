// Notes on a being (ADR 0271): an information row of type `note`, with one of the four audiences
// identity §14.3 names. The API stores who may read a row as `is_public` plus the rows of knowers
// (ADR 0038, 0109); the audiences are how this app reads and writes those.
import { client, type components, unwrap } from './api';
import type { GmWords } from './gmTitle';
import { type Information, listInformation } from './information';

export type Knower = components['schemas']['KnowerOut'];

/** The four audiences. "Shared with you" is what a reader who can't list knowers sees. */
export type Audience = 'gm' | 'everyone' | 'some' | 'player';
export type Shown = Audience | 'shared';

/**
 * What an audience is called and what it means, with the game masters named by `words`: the
 * campaign's own title when the being's campaigns agree on one (ADR 0294), otherwise "GM".
 */
export function audienceTexts(audience: Audience, words: GmWords): { label: string; hint: string } {
  switch (audience) {
    case 'gm':
      return {
        label: `${words.title} only`,
        hint: `Only the ${words.plural} of the campaign can read it.`,
      };
    case 'everyone':
      return { label: 'Everyone', hint: 'Anyone with access to the library can read it.' };
    case 'some':
      return {
        label: 'Some characters',
        hint: `The ${words.plural} and the characters you choose can read it.`,
      };
    case 'player':
      return {
        label: 'Player note',
        hint: `The ${words.plural} and this being's players can read it.`,
      };
  }
}

/** What a note says about who can read it. */
export function audienceLabel(shown: Shown, words: GmWords): string {
  return shown === 'shared' ? 'Shared with you' : audienceTexts(shown, words).label;
}

/** Characters told, among the knowers (a player knower is not a character). */
export const knownCharacters = (knowers: readonly Knower[]): string[] =>
  knowers.flatMap((k) => (k.kind === 'entity' && k.knower_entity_id ? [k.knower_entity_id] : []));

/**
 * The audience a stored note has. `knowers` is null when the viewer may not list them (only those
 * who can grant may, ADR 0109). A note only the being itself is told is a Player note.
 */
export function audienceOf(
  info: Pick<Information, 'is_public'>,
  knowers: readonly Knower[] | null,
  beingId: string,
): Shown {
  if (info.is_public) return 'everyone';
  if (knowers === null) return 'shared';
  if (knowers.length === 0) return 'gm';
  const characters = knownCharacters(knowers);
  if (
    characters.length === knowers.length &&
    characters.length === 1 &&
    characters[0] === beingId
  ) {
    return 'player';
  }
  return 'some';
}

/** The change that makes a note readable by `wanted`: whether it is public, and who is told. */
export type Plan = { isPublic: boolean; add: string[]; remove: string[]; removePlayers: string[] };

export function planAudience(
  wanted: { audience: Audience; characters: readonly string[] },
  knowers: readonly Knower[],
  beingId: string,
  words: GmWords,
): Plan {
  const told = new Set(knownCharacters(knowers));
  const players = knowers.flatMap((k) => (k.kind === 'player' && k.player_id ? [k.player_id] : []));
  const target = new Set<string>(
    wanted.audience === 'player' ? [beingId] : wanted.audience === 'some' ? wanted.characters : [],
  );

  if (wanted.audience === 'some' && target.size === 0) {
    throw new Error(
      `Choose at least one character, or make it ${audienceTexts('gm', words).label}.`,
    );
  }

  // Everyone can read it already; who else was told stays as it was, to come back to.
  if (wanted.audience === 'everyone') {
    return { isPublic: true, add: [], remove: [], removePlayers: [] };
  }

  return {
    isPublic: false,
    add: [...target].filter((id) => !told.has(id)),
    remove: [...told].filter((id) => !target.has(id)),
    removePlayers: wanted.audience === 'some' || wanted.audience === 'player' ? [] : players,
  };
}

/** Who a note is told to; only those who may grant it may ask (ADR 0109), so null if refused. */
export async function listKnowers(
  tenantId: string,
  informationId: string,
): Promise<Knower[] | null> {
  try {
    return await unwrap(
      await client.GET('/tenants/{tenant_id}/information/{information_id}/knowers', {
        params: { path: { tenant_id: tenantId, information_id: informationId } },
      }),
    );
  } catch {
    return null;
  }
}

/** Makes the note readable by the plan's characters: the adds and removes of knowers (idempotent). */
export async function applyKnowers(tenantId: string, informationId: string, plan: Plan) {
  const path = { tenant_id: tenantId, information_id: informationId };

  for (const id of plan.add) {
    await unwrap(
      await client.PUT(
        '/tenants/{tenant_id}/information/{information_id}/knowers/{knower_entity_id}',
        {
          params: { path: { ...path, knower_entity_id: id } },
        },
      ),
    );
  }

  for (const id of plan.remove) {
    await unwrap(
      await client.DELETE(
        '/tenants/{tenant_id}/information/{information_id}/knowers/{knower_entity_id}',
        { params: { path: { ...path, knower_entity_id: id } } },
      ),
    );
  }

  for (const id of plan.removePlayers) {
    await unwrap(
      await client.DELETE(
        '/tenants/{tenant_id}/information/{information_id}/player-knowers/{player_id}',
        { params: { path: { ...path, player_id: id } } },
      ),
    );
  }
}

/** The ids of every piece of information of the entity the viewer can see, in order (not just notes). */
export async function visibleOrder(tenantId: string, entityId: string): Promise<string[]> {
  return (await listInformation(tenantId, entityId)).map((info) => info.id);
}

/**
 * `all` with the notes in `notes` put in the order `notes` gives, in the places the notes held:
 * the other information keeps its slots (ADR 0237).
 */
export function reordered(all: readonly string[], notes: readonly string[]): string[] {
  const asNotes = new Set(notes);
  let next = 0;

  return all.map((id) => (asNotes.has(id) ? (notes[next++] as string) : id));
}

/** `ids` with the one at `from` moved to `to` (clamped), or the same list if it can't move. */
export function moved<T>(ids: readonly T[], from: number, to: number): T[] {
  const next = [...ids];

  if (from < 0 || from >= ids.length) return next;

  const [item] = next.splice(from, 1);

  next.splice(Math.max(0, Math.min(ids.length - 1, to)), 0, item as T);

  return next;
}

/** Writes the order of an entity's information; the list must be every row the viewer can see. */
export async function saveOrder(tenantId: string, entityId: string, ids: string[]) {
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/information/order', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: { information_ids: ids },
    }),
  );
}

/**
 * What a note says where it is Everyone's in a repository: it goes with every copy of the
 * repository and is what a person may read before copying it (RFC 0038 section 5, ADR 0293).
 */
export const EVERYONE_NOTE_IN_REPOSITORY = 'Visible to libraries that copy this';

/** Whether a note shows the lock: it is Everyone's, and the being is an entry of a repository. */
export function showsLock(inRepository: boolean | undefined, info: Pick<Information, 'is_public'>) {
  return inRepository === true && info.is_public;
}

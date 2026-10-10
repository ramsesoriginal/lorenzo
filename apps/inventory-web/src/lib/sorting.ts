// Sorting unsorted items (ADR 0240): the library's placeholders gathered by the name the player
// wrote, and a group given to a catalog item one instance at a time.
import { client, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { errorMessage } from './errorMessage';
import { normalize } from './fuzzy';
import { descriptionDraft, listInformation, saveDescription, textOf } from './information';
import { createCatalogItem, getEntityDetail, setInstancePrototype } from './items';
import type { ItemInstance } from './types';

/** Every instance of the placeholder the caller may see (ADR 0192: `?prototype_id=`). */
export async function listUnsortedInstances(
  tenantId: string,
  unsortedId: string,
): Promise<ItemInstance[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/item-instances', {
        params: {
          path: { tenant_id: tenantId },
          query: { prototype_id: unsortedId, page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

/** Instances written alike: the name most of them use, and who holds them. */
export type UnsortedGroup = Readonly<{
  key: string;
  name: string;
  instances: readonly ItemInstance[];
}>;

/** Grouped by name without case, accents or punctuation, biggest group first, then by name. */
export function groupUnsorted(instances: readonly ItemInstance[]): UnsortedGroup[] {
  const byKey = new Map<string, ItemInstance[]>();

  for (const instance of instances) {
    // A name of only punctuation still gets its own group, as typed.
    const key = normalize(instance.title) || instance.title;
    const group = byKey.get(key);

    if (group) group.push(instance);
    else byKey.set(key, [instance]);
  }

  return [...byKey.entries()]
    .map(([key, members]) => ({
      key,
      name: commonest(members.map((m) => m.title)),
      instances: members,
    }))
    .sort((a, b) => b.instances.length - a.instances.length || a.name.localeCompare(b.name));
}

/** The spelling used most; of those used equally, the first in code-point order, so it never varies. */
function commonest(names: readonly string[]): string {
  const counts = new Map<string, number>();

  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1);

  return (
    [...counts.entries()].sort(([a, x], [b, y]) => y - x || (a < b ? -1 : a > b ? 1 : 0))[0]?.[0] ??
    ''
  );
}

/** What `assign` did: how many took the new prototype, and which did not and why. */
export type Sorted = Readonly<{
  done: readonly ItemInstance[];
  failed: readonly { instance: ItemInstance; problem: string }[];
}>;

/** Each instance takes `prototypeId`, one after another; one failing does not stop the rest. */
export async function assignAll(
  tenantId: string,
  instances: readonly ItemInstance[],
  prototypeId: string,
  onProgress: (finished: number, total: number) => void = () => {},
): Promise<Sorted> {
  const done: ItemInstance[] = [];
  const failed: { instance: ItemInstance; problem: string }[] = [];

  for (const instance of instances) {
    try {
      await setInstancePrototype(tenantId, instance.entity_id, prototypeId);
      done.push(instance);
    } catch (error) {
      failed.push({ instance, problem: errorMessage(error) });
    }

    onProgress(done.length + failed.length, instances.length);
  }

  return { done, failed };
}

/** A new catalog item for a group, its description from the player's note if it has one. */
export async function createFromGroup(
  tenantId: string,
  name: string,
  inPublicCatalog: boolean,
  description: string | null,
): Promise<{ entityId: string; descriptionProblem: string | null }> {
  const item = await createCatalogItem(tenantId, name, [], inPublicCatalog);
  let descriptionProblem: string | null = null;

  if (description) {
    try {
      await saveDescription(
        tenantId,
        item.entity_id,
        null,
        { ...descriptionDraft(null, name), content: description },
        name,
      );
    } catch (error) {
      descriptionProblem = errorMessage(error);
    }
  }

  return { entityId: item.entity_id, descriptionProblem };
}

/** The player's notes on an instance, in the order written: title and text. */
export type PlayerNote = Readonly<{ title: string; text: string }>;

export async function playerNotes(tenantId: string, entityId: string): Promise<PlayerNote[]> {
  const notes = await listInformation(tenantId, entityId, ['note']);

  return notes.flatMap((note) => {
    const text = textOf(note)?.content ?? '';

    return text ? [{ title: note.title, text }] : [];
  });
}

/** The text of the group's first "Note" (the player's description), if any instance has one. */
export function descriptionFrom(notes: readonly PlayerNote[]): string | null {
  return notes.find((note) => note.title === 'Note')?.text ?? null;
}

/** Names for the holders of a group, each once. */
export async function holderNames(
  tenantId: string,
  instances: readonly ItemInstance[],
  known: Map<string, string>,
): Promise<void> {
  const unknown = [
    ...new Set(instances.map((i) => i.owner_entity_id).filter((id): id is string => !!id)),
  ].filter((id) => !known.has(id));

  await Promise.all(
    unknown.map(async (id) => {
      try {
        known.set(id, (await getEntityDetail(tenantId, id)).name);
      } catch {
        known.set(id, 'Someone');
      }
    }),
  );
}

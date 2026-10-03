import type { Suggestion } from '../components/Combobox/renderer';
import { listBeings } from './beings';
import { listGroups, matchingGroups } from './groups';
import type { BeingRef, BeingSummary } from './types';

function beingLabel(being: BeingSummary): string {
  // is_pc is genuinely three-valued (BeingSummary) - null means no
  // Character row exists at all, distinct from false.
  if (being.is_pc === null) return `${being.name} (being)`;

  return being.is_pc ? being.name : `${being.name} (NPC)`;
}

/** The beings matching `query`, as a combobox offers them. */
export async function searchBeings(
  tenantId: string,
  query: string,
): Promise<Suggestion<BeingRef>[]> {
  const found = await listBeings(tenantId, query);

  return found.items.map((being) => ({ label: beingLabel(being), value: being }));
}

/** Beings, then groups (ADR 0124): a group can own things too, so it's offered alongside. */
export async function searchBeingsAndGroups(
  tenantId: string,
  query: string,
): Promise<Suggestion<BeingRef>[]> {
  const [beings, groups] = await Promise.all([
    searchBeings(tenantId, query),
    listGroups(tenantId).catch(() => [] as BeingRef[]),
  ]);

  return [
    ...beings,
    ...matchingGroups(groups, query).map((group) => ({
      label: `${group.name} (group)`,
      value: group,
    })),
  ];
}

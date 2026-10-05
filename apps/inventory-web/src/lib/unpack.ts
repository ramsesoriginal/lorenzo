// Unpacking a pack (ADR 0189): which instances offer it, and what's asked and said. Pure, so
// the wording and the guess are tested without a page.
import type { Description, PackItem } from './types';

// A line of ADR 0145's contents list: "- 5 x [Label](slug)", at any depth.
const PACK_LINE = /^\s*- \d+ x \[[^\]]+\]\([^)]+\)/m;

/**
 * Whether one of the descriptions holds a line of a pack's contents list. A guess that decides
 * only whether to offer the button: the API's dry run is what knows, and a wrong guess is its
 * plain "not a pack".
 */
export function looksLikeAPack(descriptions: readonly Pick<Description, 'content'>[]): boolean {
  return descriptions.some((description) => PACK_LINE.test(description.content));
}

function line(item: PackItem): string {
  const { title, quantity } = item.item_instance;
  const count = quantity && quantity > 1 ? ` ×${quantity}` : '';
  const inside = item.children.map(line);

  return inside.length > 0 ? `${title}${count} (${inside.join(', ')})` : `${title}${count}`;
}

/** What a dry run says would be made: "Backpack (Rations ×5, Torch ×2), Rope". */
export function madeSummary(created: readonly PackItem[]): string {
  return created.map(line).join(', ');
}

/** The question: what unpacking makes, and what it costs. */
export function unpackQuestion(packTitle: string, created: readonly PackItem[]): string {
  return `Unpacking ${packTitle} makes ${madeSummary(created)}, and the pack goes. This can't be undone.`;
}

/** Said when the contents were made but the pack couldn't be removed: both are there now. */
export function packNotRemoved(reason: string): string {
  return `The contents were added, but the pack itself couldn't be removed: ${reason}`;
}

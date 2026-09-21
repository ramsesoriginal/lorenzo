// Shared by every command with an autocompleted string option (`/give`,
// `/set-current`, and onward) - Discord's own 25-choice cap and "filter by
// what's typed so far" behavior are identical everywhere this is used, so
// this is the one place that logic lives rather than being copied per
// command.

export const MAX_AUTOCOMPLETE_CHOICES = 25;

export type Choice = Readonly<{ name: string; value: string }>;

export function filterChoices(choices: readonly Choice[], typed: string): Choice[] {
  const needle = typed.toLowerCase();
  return choices
    .filter((choice) => choice.name.toLowerCase().includes(needle))
    .slice(0, MAX_AUTOCOMPLETE_CHOICES);
}

/** `"Torch"` for a non-stacked item, `"Torch ×5"` once it's part of a
 * stack (quantity > 1) - matches format-inventory.ts's own convention for
 * showing stack size only when it's not just "one, unremarkable." */
export function formatItemChoiceName(title: string, quantity: number | null): string {
  return quantity !== null && quantity > 1 ? `${title} ×${quantity}` : title;
}

// Discord rejects an autocomplete choice whose `name` is over 100 characters.
const MAX_CHOICE_NAME_LENGTH = 100;

/** `formatItemChoiceName`, plus the instance's slug in brackets when it has
 * one (`"Goblin hoard [goblin-hoard]"`) - so a GM can tell two containers
 * with the same title apart, and learn the slug they could have typed
 * instead. The title is what gets truncated to stay under Discord's
 * 100-character limit, never the slug: it's the part someone might copy. */
export function formatChoiceNameWithSlug(
  title: string,
  quantity: number | null,
  slug: string | null,
): string {
  const name = formatItemChoiceName(title, quantity);
  if (slug === null) return name.slice(0, MAX_CHOICE_NAME_LENGTH);
  const suffix = ` [${slug}]`;
  const room = Math.max(MAX_CHOICE_NAME_LENGTH - suffix.length, 0);
  return `${name.slice(0, room)}${suffix}`.slice(0, MAX_CHOICE_NAME_LENGTH);
}

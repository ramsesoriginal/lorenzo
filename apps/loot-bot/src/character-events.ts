import { randomUUID } from "node:crypto";
import type { Logger } from "pino";
import { insertCharacterEvents } from "./db.js";

/**
 * Recording what happens to characters' belongings, for `/changes` (ADR
 * 0097). Each command that moves something between characters builds one
 * {@link PendingEvent} with a describer below and hands it to
 * {@link recordCharacterEvents}.
 *
 * The wording is chosen for how it will be *read later*, by whoever plays an
 * affected character, possibly among several characters of their own:
 *
 * - it names characters instead of saying "you";
 * - it never names a GM who acted - `/changes` shows what happened to your
 *   stuff, not who decided it (RFC 0022 leaves actor visibility open);
 * - it's rendered now, from names the acting user was allowed to read now.
 */

export type ChangeKind =
  | "gave"
  | "given-in-bulk"
  | "reassigned"
  | "awarded"
  | "confiscated"
  | "took"
  | "claim-honored";

export type NamedCharacter = Readonly<{ id: string; name: string }>;

/** One thing that happened, and which characters it happened to. */
export type PendingEvent = Readonly<{
  kind: ChangeKind;
  summary: string;
  characterEntityIds: readonly string[];
}>;

/** `"Torch"`, or `"Torch ×5"` for a stack - the convention every other
 * place in this bot uses for showing a stack's size. */
export function describeItem(title: string, quantity: number | null): string {
  return quantity !== null && quantity > 1 ? `${title} ×${quantity}` : title;
}

/** A character for an event, tolerating a failed name lookup: the id is what
 * matters for *who sees* the event, so a missing name only weakens the
 * wording ("another character") rather than dropping the event. `null` when
 * there's no character at all (an ownerless item). */
export function nameCharacter(
  id: string | null | undefined,
  name: string | null | undefined,
): NamedCharacter | null {
  return id ? { id, name: name ?? "another character" } : null;
}

function ids(...characters: readonly (NamedCharacter | null)[]): string[] {
  return characters.flatMap((c) => (c ? [c.id] : []));
}

/** `/give`: a character gave an item to another. `giver` is `null` when the
 * item had no owner to name. */
export function giveEvent(args: {
  giver: NamedCharacter | null;
  receiver: NamedCharacter;
  item: string;
}): PendingEvent {
  return {
    kind: "gave",
    summary: `${args.giver?.name ?? "Someone"} gave ${args.item} to ${args.receiver.name}.`,
    characterEntityIds: ids(args.giver, args.receiver),
  };
}

const MAX_LISTED_ITEMS = 5;

/** `/give-bulk`: several items given to one character. Only the receiver is
 * recorded - the bulk-assign result doesn't say who each item came from. */
export function bulkGiveEvent(args: {
  receiver: NamedCharacter;
  items: readonly string[];
}): PendingEvent {
  const listed = args.items.slice(0, MAX_LISTED_ITEMS).join(", ");
  const more = args.items.length - MAX_LISTED_ITEMS;
  const summary =
    args.items.length === 1
      ? `${args.receiver.name} was given ${args.items[0]}.`
      : `${args.receiver.name} was given ${args.items.length} items: ${listed}${more > 0 ? `, and ${more} more` : ""}.`;
  return { kind: "given-in-bulk", summary, characterEntityIds: ids(args.receiver) };
}

/** `/reassign` (a GM): an item moved between characters. The GM isn't named. */
export function reassignEvent(args: {
  from: NamedCharacter | null;
  to: NamedCharacter;
  item: string;
}): PendingEvent {
  return {
    kind: "reassigned",
    summary: args.from
      ? `${args.item} was reassigned from ${args.from.name} to ${args.to.name}.`
      : `${args.item} was assigned to ${args.to.name}.`,
    characterEntityIds: ids(args.from, args.to),
  };
}

/** `/award` (a GM): a brand-new item for a character. */
export function awardEvent(args: { character: NamedCharacter; item: string }): PendingEvent {
  return {
    kind: "awarded",
    summary: `${args.character.name} was awarded ${args.item}.`,
    characterEntityIds: ids(args.character),
  };
}

/** `/confiscate` (a GM): an item taken away for good. */
export function confiscateEvent(args: { character: NamedCharacter; item: string }): PendingEvent {
  return {
    kind: "confiscated",
    summary: `${args.item} was taken from ${args.character.name}.`,
    characterEntityIds: ids(args.character),
  };
}

/** `/drop`: a character took an item straight from a loot drop. */
export function takeEvent(args: { character: NamedCharacter; item: string }): PendingEvent {
  return {
    kind: "took",
    summary: `${args.character.name} took ${args.item} from a loot drop.`,
    characterEntityIds: ids(args.character),
  };
}

/** `/drop` apply-claims: a claim was honored, and the item is now theirs. */
export function claimHonoredEvent(args: {
  character: NamedCharacter;
  item: string;
}): PendingEvent {
  return {
    kind: "claim-honored",
    summary: `${args.character.name} received ${args.item} from a loot drop claim.`,
    characterEntityIds: ids(args.character),
  };
}

// Well under anything a Discord message could show, and keeps a runaway
// title from bloating the table.
const MAX_SUMMARY_LENGTH = 500;

/**
 * Writes events to the log: one row per affected character, all of an
 * event's rows sharing one `eventId` so a player who controls both sides of
 * a transfer sees it once.
 *
 * Best-effort by design. It always runs *after* the write it describes has
 * already succeeded, so a failure here (the database, say) is logged and
 * swallowed - a missing log line must never turn a completed give into an
 * error message.
 */
export async function recordCharacterEvents(
  events: readonly PendingEvent[],
  logger: Logger,
): Promise<void> {
  const rows = events.flatMap((event) => {
    const eventId = randomUUID();
    const summary =
      event.summary.length <= MAX_SUMMARY_LENGTH
        ? event.summary
        : `${event.summary.slice(0, MAX_SUMMARY_LENGTH - 1)}…`;
    return [...new Set(event.characterEntityIds)].map((characterEntityId) => ({
      eventId,
      characterEntityId,
      kind: event.kind,
      summary,
    }));
  });
  if (rows.length === 0) return;

  try {
    await insertCharacterEvents(rows);
  } catch (error) {
    logger.warn({ err: error }, "couldn't record character events");
  }
}

import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js";
import type { ContentsResultItem } from "./lorenzo-client.js";

/**
 * Giving what's inside a container (ADR 0125): `/give`'s "Give with what's
 * inside" and `/give-contents`. Pure builders and wording, no Discord API
 * calls, mirroring format-give.ts's split from give.ts. Every question is
 * worded from a dry run's answer: what would go, and whose what can't go
 * stays.
 *
 * Like `/give`'s confirm, the whole intent lives in the button's `customId`
 * (ADR 0088): two entity ids fit Discord's 100-character limit.
 */
export type GiveContentsIntent = Readonly<{
  containerEntityId: string;
  targetCharacterId: string;
}>;

export const GIVE_CONTENTS_CANCEL_CUSTOM_ID = "give-contents:no";

export function buildGiveContentsCustomId(intent: GiveContentsIntent): string {
  return `give-contents:ok:${intent.containerEntityId}:${intent.targetCharacterId}`;
}

/** Inverse of {@link buildGiveContentsCustomId}; `undefined` for anything
 * that isn't a well-formed confirm id. */
export function parseGiveContentsCustomId(customId: string): GiveContentsIntent | undefined {
  const [namespace, action, containerEntityId, targetCharacterId, ...rest] = customId.split(":");
  if (namespace !== "give-contents" || action !== "ok" || rest.length > 0) return undefined;
  if (!containerEntityId || !targetCharacterId) return undefined;
  return { containerEntityId, targetCharacterId };
}

export function buildGiveContentsComponents(
  intent: GiveContentsIntent,
): ActionRowBuilder<ButtonBuilder>[] {
  return [
    new ActionRowBuilder<ButtonBuilder>().addComponents(
      new ButtonBuilder()
        .setCustomId(buildGiveContentsCustomId(intent))
        .setLabel("Give")
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId(GIVE_CONTENTS_CANCEL_CUSTOM_ID)
        .setLabel("Cancel")
        .setStyle(ButtonStyle.Secondary),
    ),
  ];
}

export function things(count: number): string {
  return `${count} ${count === 1 ? "thing" : "things"}`;
}

export function givenCount(contents: readonly ContentsResultItem[]): number {
  return contents.filter((content) => content.status === "ok").length;
}

/**
 * Whose the things that can't go stay: "1 thing inside stays Pia's." With
 * several owners: "3 things inside stay with their owners: 2 are Pia's, 1
 * is Oskar's." `null` when everything goes.
 */
export function formatKeptNote(contents: readonly ContentsResultItem[]): string | null {
  const byOwner = new Map<string, number>();
  for (const content of contents) {
    if (content.status !== "kept") continue;
    const owner = content.owner?.name ?? "no one";
    byOwner.set(owner, (byOwner.get(owner) ?? 0) + 1);
  }
  const kept = [...byOwner.values()].reduce((sum, n) => sum + n, 0);
  if (kept === 0) return null;
  if (byOwner.size === 1) {
    const [owner] = byOwner.keys();
    return `${things(kept)} inside ${kept === 1 ? "stays" : "stay"} ${owner}'s.`;
  }
  const shares = [...byOwner].map(([owner, n]) => `${n} ${n === 1 ? "is" : "are"} ${owner}'s`);
  return `${things(kept)} inside stay with their owners: ${shares.join(", ")}.`;
}

function withKept(sentence: string, contents: readonly ContentsResultItem[]): string {
  const kept = formatKeptNote(contents);
  return kept ? `${sentence} ${kept}` : sentence;
}

/** `/give-contents`' question, when something inside can go. */
export function formatGiveContentsPrompt(
  containerTitle: string,
  targetName: string,
  contents: readonly ContentsResultItem[],
): string {
  return withKept(
    `Give **${things(givenCount(contents))}** inside **${containerTitle}** to **${targetName}**?`,
    contents,
  );
}

/** When nothing inside can go: nothing's there, or none of it is yours to give. */
export function formatNothingInsideToGive(
  containerTitle: string,
  targetName: string,
  contents: readonly ContentsResultItem[],
): string {
  if (contents.length === 0) {
    return `There's nothing inside ${containerTitle} to give to ${targetName}.`;
  }
  return withKept(`Nothing inside ${containerTitle} can be given.`, contents);
}

export function formatContentsGiven(
  containerTitle: string,
  targetName: string,
  contents: readonly ContentsResultItem[],
): string {
  return withKept(
    `Gave ${things(givenCount(contents))} inside ${containerTitle} to ${targetName}.`,
    contents,
  );
}

/** `/give`'s extra line for a container: what "Give with what's inside" would add. */
export function formatWithContentsNote(contents: readonly ContentsResultItem[]): string {
  return withKept(
    `"Give with what's inside" also gives ${things(givenCount(contents))} inside it.`,
    contents,
  );
}

export function formatGivenWithContents(
  itemTitle: string,
  targetName: string,
  contents: readonly ContentsResultItem[],
): string {
  const given = givenCount(contents);
  return withKept(
    given > 0
      ? `Gave ${itemTitle} to ${targetName}, with ${things(given)} inside.`
      : `Gave ${itemTitle} to ${targetName}.`,
    contents,
  );
}

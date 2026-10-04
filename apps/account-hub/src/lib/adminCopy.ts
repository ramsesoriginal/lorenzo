// What a campaign's manager is asked, and told, when they take someone off a
// campaign or undo a roster link (ADR 0170). Pure and dependency-free like
// format.ts, so a test can hold the sentences to what the API does.

// DELETE .../players/{id} removes the Player row and every character link it
// grants (ADR 0081); the characters themselves are untouched.
export function removePlayerConfirmation(playerName: string, campaignName: string): string {
  return `Remove ${playerName} from "${campaignName}"? Their seat goes, and with it the links that give them their characters here. The characters themselves are not deleted.`;
}

// DELETE .../characters/{id}/players/{player} removes one link (ADR 0079's
// reverse) and nothing else.
export function unlinkCharacterConfirmation(
  characterName: string,
  campaignName: string,
  playerName?: string,
): string {
  const whose = playerName === undefined ? 'this seat' : `${playerName}'s seat`;
  return `Stop using "${characterName}" in "${campaignName}"? Only the link between ${whose} and the character is removed. The character is not deleted, and its links in other campaigns stay.`;
}

// A character's control comes from its roster links, not from its owner, so
// unlinking its owner would leave a character owned by someone who no longer
// controls it (ADR 0170). The hub does not change owners, so it says so.
export function ownerLinkRefusal(characterName: string, playerName?: string): string {
  const who = playerName ?? 'this player';
  return `"${characterName}" is owned by ${who} here, so the link stays. Changing who owns a character isn't something the hub does yet.`;
}

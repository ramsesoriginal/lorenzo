import { describe, expect, it } from 'vitest';
import {
  ownerLinkRefusal,
  removePlayerConfirmation,
  unlinkCharacterConfirmation,
} from '../../src/lib/adminCopy';

describe('removePlayerConfirmation', () => {
  it('names who and where, and what goes with the seat', () => {
    const text = removePlayerConfirmation('Pia Player', 'Zorro');
    expect(text).toContain('Remove Pia Player from "Zorro"?');
    expect(text).toContain('with it the links that give them their characters here');
    expect(text).toContain('The characters themselves are not deleted');
  });
});

describe('unlinkCharacterConfirmation', () => {
  it('says it is one link, and leaves the character and its other links alone', () => {
    const text = unlinkCharacterConfirmation('Cael', 'Hood');
    expect(text).toContain('Stop using "Cael" in "Hood"?');
    expect(text).toContain('Only the link between this seat and the character is removed');
    expect(text).toContain('The character is not deleted');
    expect(text).toContain('its links in other campaigns stay');
  });

  it('names whose seat when someone else is doing it', () => {
    expect(unlinkCharacterConfirmation('Cael', 'Hood', 'Pia Player')).toContain(
      "Pia Player's seat",
    );
  });
});

describe('ownerLinkRefusal', () => {
  it('says why, and that the hub does not change owners', () => {
    expect(ownerLinkRefusal('Cael', 'Pia Player')).toBe(
      `"Cael" is owned by Pia Player here, so the link stays. Changing who owns a character isn't something the hub does yet.`,
    );
  });

  it('copes without a name', () => {
    expect(ownerLinkRefusal('Cael')).toContain('owned by this player here');
  });
});

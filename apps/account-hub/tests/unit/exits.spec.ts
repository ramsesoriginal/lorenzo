import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/lib/apiError';
import {
  deleteAccountConfirmation,
  leaveLibraryConfirmation,
  soleOwnerLibraryId,
  soleOwnerMessage,
  stepDownConfirmation,
} from '../../src/lib/exits';

const LIBRARY_ID = '3f2b8c1e-5a47-4d0e-9c61-0b7e2f4a8d15';
const USER_ID = '9a1d6e40-27c3-4b58-8f0a-5c3e71d92b64';

function lastOwner(libraryId = LIBRARY_ID): ApiError {
  const detail = `User ${USER_ID} is the sole OWNER of tenant ${libraryId}`;
  return new ApiError(detail, 409, 'last-owner', {
    title: "Cannot remove the tenant's only OWNER",
    status: 409,
    detail,
  });
}

describe('soleOwnerLibraryId', () => {
  it("reads the library out of the API's last-owner detail", () => {
    expect(soleOwnerLibraryId(lastOwner())).toBe(LIBRARY_ID);
  });

  it('is case-insensitive about the id', () => {
    expect(soleOwnerLibraryId(lastOwner(LIBRARY_ID.toUpperCase()))).toBe(LIBRARY_ID.toUpperCase());
  });

  it.each([
    ['another 409', new ApiError('x', 409, undefined, { detail: 'Slug already in use' })],
    ['a 409 with no detail', new ApiError('x', 409, undefined, {})],
    [
      'the same words under another status',
      new ApiError('x', 403, undefined, { detail: `sole OWNER of tenant ${LIBRARY_ID}` }),
    ],
    ['a 409 naming no id', new ApiError('x', 409, undefined, { detail: 'sole OWNER of tenant x' })],
    ['a plain Error', new Error(`sole OWNER of tenant ${LIBRARY_ID}`)],
    ['a string', 'sole OWNER'],
    ['null', null],
  ])('is not claimed for %s', (_name, error) => {
    expect(soleOwnerLibraryId(error)).toBeNull();
  });
});

describe('soleOwnerMessage', () => {
  const names = new Map([[LIBRARY_ID, 'The Shattered Realms']]);

  it('names the library and says what to do, for leaving', () => {
    expect(soleOwnerMessage(lastOwner(), names, 'leave-library')).toBe(
      `You're the only owner of "The Shattered Realms", so you can't leave it yet. Make someone else an owner first, then try again.`,
    );
  });

  it('says the account is what is blocked, for deleting it', () => {
    expect(soleOwnerMessage(lastOwner(), names, 'delete-account')).toBe(
      `You're the only owner of "The Shattered Realms", so your account can't be deleted yet. Make someone else an owner first, then try again.`,
    );
  });

  it('still helps when the library is not one it has a name for', () => {
    expect(soleOwnerMessage(lastOwner(), new Map(), 'delete-account')).toBe(
      "You're the only owner of one of your libraries, so your account can't be deleted yet. Make someone else an owner first, then try again.",
    );
  });

  it('never shows the ids from the detail', () => {
    const message = soleOwnerMessage(lastOwner(), names, 'leave-library') ?? '';
    expect(message).not.toContain(LIBRARY_ID);
    expect(message).not.toContain(USER_ID);
  });

  it('is null for any other error', () => {
    expect(soleOwnerMessage(new Error('x'), names, 'leave-library')).toBeNull();
  });
});

describe('the confirmations', () => {
  it('leaving a library says what ADR 0084 says happens, and names the library', () => {
    const text = leaveLibraryConfirmation('The Shattered Realms');
    expect(text).toContain('Leave "The Shattered Realms"?');
    expect(text).toContain('Your membership ends');
    expect(text).toContain('Nothing you made there is deleted');
    expect(text).toContain('campaign seat or GM role you hold in it stays');
    expect(text).toContain('notification confirming it');
  });

  it('stepping down says who can make you its GM again, and that an administrator keeps it', () => {
    const text = stepDownConfirmation('Zorro');
    expect(text).toContain('Step down as GM of "Zorro"?');
    expect(text).toContain('unless you also administer its library');
    expect(text).toContain('can make you its GM again');
  });

  it('deleting an account says what goes, what stays, and that the Authgear login does not', () => {
    const text = deleteAccountConfirmation();
    // What it does (ADR 0036): the account and every row it holds, everywhere.
    expect(text).toContain('removes your account');
    for (const held of ['membership', 'player seat', 'GM role', 'campaign opt-out']) {
      expect(text).toContain(held);
    }
    expect(text).toContain('in every library');
    // What it leaves: what they made, no longer credited.
    expect(text).toContain('What you made stays, but no longer names you');
    // What it does not do.
    expect(text).toContain('does not delete your Authgear login');
    expect(text).toContain('fresh, empty Lorenzo account');
  });

  it('use the product word for a tenant', () => {
    for (const text of [
      leaveLibraryConfirmation('x'),
      stepDownConfirmation('x'),
      deleteAccountConfirmation(),
    ]) {
      expect(text.toLowerCase()).not.toContain('tenant');
    }
  });
});

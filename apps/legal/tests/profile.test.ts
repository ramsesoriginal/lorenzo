import { describe, expect, it, vi } from 'vitest';
import { loadProfile, parseProfile, unverifiedPaths } from '../src/lib/profile';
import { SAMPLE_PROFILE } from '../src/lib/sample-profile';

// A profile the tests are free to break in any way, so it is deliberately loose.
// biome-ignore lint/suspicious/noExplicitAny: test data that is edited into invalid shapes
const clone = () => structuredClone(SAMPLE_PROFILE) as Record<string, any>;

describe('the operator profile', () => {
  it('accepts a complete profile and marks the sample', () => {
    expect(parseProfile(SAMPLE_PROFILE).sample).toBe(false);
    expect(loadProfile({ LEGAL_PROFILE_SAMPLE: '1' }, SAMPLE_PROFILE).sample).toBe(true);
  });

  it('fails the build with no profile, and says what to set', () => {
    expect(() => loadProfile({}, SAMPLE_PROFILE)).toThrow(/LEGAL_PROFILE/);
    expect(() => loadProfile({ LEGAL_PROFILE: '  ' }, SAMPLE_PROFILE)).toThrow(/LEGAL_PROFILE/);
  });

  it('names every missing field at once', () => {
    const incomplete = clone();
    delete incomplete.operator.name;
    delete incomplete.operator.email;
    incomplete.providers = [];

    expect(() => parseProfile(incomplete)).toThrow(
      /operator\.name: is required[\s\S]*operator\.email: is required[\s\S]*providers: needs at least one/,
    );
  });

  it('rejects a placeholder as if it were missing', () => {
    for (const value of ['TODO', 'tbd', '<street>', '...', '   ']) {
      const profile = clone();
      profile.operator.street = value;
      expect(() => parseProfile(profile), value).toThrow(/operator\.street/);
    }
  });

  it("tells 'none' from a forgotten tax number and second contact", () => {
    const forgotten = clone();
    delete forgotten.operator.taxId;
    delete forgotten.operator.secondContact;
    const message = (() => {
      try {
        parseProfile(forgotten);
        return '';
      } catch (e) {
        return (e as Error).message;
      }
    })();
    expect(message).toMatch(/operator\.taxId/);
    expect(message).toMatch(/secondContact/);

    const empty = clone();
    empty.operator.taxId = { kind: 'vat' };
    expect(() => parseProfile(empty)).toThrow(/operator\.taxId\.value/);

    const given = clone();
    given.operator.taxId = { kind: 'vat', value: 'XX000000000' };
    expect(parseProfile(given).operator.taxId).toEqual({ kind: 'vat', value: 'XX000000000' });
  });

  it('wants https addresses and real dates', () => {
    const profile = clone();
    profile.supervisoryAuthority.url = 'http://insecure.example.test';
    profile.changedOn = '7 November';
    const message = (() => {
      try {
        parseProfile(profile);
        return '';
      } catch (e) {
        return (e as Error).message;
      }
    })();
    expect(message).toMatch(/supervisoryAuthority\.url/);
    expect(message).toMatch(/changedOn/);
  });

  it('keeps the review date empty until a review has happened', () => {
    expect(parseProfile(SAMPLE_PROFILE).reviewedOn).toBeNull();
    const reviewed = clone();
    reviewed.reviewedOn = '2027-01-31';
    expect(parseProfile(reviewed).reviewedOn).toBe('2027-01-31');
  });

  it('wants the Gravatar lookup stated, true or false', () => {
    const profile = clone();
    delete profile.gravatarLookup;
    expect(() => parseProfile(profile)).toThrow(/gravatarLookup/);
  });

  it('rejects text that still says FILL or TODO, anywhere in a value', () => {
    for (const value of ['FILL: the region', 'Region TODO', 'to be confirmed (TBD)']) {
      const profile = clone();
      profile.providers[0].location.en = value;
      expect(() => parseProfile(profile), value).toThrow(/providers\[0\]\.location\.en/);
    }
  });

  it('builds with guesses but names every one of them in a warning', () => {
    const profile = clone();
    profile.providers[0].location.de = 'Frankfurt [unverified]';
    profile.retention.logs.en = '30 days [unverified]';
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(loadProfile({ LEGAL_PROFILE: JSON.stringify(profile) }, SAMPLE_PROFILE).sample).toBe(
      false,
    );
    expect(unverifiedPaths(profile)).toEqual(['providers[0].location.de', 'retention.logs.en']);
    expect(warn.mock.calls[0]?.[0]).toMatch(
      /providers\[0\]\.location\.de[\s\S]*retention\.logs\.en/,
    );
    warn.mockRestore();
  });

  it('does not accept invalid JSON in the environment', () => {
    expect(() => loadProfile({ LEGAL_PROFILE: '{nope' }, SAMPLE_PROFILE)).toThrow(/not JSON/);
  });
});

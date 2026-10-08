import { describe, expect, it } from 'vitest';
import {
  ACKNOWLEDGE_TEXT,
  breakingLines,
  composerProblem,
  contentLines,
  countsLines,
  defaultLabel,
  descriptionsHint,
  matchesSentence,
  nameList,
  onRelease,
  publishBody,
  releasePlace,
  TEXT_NOT_TRACKED,
  warningLines,
} from '../../src/lib/releases';
import type {
  BreakingRowOut,
  ReleaseCountsOut,
  ReleaseOut,
  ReleasePreviewOut,
} from '../../src/lib/types';

const counts = (over: Partial<ReleaseCountsOut> = {}): ReleaseCountsOut => ({
  entities: { added: 0, changed: 0, removed: 0 },
  stat_groups: { added: 0, changed: 0, removed: 0 },
  stat_definitions: { added: 0, changed: 0, removed: 0 },
  attachments: { added: 0, removed: 0 },
  descriptions_edited: 0,
  ...over,
});

const release = (over: Partial<ReleaseOut> = {}): ReleaseOut => ({
  id: 'r1',
  number: 3,
  label: '1.3',
  notes: null,
  breaking: false,
  created_at: '2026-10-08T10:00:00Z',
  digest: 'abc',
  counts: counts(),
  breaking_rows: [],
  warning_rows: [],
  ...over,
});

const preview = (over: Partial<ReleasePreviewOut> = {}): ReleasePreviewOut => ({
  release: release(),
  baseline: true,
  matches: true,
  live_digest: 'abc',
  differing_rows: 0,
  counts: counts(),
  added: [],
  changed: [],
  removed: [],
  breaking: [],
  warnings: [],
  descriptions_edited: 0,
  libraries_told: 2,
  ...over,
});

const hit = (over: Partial<BreakingRowOut> = {}): BreakingRowOut => ({
  kind: 'entity',
  row_id: 'e1',
  parent_id: null,
  name: 'Longsword',
  reason: 'entity_removed',
  detail: '“Longsword” was removed. Libraries that copied it can only keep it.',
  ...over,
});

describe('matches and edited since, in the words of the rule', () => {
  it('says "Matches release 1.3" when the live content matches', () => {
    expect(matchesSentence(preview())).toBe('Matches release 1.3.');
  });

  it('says "Edited since release 1.3" with how many rows differ, and never "stable" or "frozen"', () => {
    const text = matchesSentence(preview({ matches: false, differing_rows: 4 }));

    expect(text).toBe('Edited since release 1.3: 4 rows differ.');
    expect(matchesSentence(preview({ matches: false, differing_rows: 1 }))).toBe(
      'Edited since release 1.3: 1 row differs.',
    );
    expect(text).not.toMatch(/stable|frozen|final/i);
  });

  it('says so when there is no release, or one made before releases could be compared', () => {
    expect(matchesSentence(preview({ release: null, baseline: false, matches: null }))).toMatch(
      /No release yet/,
    );
    expect(matchesSentence(preview({ baseline: false, matches: null }))).toBe(
      'Release 1.3 was made before releases could be compared, so what changed since cannot be said.',
    );
  });

  it('always has the line that text edits are not tracked', () => {
    expect(TEXT_NOT_TRACKED).toMatch(/^Text edits are not tracked/);
  });

  it('gives the description count as a hint, written or edited, that cannot see a deletion', () => {
    expect(descriptionsHint(preview({ descriptions_edited: 12 }))).toBe(
      '12 descriptions written or edited since release 1.3. This is a hint: a deleted description leaves no trace.',
    );
    expect(descriptionsHint(preview({ descriptions_edited: 0 }))).toBeNull();
    expect(descriptionsHint(preview({ release: null, descriptions_edited: null }))).toBeNull();
  });
});

describe('what a release contains', () => {
  it('has a line for each kind that has anything', () => {
    expect(
      countsLines(
        counts({
          entities: { added: 3, changed: 5, removed: 1 },
          stat_definitions: { added: 0, changed: 2, removed: 0 },
          attachments: { added: 1, removed: 0 },
        }),
      ),
    ).toEqual([
      'Entries: 3 added, 5 changed, 1 removed.',
      'Stats: 2 changed.',
      'Parents added to what other repositories hold: 1 added, 0 taken off.',
    ]);
    expect(countsLines(counts())).toEqual([]);
    expect(countsLines(null)).toEqual([]);
  });

  it('names the first few of what is added or removed, and how many more', () => {
    const rows = Array.from({ length: 10 }, (_, i) => ({ name: `Row ${i + 1}` }));

    expect(nameList(rows.slice(0, 2))).toBe('“Row 1”, “Row 2”');
    expect(nameList(rows)).toBe(
      '“Row 1”, “Row 2”, “Row 3”, “Row 4”, “Row 5”, “Row 6”, “Row 7”, “Row 8” and 2 more',
    );
  });

  it('says what a publish would contain, and when nothing differs', () => {
    const lines = contentLines(
      preview({
        counts: counts({ entities: { added: 1, changed: 0, removed: 1 } }),
        added: [
          { kind: 'entity', row_id: 'a', parent_id: null, name: 'Buckler', parent_name: null },
        ],
        removed: [
          { kind: 'entity', row_id: 'b', parent_id: null, name: 'Club', parent_name: null },
        ],
      }),
    );

    expect(lines).toEqual(['Entries: 1 added, 1 removed.', 'New: “Buckler”.', 'Removed: “Club”.']);
    expect(contentLines(preview())).toEqual(['Nothing differs from the latest release.']);
  });
});

describe('a parent added is a warning', () => {
  const added = (name: string): BreakingRowOut =>
    hit({
      kind: 'attachment',
      name,
      reason: 'attachment_added',
      detail: `“Silvered” was added as a parent of “${name}”.`,
    });

  it('says how many, and names the first few', () => {
    expect(warningLines([])).toEqual([]);

    const one = warningLines([added('Dagger')]);

    expect(one[0]).toMatch(/^A parent is added to items libraries may already hold/);
    expect(one[0]).toMatch(/does not make the release breaking/);
    expect(one.slice(1)).toEqual(['“Silvered” was added as a parent of “Dagger”.']);

    const many = warningLines(Array.from({ length: 10 }, (_, i) => added(`Item ${i + 1}`)));

    expect(many[0]).toMatch(/^10 parents are added/);
    expect(many).toHaveLength(1 + 8 + 1);
    expect(many.at(-1)).toBe('and 2 more.');
  });

  it('is never something to acknowledge', () => {
    const form = { label: '', notes: '', breaking: false, acknowledged: false };

    expect(composerProblem(form, [])).toBeNull();
    expect(publishBody(form, [])).toEqual({ breaking: false, acknowledge_breaking: false });
  });
});

describe('breaking', () => {
  it('says each hit as the API words it', () => {
    expect(breakingLines([hit()])).toEqual([
      '“Longsword” was removed. Libraries that copied it can only keep it.',
    ]);
  });

  it('cannot be sent until it is acknowledged', () => {
    const form = { label: '', notes: '', breaking: false, acknowledged: false };

    expect(composerProblem(form, [hit()])).toMatch(/breaks things/);
    expect(composerProblem({ ...form, acknowledged: true }, [hit()])).toBeNull();
    expect(composerProblem(form, [])).toBeNull();
    expect(ACKNOWLEDGE_TEXT).toMatch(/break libraries/);
  });

  it('holds a label and notes to their limits', () => {
    const form = { label: 'x'.repeat(81), notes: '', breaking: false, acknowledged: false };

    expect(composerProblem(form, [])).toBe('A label is at most 80 characters.');
    expect(composerProblem({ ...form, label: 'ok', notes: 'n'.repeat(4001) }, [])).toBe(
      'Notes are at most 4000 characters.',
    );
  });
});

describe('the body of a publish', () => {
  it('leaves out what is blank, so the API defaults apply', () => {
    expect(
      publishBody({ label: ' ', notes: '', breaking: false, acknowledged: false }, []),
    ).toEqual({ breaking: false, acknowledge_breaking: false });
  });

  it('trims a label and notes, and carries the flags', () => {
    expect(
      publishBody({ label: ' 1.4 ', notes: ' Spring ', breaking: true, acknowledged: false }, []),
    ).toEqual({ label: '1.4', notes: 'Spring', breaking: true, acknowledge_breaking: false });
  });

  it('acknowledges what the release breaks, and then the release is breaking', () => {
    expect(
      publishBody({ label: '', notes: '', breaking: false, acknowledged: true }, [hit()]),
    ).toEqual({ breaking: true, acknowledge_breaking: true });
  });

  it('suggests the next number as the label', () => {
    expect(defaultLabel(preview())).toBe('4');
    expect(defaultLabel(preview({ release: null }))).toBe('1');
    expect(defaultLabel(null)).toBe('1');
  });
});

describe('where a library stands among the releases', () => {
  const ref = (id: string, label: string) => ({ id, number: 1, label });

  it('says which release it took and which is the latest, and whether it is behind', () => {
    expect(
      releasePlace({
        copied_at: '2026-10-02T10:00:00Z',
        synced_release: ref('r1', '1.2'),
        current_release: ref('r2', '1.4'),
      }),
    ).toEqual({ took: '1.2', latest: '1.4', behind: true });
    expect(
      releasePlace({
        copied_at: '2026-10-02T10:00:00Z',
        synced_release: ref('r2', '1.4'),
        current_release: ref('r2', '1.4'),
      })?.behind,
    ).toBe(false);
  });

  it('says nothing for a library that has not copied it, or a repository with no release', () => {
    expect(
      releasePlace({ copied_at: null, synced_release: null, current_release: ref('r2', '1.4') }),
    ).toBeNull();
    expect(
      releasePlace({
        copied_at: '2026-10-02T10:00:00Z',
        synced_release: null,
        current_release: null,
      }),
    ).toBeNull();
  });

  it('says which release a library is on, for its owner', () => {
    expect(onRelease({ copied_at: '2026-10-02T10:00:00Z', synced_release: ref('r1', '1.2') })).toBe(
      'on release 1.2',
    );
    expect(onRelease({ copied_at: null, synced_release: null })).toBeNull();
    expect(onRelease({ copied_at: '2026-10-02T10:00:00Z', synced_release: null })).toBeNull();
  });
});

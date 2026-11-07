import { describe, expect, it } from 'vitest';
import type { Bi } from '../src/lib/profile';
import { parseProfile } from '../src/lib/profile';
import { SAMPLE_PROFILE } from '../src/lib/sample-profile';
import { noticeDoc } from '../src/lib/texts/notice';
import { policyDoc } from '../src/lib/texts/policy';

const profile = parseProfile(SAMPLE_PROFILE, true);

function everyText(doc: ReturnType<typeof policyDoc>): Bi[] {
  const found: Bi[] = [doc.title];
  for (const section of doc.sections) {
    found.push(section.heading);
    for (const block of section.blocks) {
      if ('p' in block) found.push(block.p);
      else if ('ul' in block) found.push(...block.ul);
      else found.push(...block.table.head, ...block.table.rows.flat());
    }
  }
  return found;
}

describe.each([
  ['the legal notice', () => noticeDoc(profile)],
  ['the privacy policy', () => policyDoc(profile)],
])('%s', (_name, build) => {
  const doc = build();

  it('has the same text in both languages and no loose ends', () => {
    for (const text of everyText(doc)) {
      for (const lang of ['de', 'en'] as const) {
        expect(text[lang].trim(), JSON.stringify(text)).not.toBe('');
        expect(text[lang]).not.toMatch(/undefined|\[object|\bnull\b|\$\{|TODO/);
      }
    }
  });

  it('has unique section ids and rectangular tables', () => {
    const ids = doc.sections.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const section of doc.sections) {
      for (const block of section.blocks) {
        if ('table' in block) {
          for (const row of block.table.rows) expect(row.length).toBe(block.table.head.length);
        }
      }
    }
  });
});

describe('what the operator profile changes', () => {
  it('shows a tax number only when there is one', () => {
    const without = noticeDoc(profile).sections.map((s) => s.id);
    expect(without).not.toContain('tax');

    const given = parseProfile(
      {
        ...SAMPLE_PROFILE,
        operator: { ...SAMPLE_PROFILE.operator, taxId: { kind: 'vat', value: 'XX000000000' } },
      },
      true,
    );
    expect(noticeDoc(given).sections.map((s) => s.id)).toContain('tax');
  });

  it('puts the operator and every provider into the policy', () => {
    const text = JSON.stringify(policyDoc(profile));
    expect(text).toContain('Sample Operator');
    expect(text).toContain('Sample Identity Provider');
    expect(text).toContain('Sample Data Protection Authority');
  });
});

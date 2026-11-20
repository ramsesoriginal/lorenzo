import { describe, expect, it } from 'vitest';
import { backTo, type StatStep, stepText, whoLabel } from './statHistory';

const step = (stat: string, old: StatStep['old'], next: StatStep['new']): StatStep =>
  ({
    id: `${stat}-${old}-${next}`,
    stat_definition_id: stat,
    stat_name: stat,
    old,
    new: next,
    actor_id: null,
    actor_name: null,
    created_at: '2026-11-20T12:00:00Z',
  }) as StatStep;

describe('whoLabel', () => {
  it('says "you" for the viewer, else the name, else someone', () => {
    expect(whoLabel({ actor_id: 'me', actor_name: 'Ana' }, 'me')).toBe('you');
    expect(whoLabel({ actor_id: 'x', actor_name: 'Ana' }, 'me')).toBe('Ana');
    expect(whoLabel({ actor_id: null, actor_name: null }, 'me')).toBe('someone');
  });
});

describe('stepText', () => {
  it('says what a number, a removed value and a tag went from and to', () => {
    expect(stepText(step('hit_points', 16, 14))).toBe('Hit points 16 → 14');
    expect(stepText(step('Hit points', 16, null))).toBe('Hit points 16 → unset');
    expect(stepText(step('Prone', false, true))).toBe('Prone off → on');
  });
});

describe('backTo', () => {
  it('sends each stat back to what it was before the oldest step undone', () => {
    // newest first: hp 12→10, resolve 3→2, hp 14→12
    const steps = [step('hp', 12, 10), step('resolve', 3, 2), step('hp', 14, 12)];

    expect(Object.fromEntries(backTo(steps, 0))).toEqual({ hp: 12 });
    expect(Object.fromEntries(backTo(steps, 2))).toEqual({ hp: 14, resolve: 3 });
  });
});

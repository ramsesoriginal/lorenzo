import { describe, expect, it } from 'vitest';
import { byCampaign, dateWords, type HomeSession, nextSession, stateOf } from './home';

const s = (id: string, real_date: string | null, campaign = 'c1'): HomeSession => ({
  tenant_id: 't',
  id,
  name: id,
  campaign_id: campaign,
  real_date,
  can_manage: true,
});

describe('Home', () => {
  const all = [s('a', '2026-03-07'), s('b', '2026-03-21'), s('c', '2026-03-28'), s('d', null)];
  it('picks the soonest Session dated today or later as next', () => {
    expect(nextSession(all, '2026-03-14')?.id).toBe('b');
    expect(nextSession(all, '2026-03-21')?.id).toBe('b');
    expect(nextSession(all, '2026-04-01')).toBeUndefined();
  });
  it('never makes an undated Session next, and says past only for a date gone by', () => {
    const next = nextSession(all, '2026-03-14');
    expect(stateOf(all[0] as HomeSession, '2026-03-14', next)).toBe('past');
    expect(stateOf(all[1] as HomeSession, '2026-03-14', next)).toBe('next');
    expect(stateOf(all[2] as HomeSession, '2026-03-14', next)).toBeNull();
    expect(stateOf(all[3] as HomeSession, '2026-03-14', next)).toBeNull();
  });
  it('groups by campaign, the earliest first, each in date order with the undated last', () => {
    const groups = byCampaign([
      s('x', null, 'c2'),
      s('b', '2026-03-21'),
      s('a', '2026-03-07'),
      s('y', '2026-02-01', 'c2'),
    ]);
    expect(groups.map((g) => g.campaign)).toEqual(['c2', 'c1']);
    expect(groups[0]?.sessions.map((x) => x.id)).toEqual(['y', 'x']);
    expect(groups[1]?.sessions.map((x) => x.id)).toEqual(['a', 'b']);
  });
  it('says a date in its own day', () => {
    expect(dateWords('2026-03-21')).toBe('Sat 21 Mar');
    expect(dateWords(null)).toBe('Date not set');
  });
});

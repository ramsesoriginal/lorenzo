import { expect, test } from 'vitest';
import { type AppLinks, calendarDateLinks, calendarEntryHref, createLorenzoClient } from '../src';

const registry: AppLinks = {
  apps: {
    account_hub: { url: '' },
    inventory_web: { url: '' },
    beings: { url: '' },
    bench: { url: '' },
    calendars: { url: 'https://calendar.example' },
  },
  links: {
    calendar: 'https://calendar.example/calendar/?tenant={tenant}&id={id}',
    calendar_by_slug: 'https://calendar.example/calendar/?tenant={tenant}&slug={slug}',
    calendar_entry: 'https://calendar.example/entry/?tenant={tenant}&id={id}',
    calendar_entry_by_slug: 'https://calendar.example/entry/?tenant={tenant}&slug={slug}',
  },
};
test('calendar addresses prefer slugs, encode names and preserve UUID fallback', () => {
  expect(
    calendarEntryHref(registry, 'library', {
      entity_id: 'id',
      slug: 'event & name',
      kinds: ['event'],
    }),
  ).toBe('https://calendar.example/entry/?tenant=library&slug=event%20%26%20name');
  expect(calendarEntryHref(registry, 'library', { entity_id: 'id', kinds: ['calendar'] })).toBe(
    'https://calendar.example/calendar/?tenant=library&id=id',
  );
  expect(
    calendarEntryHref(registry, 'library', { entity_id: 'id', slug: 'mainland', kinds: ['clock'] }),
  ).toBe('https://calendar.example/entry/?tenant=library&slug=mainland');
  expect(
    calendarEntryHref(undefined, 'library', { entity_id: 'id', kinds: ['calendar'] }),
  ).toBeNull();
});
test('computed links batch at 100 and never materialize periods or link unresolved dates', async () => {
  const calls: Request[] = [];
  const client = createLorenzoClient({
    baseUrl: 'https://api.example',
    getAccessToken: () => 'test-token',
    fetch: async (request) => {
      calls.push(request);
      const body = (await request.json()) as { expressions: string[] };
      return new Response(
        JSON.stringify(
          body.expressions
            .filter((e) => e !== 'hidden 0')
            .map((expression) => ({
              expression,
              calendar_entity_id: 'id',
              calendar_slug: 'reckoning',
              text: '16 Quirm 3286',
              year: 3286,
              segment: 'quirm',
              day: 16,
            })),
        ),
        { headers: { 'Content-Type': 'application/json' } },
      );
    },
  });
  const result = await calendarDateLinks(client, registry, 'library', [
    ...Array.from({ length: 101 }, (_, i) => `reckoning ${i}`),
    'hidden 0',
    'reckoning 0',
  ]);
  expect(calls).toHaveLength(2);
  expect(
    calls.every((r) => r.method === 'POST' && r.url.endsWith('/calendar-references/resolve')),
  ).toBe(true);
  expect(result.has('hidden 0')).toBe(false);
  expect(result.get('reckoning 0')?.href).toContain(
    'slug=reckoning&year=3286&segment=quirm&day=16',
  );
});

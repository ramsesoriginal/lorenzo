import { randomUUID } from 'node:crypto';
import type { Schema } from '@lorenzo/api-client';
import { apiAs, ok } from './api.ts';
export async function buildWorld() {
  const subject = `calendar-owner-${randomUUID()}`;
  const api = await apiAs(subject, ['tenant_creator']);
  const me = await ok(api.GET('/me'));
  const tenant = await ok(
    api.POST('/tenants', { body: { name: `Calendar library ${randomUUID()}` } }),
  );
  const tenantId = tenant.id;
  const names = [
    'Rimsep',
    'Sogmen',
    'Temez',
    'Nordtage',
    'Querm',
    'Quirm',
    'Emsest',
    'Osttage',
    'Pestmen',
    'Vamoten',
    'Nesem',
    'Südtage',
    'Idemic',
    'Nunumde',
    'Dedomde',
    'Westtage',
    'Retedem',
    'Kameste',
    'Sprungfest',
  ];
  const definition: Schema<'CalendarDefinition-Input'> = {
    format: 'lorenzo.calendar/1',
    segments: names.map((name, i) => ({
      key: `segment-${i + 1}`,
      name,
      days: [3, 7, 11, 15].includes(i) ? 2 : i === 18 ? 1 : 27,
      kind: 'month',
      in_week: true,
      when: null,
    })),
    week: {
      length: 7,
      names: ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'],
      reset: 'never',
      reference: { year: 3286, segment: 'segment-1', day: 1 },
      weekday: 4,
    },
    moons: [
      {
        key: 'maira',
        name: 'Maira',
        period: '14',
        reference: { year: 3286, segment: 'segment-1', day: 1 },
        offset: String((((1 - (3286 * 387 + 4)) % 14) + 14) % 14),
      },
      {
        key: 'mendra',
        name: 'Mendra',
        period: '23',
        reference: { year: 3286, segment: 'segment-1', day: 1 },
        offset: String(((-(3286 * 387 + 4) % 23) + 23) % 23),
      },
      {
        key: 'galon',
        name: 'Galon',
        period: '42',
        reference: { year: 3286, segment: 'segment-1', day: 1 },
        offset: String(((-(3286 * 387 + 4) % 42) + 42) % 42),
      },
    ],
  };
  const document: Schema<'CalendarDocument-Input'> = {
    format: 'lorenzo.calendar-document/1',
    source_key: 'isles',
    name: 'Isles calendar',
    definition,
    is_public: true,
    period_is_public: true,
    warnings: [],
    annotations: [
      {
        key: 'diary',
        date: { year: 3286, segment: 'segment-6', day: 16 },
        text: 'A lantern was lit by the harbour.',
        original_text: 'A lantern was lit by the harbour.',
        classification: 'note',
        is_public: false,
        information_is_public: true,
      },
      {
        key: 'storm',
        date: { year: 3286, segment: 'segment-6', day: 17 },
        text: 'A storm reaches the harbour.',
        original_text: 'A storm reaches the harbour.',
        title: 'Harbour storm',
        classification: 'event',
        is_public: true,
        information_is_public: false,
      },
      {
        key: 'feast',
        date: { year: 3286, segment: 'segment-6', day: 18 },
        text: 'The annual feast.',
        original_text: 'The annual feast.',
        title: 'Harbour feast',
        classification: 'observance',
        recurrence: { segment: 'segment-6', day: 18, when: { every: 1, offset: 0 } },
        is_public: true,
        information_is_public: true,
      },
    ],
  };
  const plan = await ok(
    api.POST('/tenants/{tenant_id}/calendar-imports/plan', {
      params: { path: { tenant_id: tenantId } },
      body: { document },
    }),
  );
  const receipt = await ok(
    api.POST('/tenants/{tenant_id}/calendar-imports', {
      params: { path: { tenant_id: tenantId } },
      body: { document, token: plan.token },
    }),
  );
  const calendarId = receipt.calendar_entity_id;
  const readerSubject = `calendar-reader-${randomUUID()}`;
  const reader = await apiAs(readerSubject);
  const readerMe = await ok(reader.GET('/me'));
  const campaign = await ok(
    api.POST('/tenants/{tenant_id}/campaigns', {
      params: { path: { tenant_id: tenantId } },
      body: {
        name: 'Harbour campaign',
        game_system: 'Homebrew',
        slug: 'harbour',
        description: '',
        secret: false,
      },
    }),
  );
  await ok(
    api.POST('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
      params: { path: { tenant_id: tenantId, campaign_id: campaign.id } },
      body: { user_id: readerMe.id },
    }),
  );
  return { api, subject, tenantId, calendarId, definition, readerSubject, reader, ownerId: me.id };
}

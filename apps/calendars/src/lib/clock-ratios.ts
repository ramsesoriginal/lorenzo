import type { Schema } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { clockEditor, formatReading } from './clocks';
import { button, check, disclosure, el, entryHref, field, linkButton, select } from './dom';

type Converted = Schema<'ClockConversionOut'>;

function conversionView(tenant: string, result: Converted): HTMLElement {
  const host = el('div', '', 'card card-body stack-tight');
  const labels = {
    entered: 'Entered',
    derived: 'Derived',
    not_reckoned: 'Not reckoned',
    conflicting: 'Conflicting',
    limit_reached: 'Limit reached',
  };
  host.append(el('h3', labels[result.status], 'item-title'));
  if (result.reading) host.append(el('p', formatReading(result.reading)));
  if (result.status === 'not_reckoned')
    host.append(el('p', 'No reading can be reckoned from the records available to you.', 'lede'));
  if (result.status === 'conflicting')
    host.append(
      el(
        'p',
        'Recorded readings or declared relationships disagree. Entered readings are kept.',
        'lede',
      ),
    );
  if (result.status === 'limit_reached')
    host.append(
      el(
        'p',
        'This conversion exceeds the supported size or precision. No reading was guessed.',
        'lede',
      ),
    );
  for (const candidate of result.candidates) {
    const source = el('div', '', 'stack-tight');
    source.append(
      linkButton(
        candidate.source_clock_name,
        entryHref(tenant, candidate.source_clock_id),
        'kind-clock',
      ),
      el('p', `${formatReading(candidate.source_reading)} → ${formatReading(candidate.reading)}`),
    );
    for (const step of candidate.path)
      source.append(
        el('p', `${step.source_clock_name} → ${step.target_clock_name} · ${step.ratio}`, 'caption'),
      );
    host.append(source);
  }
  for (const path of result.conflict_paths) {
    if (path.length)
      host.append(
        el(
          'p',
          `Conflicting path: ${path.map((s) => `${s.source_clock_name} → ${s.target_clock_name}`).join('; ')}`,
          'caption',
        ),
      );
  }
  return host;
}

export async function clockRelationships(tenant: string, clockId: string, name: string) {
  const ui = clockEditor('Clock relationships and conversion');
  const path = { tenant_id: tenant, clock_id: clockId };
  const own = await unwrap(
    await client.GET('/tenants/{tenant_id}/clocks/{clock_id}', { params: { path } }),
  );
  if (!own.ticking) {
    ui.add(el('p', 'Timeless clocks have no ratios or readings.', 'caption'));
    return ui.host;
  }
  let version = '';
  let edit: ((row: Schema<'ClockRelationshipOut'>) => void) | null = null;
  async function read(fresh = false) {
    const result = await client.GET('/tenants/{tenant_id}/clocks/{clock_id}/relationships', {
      params: { path },
      cache: fresh ? 'no-store' : 'default',
    });
    const data = await unwrap(result);
    version = result.response.headers.get('etag') ?? '';
    ui.list.replaceChildren();
    for (const row of data.items) {
      const li = el('li');
      const text = el('div', '', 'stack-tight grow');
      text.append(
        el(
          'p',
          `${name}: ${row.ratio} days per day on ${row.reference_clock_name}. ${row.is_shared ? 'Shared' : 'Private'}.`,
        ),
        el(
          'p',
          row.clock_anchor == null
            ? 'Duration conversion only; no anchor is recorded.'
            : `${name} ${row.clock_anchor} coincides with ${row.reference_clock_name} ${row.reference_anchor}.`,
          'caption',
        ),
      );
      const actions = el('div', '', 'row-tight');
      actions.append(
        linkButton(
          row.reference_clock_name,
          entryHref(tenant, row.reference_clock_entity_id),
          'kind-clock',
        ),
      );
      if (data.can_manage)
        actions.append(
          button(
            'Edit relationship',
            () => {
              edit?.(row);
            },
            true,
            'edit',
          ),
          button(
            'Remove relationship',
            () =>
              ui.run(async () => {
                await unwrap(
                  await client.DELETE(
                    '/tenants/{tenant_id}/clocks/{clock_id}/relationships/{reference_id}',
                    {
                      params: {
                        path: { ...path, reference_id: row.reference_clock_entity_id },
                        header: { 'if-match': version },
                      },
                    },
                  ),
                );
                await read();
                ui.status.say('Relationship removed. Entered readings were kept.');
              }),
            true,
            'delete',
          ),
        );
      li.append(text, actions);
      ui.list.append(li);
    }
    if (!data.items.length)
      ui.list.append(el('li', 'No permitted clock relationships recorded.', 'caption'));
    return data.can_manage;
  }
  const canManage = await read();
  const clocks = (
    await unwrap(
      await client.GET('/tenants/{tenant_id}/clocks', { params: { path: { tenant_id: tenant } } }),
    )
  ).filter((c) => c.ticking && c.entity_id !== clockId);
  if (!clocks.length) {
    ui.add(el('p', 'Another ticking clock is needed to declare a relationship.', 'caption'));
    return ui.host;
  }
  if (canManage) {
    const reference = select(
      'Reference clock',
      clocks.map((c) => [c.entity_id, c.name]),
      clocks[0]?.entity_id ?? '',
    );
    const ratio = field('Days on this clock per reference day', '2');
    const anchored = check('Anchor the readings');
    const clockAnchor = field('This clock reads', '0');
    const referenceAnchor = field('Reference clock reads', '0');
    const anchors = el('div', '', 'toolbar');
    anchors.append(clockAnchor.label, referenceAnchor.label);
    anchors.hidden = true;
    anchored.input.addEventListener('change', () => {
      anchors.hidden = !anchored.input.checked;
    });
    const shared = check('Share relationship with readers of both clocks');
    const previewValue = field('Reference reading or duration to preview', '6');
    const preview = el('p', '', 'status-text');
    preview.setAttribute('role', 'status');
    const values = () => ({
      ratio: ratio.input.value,
      clock_anchor: anchored.input.checked ? clockAnchor.input.value : null,
      reference_anchor: anchored.input.checked ? referenceAnchor.input.value : null,
    });
    edit = (row) => {
      reference.input.value = row.reference_clock_entity_id;
      ratio.input.value = row.ratio;
      anchored.input.checked = row.clock_anchor != null;
      anchors.hidden = !anchored.input.checked;
      clockAnchor.input.value = row.clock_anchor ?? '0';
      referenceAnchor.input.value = row.reference_anchor ?? '0';
      shared.input.checked = row.is_shared;
    };
    const actions = el('div', '', 'row');
    actions.append(
      button(
        'Preview relationship',
        () =>
          ui.run(async () => {
            const result = await unwrap(
              await client.POST('/tenants/{tenant_id}/clocks/{clock_id}/relationship-preview', {
                params: { path },
                body: {
                  ...values(),
                  reference_clock_entity_id: reference.input.value,
                  reading: {
                    lo: previewValue.input.value,
                    hi: previewValue.input.value,
                    lo_inclusive: true,
                    hi_inclusive: true,
                  },
                },
              }),
            );
            preview.textContent = `${name}: ${formatReading(result.reading)} (${result.kind === 'duration' ? 'duration' : 'reading'}). Preview only.`;
            ui.status.say('Relationship previewed. No records were changed.');
          }),
        true,
        'visibility',
      ),
      button(
        'Save relationship',
        () =>
          ui.run(async () => {
            await unwrap(
              await client.PUT(
                '/tenants/{tenant_id}/clocks/{clock_id}/relationships/{reference_id}',
                {
                  params: {
                    path: { ...path, reference_id: reference.input.value },
                    header: { 'if-match': version },
                  },
                  body: { ...values(), is_shared: shared.input.checked },
                },
              ),
            );
            await read();
            ui.status.say('Relationship saved. Entered readings and story order were kept.');
          }),
        false,
        'save',
      ),
      button(
        'Refresh saved relationships',
        () =>
          ui.run(async () => {
            await read(true);
            ui.status.say('Saved relationships refreshed. Your draft is kept.');
          }),
        true,
        'refresh',
      ),
    );
    ui.add(
      el(
        'p',
        'A ratio converts durations. An anchor also lets it convert absolute readings. Negative ratios describe clocks running in opposite directions.',
        'caption',
      ),
      reference.label,
      ratio.label,
      anchored.label,
      anchors,
      shared.label,
      previewValue.label,
      preview,
      actions,
    );
  }
  const converter = disclosure('Convert a reading or duration');
  const target = select(
    'Convert to clock',
    clocks.map((c) => [c.entity_id, c.name]),
    clocks[0]?.entity_id ?? '',
  );
  const kind = select(
    'Convert',
    [
      ['reading', 'Reading'],
      ['duration', 'Duration'],
    ],
    'reading',
  );
  const value = field('Reading or duration on this clock', '0');
  const output = el('div', '', 'stack');
  converter.body.append(
    target.label,
    kind.label,
    value.label,
    button(
      'Convert value',
      () =>
        ui.run(async () => {
          const result = await unwrap(
            await client.POST('/tenants/{tenant_id}/clock-conversions', {
              params: { path: { tenant_id: tenant } },
              body: {
                source_clock_id: clockId,
                target_clock_id: target.input.value,
                kind: kind.input.value as 'reading' | 'duration',
                reading: {
                  lo: value.input.value,
                  hi: value.input.value,
                  lo_inclusive: true,
                  hi_inclusive: true,
                },
              },
            }),
          );
          output.replaceChildren(conversionView(tenant, result));
          ui.status.say('Conversion shown. No reading was recorded.');
        }),
      false,
      'compare',
    ),
    output,
  );
  ui.add(converter.root);
  return ui.host;
}

export async function eventClockConversions(tenant: string, eventId: string) {
  const ui = clockEditor('Read this Event on another clock');
  const clocks = (
    await unwrap(
      await client.GET('/tenants/{tenant_id}/clocks', { params: { path: { tenant_id: tenant } } }),
    )
  ).filter((c) => c.ticking);
  if (!clocks.length) {
    ui.add(el('p', 'No ticking clocks are available here.', 'caption'));
    return ui.host;
  }
  const target = select(
    'Read on clock',
    clocks.map((c) => [c.entity_id, c.name]),
    clocks[0]?.entity_id ?? '',
  );
  const output = el('div', '', 'stack');
  ui.add(
    target.label,
    button(
      'Show clock reading',
      () =>
        ui.run(async () => {
          const result = await unwrap(
            await client.GET(
              '/tenants/{tenant_id}/events/{event_id}/clock-readings/{clock_id}/derived',
              {
                params: {
                  path: { tenant_id: tenant, event_id: eventId, clock_id: target.input.value },
                },
                cache: 'no-store',
              },
            ),
          );
          output.replaceChildren(conversionView(tenant, result));
          ui.status.say('Reading shown from the records available to you.');
        }),
      false,
      'kind-clock',
    ),
    output,
  );
  return ui.host;
}

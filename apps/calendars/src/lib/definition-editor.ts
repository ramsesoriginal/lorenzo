import { client, LorenzoApiError, unwrap } from './api';
import { button, calendarHref, check, el, field, message, select } from './dom';
import type { Calendar, DateValue, Definition, Segment } from './types';
export function definitionEditor(tenantId: string, original?: Calendar): HTMLElement {
  const form = el('form', '', 'stack');
  const status = el('p', '', 'draft-status');
  status.setAttribute('role', 'status');
  const name = field('Calendar name', original?.name ?? '');
  name.input.required = true;
  const publicGate = check('Everyone in this library can know this calendar exists', false);
  if (!original) form.append(name.label, publicGate.label);
  const year = field(
    'Preview year',
    String(
      original?.definition.week?.reference.year ??
        original?.definition.moons[0]?.reference.year ??
        0,
    ),
    'number',
  );
  year.input.min = '-1000000';
  year.input.max = '1000000';
  form.append(year.label);
  let version = original ? `W/"${original.updated_at}"` : '';
  let acceptedPreview = '';
  let blocked = false;
  const segments = el('fieldset');
  segments.append(el('legend', 'Months and festivals'));
  const rows = el('div', '', 'stack-tight');
  segments.append(rows);
  form.append(segments);
  const segmentReaders: Array<{ node: HTMLElement; read: () => Segment }> = [];
  function addSegment(value?: Segment) {
    const key = value?.key ?? `segment-${crypto.randomUUID()}`;
    const row = el('div', '', 'segment-row stack-tight');
    const n = field('Segment name', value?.name ?? '');
    n.input.required = true;
    const days = field('Days', String(value?.days ?? 1), 'number');
    days.input.min = '1';
    days.input.max = '1000';
    days.input.required = true;
    const kind = select(
      'Counts as',
      [
        ['month', 'Month'],
        ['festival', 'Festival (outside month numbering)'],
      ],
      value?.kind ?? 'month',
    );
    const inWeek = check('Advances the week', value?.in_week ?? true);
    const every = field('Appears every N years', String(value?.when?.every ?? 1), 'number');
    every.input.min = '1';
    every.input.max = '1000';
    const offset = field('Year offset', String(value?.when?.offset ?? 0), 'number');
    const advanced = el('details');
    advanced.append(el('summary', 'Week and leap rule'), inWeek.label, every.label, offset.label);
    const controls = el('div', '', 'row');
    const record = {
      node: row,
      read: () => ({
        key,
        name: n.input.value,
        days: Number(days.input.value),
        kind: kind.input.value as Segment['kind'],
        in_week: inWeek.input.checked,
        when:
          Number(every.input.value) === 1
            ? null
            : { every: Number(every.input.value), offset: Number(offset.input.value) },
      }),
    };
    controls.append(
      button(
        'Move earlier',
        () => {
          const i = segmentReaders.indexOf(record);
          if (i > 0) {
            const before = segmentReaders[i - 1];
            if (before) {
              rows.insertBefore(row, before.node);
              segmentReaders.splice(i, 1);
              segmentReaders.splice(i - 1, 0, record);
              invalidate();
            }
          }
        },
        true,
      ),
      button(
        'Remove segment',
        () => {
          segmentReaders.splice(segmentReaders.indexOf(record), 1);
          row.remove();
          invalidate();
        },
        true,
      ),
    );
    row.append(n.label, days.label, kind.label, advanced, controls);
    segmentReaders.push(record);
    rows.append(row);
  }
  for (const s of original?.definition.segments ?? []) addSegment(s);
  if (!original) addSegment();
  segments.append(
    button(
      'Add month or festival',
      () => {
        addSegment();
        invalidate();
      },
      true,
    ),
  );
  const week = el('details');
  week.append(el('summary', 'Weeks'));
  const enabled = check('Use a week', Boolean(original?.definition.week));
  const length = field('Days in a week', String(original?.definition.week?.length ?? 7), 'number');
  length.input.min = '1';
  length.input.max = '100';
  const names = field('Weekday names (one per line)');
  const namesArea = el('textarea');
  namesArea.value = original?.definition.week?.names?.join('\n') ?? '';
  names.label.replaceChildren(
    document.createTextNode('Weekday names (one per line; leave blank for numbers)'),
    namesArea,
  );
  const reset = select(
    'The week',
    [
      ['never', 'Continues across segments and years'],
      ['segment', 'Restarts with each segment'],
    ],
    original?.definition.week?.reset ?? 'never',
  );
  const weekday = field(
    'Weekday at the reference date (first day is 1)',
    String((original?.definition.week?.weekday ?? 0) + 1),
    'number',
  );
  weekday.input.min = '1';
  function reference(host: HTMLElement, value?: DateValue) {
    const y = field('Reference year', String(value?.year ?? 0), 'number');
    const s = select('Reference segment', [], value?.segment ?? '');
    const d = field('Reference day', String(value?.day ?? 1), 'number');
    d.input.min = '1';
    let selected = value?.segment ?? '';
    const refresh = () => {
      selected = s.input.value || selected;
      s.input.replaceChildren();
      for (const r of segmentReaders) {
        const segment = r.read();
        const o = el('option', segment.name || 'Unnamed segment');
        o.value = segment.key;
        s.input.append(o);
      }
      if ([...s.input.options].some((o) => o.value === selected)) s.input.value = selected;
    };
    s.input.addEventListener('focus', refresh);
    refresh();
    host.append(y.label, s.label, d.label);
    return () => ({
      year: Number(y.input.value),
      segment: s.input.value,
      day: Number(d.input.value),
    });
  }
  week.append(enabled.label, length.label, names.label, reset.label, weekday.label);
  const weekReference = reference(week, original?.definition.week?.reference);
  form.append(week);
  const moons = el('details');
  moons.append(el('summary', 'Moons'));
  const moonRows = el('div', '', 'stack');
  moons.append(moonRows);
  form.append(moons);
  const moonReaders: Array<{ node: HTMLElement; read: () => Definition['moons'][number] }> = [];
  function addMoon(value?: Definition['moons'][number]) {
    const row = el('fieldset');
    row.append(el('legend', 'Moon'));
    const n = field('Moon name', value?.name ?? '');
    n.input.required = true;
    const period = field('Cycle in days', value?.period ?? '');
    period.input.required = true;
    period.input.inputMode = 'decimal';
    const offset = field('Days from reference to new moon', value?.offset ?? '0');
    offset.input.inputMode = 'decimal';
    row.append(n.label, period.label, offset.label);
    const ref = reference(row, value?.reference);
    const key = value?.key ?? `moon-${crypto.randomUUID()}`;
    const record = {
      node: row,
      read: () => ({
        key,
        name: n.input.value,
        period: period.input.value,
        offset: offset.input.value,
        reference: ref(),
      }),
    };
    moonReaders.push(record);
    row.append(
      button(
        'Remove moon',
        () => {
          moonReaders.splice(moonReaders.indexOf(record), 1);
          row.remove();
          invalidate();
        },
        true,
      ),
    );
    moonRows.append(row);
  }
  for (const moon of original?.definition.moons ?? []) addMoon(moon);
  moons.append(
    button(
      'Add moon',
      () => {
        addMoon();
        invalidate();
      },
      true,
    ),
  );
  const read = (): Definition => ({
    format: 'lorenzo.calendar/1',
    segments: segmentReaders.map((r) => r.read()),
    week: enabled.input.checked
      ? {
          length: Number(length.input.value),
          names: namesArea.value.trim() ? namesArea.value.split('\n').map((n) => n.trim()) : null,
          reset: reset.input.value as 'never' | 'segment',
          reference: weekReference(),
          weekday: Number(weekday.input.value) - 1,
        }
      : null,
    moons: moonReaders.map((r) => r.read()),
  });
  const preview = el('div', '', 'panel');
  preview.hidden = true;
  const save = el('button', original ? 'Save definition' : 'Create calendar', 'btn');
  save.type = 'submit';
  save.disabled = true;
  function invalidate() {
    acceptedPreview = '';
    save.disabled = true;
    preview.hidden = true;
  }
  form.addEventListener('input', invalidate);
  form.addEventListener('change', invalidate);
  const previewButton = button(
    'Preview this year',
    async () => {
      if (!form.reportValidity()) return;
      status.textContent = 'Calculating…';
      try {
        const definition = read();
        const result = await unwrap(
          await client.POST('/tenants/{tenant_id}/calendars/preview', {
            params: { path: { tenant_id: tenantId }, query: { year: Number(year.input.value) } },
            body: definition,
          }),
        );
        acceptedPreview = JSON.stringify({ definition, year: year.input.value });
        preview.replaceChildren(el('h3', `Year ${result.year}`));
        for (const s of result.segments)
          preview.append(
            el(
              'p',
              `${s.name}: ${s.days.length} days${s.month_ordinal === null ? ' (festival)' : ` · month ${s.month_ordinal}`}`,
            ),
          );
        preview.hidden = false;
        status.textContent = 'Preview ready. Your draft has not been saved.';
        save.disabled = blocked;
      } catch (e) {
        status.textContent = message(e);
        save.disabled = true;
      }
    },
    true,
  );
  const actions = el('div', '', 'row');
  actions.append(previewButton, save);
  form.append(actions, status, preview);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (blocked || !form.reportValidity()) return;
    const definition = read();
    if (acceptedPreview !== JSON.stringify({ definition, year: year.input.value })) {
      invalidate();
      status.textContent = 'Preview your changes before saving.';
      return;
    }
    save.disabled = true;
    status.textContent = 'Saving…';
    try {
      if (original) {
        const result = await client.PUT('/tenants/{tenant_id}/calendars/{entity_id}/definition', {
          params: {
            path: { tenant_id: tenantId, entity_id: original.entity_id },
            header: { 'if-match': version },
          },
          body: definition,
        });
        await unwrap(result);
        if (form.isConnected) location.reload();
      } else {
        const created = await unwrap(
          await client.POST('/tenants/{tenant_id}/calendars', {
            params: { path: { tenant_id: tenantId } },
            body: {
              id: createId,
              name: name.input.value,
              definition,
              is_public: publicGate.input.checked,
            },
          }),
        );
        if (form.isConnected)
          location.assign(calendarHref(tenantId, created.entity_id, Number(year.input.value)));
      }
    } catch (e) {
      status.textContent = message(e);
      save.disabled = false;
      if (!original) {
        try {
          const existing = await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: createId } },
          });
          if (existing.data) {
            status.replaceChildren(
              document.createTextNode('The calendar was saved. '),
              button(
                'Open saved calendar',
                () => location.assign(calendarHref(tenantId, createId, Number(year.input.value))),
                true,
              ),
            );
            save.disabled = true;
            return;
          }
        } catch {
          /* The same id is retained for a later retry. */
        }
      }
      if (e instanceof LorenzoApiError && e.status === 412 && original) {
        blocked = true;
        save.disabled = true;
        try {
          const current = await unwrap(
            await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
              params: { path: { tenant_id: tenantId, entity_id: original.entity_id } },
            }),
          );
          const review = el('details');
          review.append(
            el('summary', 'Review the saved definition'),
            el('pre', JSON.stringify(current.definition, null, 2)),
          );
          review.open = true;
          review.append(
            button(
              'I reviewed it; keep my draft against this version',
              () => {
                version = `W/"${current.updated_at}"`;
                blocked = false;
                invalidate();
                status.textContent = 'Your draft is kept. Preview it again before saving.';
                review.remove();
              },
              true,
            ),
          );
          form.append(review);
          status.textContent =
            'Someone changed this calendar. Your draft is still here. Review the saved definition before trying again.';
        } catch (readError) {
          status.textContent = `${message(readError)} Your draft is kept; the saved definition could not be loaded. Copy your draft before reloading.`;
        }
      }
    }
  });
  const createId = crypto.randomUUID();
  return form;
}

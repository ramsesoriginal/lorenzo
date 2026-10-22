import { client, LorenzoApiError, unwrap } from './api';
import {
  button,
  calendarHref,
  check,
  disclosure,
  el,
  feedback,
  field,
  message,
  select,
  submit,
  textarea,
} from './dom';
import type { Calendar, DateValue, Definition, Segment } from './types';

export function definitionEditor(tenantId: string, original?: Calendar): HTMLElement {
  const form = el('form', '', 'stack');
  const status = feedback();
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
  year.label.classList.add('narrow-field');
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
    const advanced = disclosure('Week and leap rule');
    const recurrence = el('div', '', 'form-grid');
    recurrence.append(every.label, offset.label);
    advanced.body.append(inWeek.label, recurrence);
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
        'up',
      ),
      button(
        'Remove segment',
        () => {
          segmentReaders.splice(segmentReaders.indexOf(record), 1);
          row.remove();
          invalidate();
        },
        true,
        'close',
      ),
    );
    const fields = el('div', '', 'form-grid');
    fields.append(n.label, days.label, kind.label);
    row.append(fields, advanced.root, controls);
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
      'add',
    ),
  );
  const week = disclosure('Weeks');
  const enabled = check('Use a week', Boolean(original?.definition.week));
  const length = field('Days in a week', String(original?.definition.week?.length ?? 7), 'number');
  length.input.min = '1';
  length.input.max = '100';
  const names = textarea(
    'Weekday names (one per line; leave blank for numbers)',
    original?.definition.week?.names?.join('\n') ?? '',
  );
  const namesArea = names.input;
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
    const grid = el('div', '', 'form-grid');
    grid.append(y.label, s.label, d.label);
    host.append(grid);
    return () => ({
      year: Number(y.input.value),
      segment: s.input.value,
      day: Number(d.input.value),
    });
  }
  const weekFields = el('div', '', 'form-grid');
  weekFields.append(length.label, reset.label, weekday.label);
  week.body.append(enabled.label, weekFields, names.label);
  const weekReference = reference(week.body, original?.definition.week?.reference);
  form.append(week.root);
  const moons = disclosure('Moons');
  const moonRows = el('div', '', 'stack');
  moons.body.append(moonRows);
  form.append(moons.root);
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
    const fields = el('div', '', 'form-grid');
    fields.append(n.label, period.label, offset.label);
    row.append(fields);
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
        'close',
      ),
    );
    moonRows.append(row);
  }
  for (const moon of original?.definition.moons ?? []) addMoon(moon);
  moons.body.append(
    button(
      'Add moon',
      () => {
        addMoon();
        invalidate();
      },
      true,
      'add',
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
  const preview = el('div', '', 'card card-body stack-tight');
  preview.hidden = true;
  const save = submit(original ? 'Save definition' : 'Create calendar');
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
      status.busy('Calculating…');
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
        status.say('Preview ready. Your draft has not been saved.');
        save.disabled = blocked;
      } catch (e) {
        status.fail(message(e));
        save.disabled = true;
      }
    },
    true,
  );
  const actions = el('div', '', 'row');
  actions.append(previewButton, save);
  form.append(actions, status.node, preview);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (blocked || !form.reportValidity()) return;
    const definition = read();
    if (acceptedPreview !== JSON.stringify({ definition, year: year.input.value })) {
      invalidate();
      status.fail('Preview your changes before saving.');
      return;
    }
    save.disabled = true;
    status.busy('Saving…');
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
      status.fail(message(e));
      save.disabled = false;
      if (!original) {
        try {
          const existing = await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: createId } },
          });
          if (existing.data) {
            status.say('The calendar was saved.');
            status.node.append(
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
          const review = disclosure('Review the saved definition');
          review.body.append(
            el('pre', JSON.stringify(current.definition, null, 2)),
            button(
              'I reviewed it; keep my draft against this version',
              () => {
                version = `W/"${current.updated_at}"`;
                blocked = false;
                invalidate();
                status.say('Your draft is kept. Preview it again before saving.');
                review.root.remove();
              },
              true,
            ),
          );
          review.root.open = true;
          form.append(review.root);
          status.fail(
            'Someone changed this calendar. Your draft is still here. Review the saved definition before trying again.',
          );
        } catch (readError) {
          status.fail(
            `${message(readError)} Your draft is kept; the saved definition could not be loaded. Copy your draft before reloading.`,
          );
        }
      }
    }
  });
  const createId = crypto.randomUUID();
  return form;
}

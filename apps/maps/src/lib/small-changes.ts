// What a phone can change on a Map (MP2, screen 31): drawing needs a larger window, so it offers the
// small changes that need no pointer on the sheet: the name, who may see the Map, and where a pin is,
// by its numbers. Each is the same write the larger window makes, and a refusal is shown as it is given.
import { client, unwrap } from './api';
import { actions, button, el, field, say, statusLine } from './dom';
import type { Header, Row } from './map-api';
import { putPlacement, rowState } from './map-api';

type Point = { shape: 'point'; at: [number, number] };

/** The pin the selection is, or null: only a single point can be moved by two numbers. */
export function pinOf(row: Row | undefined): Point | null {
  const parts = (row?.geometry as { parts?: Point[] } | undefined)?.parts;
  const only = parts?.length === 1 ? parts[0] : undefined;

  return only?.shape === 'point' ? only : null;
}

export function smallChanges(options: {
  tenant: string;
  header: Header;
  version: string;
  selected: () => Row | undefined;
  /** Draws the page again after a write. */
  again: () => Promise<void>;
  /** Puts this away. */
  back: () => void;
}) {
  const { tenant, header, version } = options;
  const root = el('div', '', 'card card-body stack map-small');
  root.append(
    el('h2', 'Drawing needs a larger window', 'map-small-title'),
    el('p', 'On a phone you can read every Map, and make small changes.', 'status-text'),
  );
  const name = field('Name', header.name);
  name.input.required = true;
  const open = field('Open to everyone in this library', '', 'checkbox');
  open.input.checked = header.is_public === true;
  const moveLabel = el('p', '', 'status-text');
  const x = field('x', '', 'number');
  const y = field('y', '', 'number');
  x.input.step = y.input.step = 'any';
  const fill = () => {
    const pin = pinOf(options.selected());
    moveLabel.textContent = pin
      ? `Move “${options.selected()?.name}” (x, y)`
      : 'Choose a pin on the Map to move it by its numbers.';
    x.input.disabled = y.input.disabled = !pin;
    x.input.value = pin ? String(pin.at[0]) : '';
    y.input.value = pin ? String(pin.at[1]) : '';
  };
  fill();
  const status = statusLine();
  const save = button(
    'Save',
    async () => {
      const entity = { tenant_id: tenant, entity_id: header.id };
      try {
        if (name.input.value.trim() && name.input.value.trim() !== header.name)
          await unwrap(
            await client.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: entity },
              headers: { 'If-Match': version },
              body: { name: name.input.value.trim() },
            }),
          );
        if (open.input.checked !== (header.is_public === true)) {
          const current = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
            params: { path: entity },
          });
          const audience = await unwrap(current);
          await unwrap(
            await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
              params: { path: entity },
              headers: { 'If-Match': current.response.headers.get('etag') ?? '' },
              body: { ...audience, is_public: open.input.checked },
            }),
          );
        }
        const row = options.selected();
        const pin = pinOf(row);
        if (row && pin && !x.input.disabled) {
          const to: [number, number] = [Number(x.input.value), Number(y.input.value)];
          if (to[0] !== pin.at[0] || to[1] !== pin.at[1])
            await putPlacement(tenant, header.id, row.id, {
              ...rowState(row),
              geometry: { ...(row.geometry as object), parts: [{ ...pin, at: to }] },
            });
        }
        await options.again();
      } catch (error) {
        say(
          status,
          `${error instanceof Error ? error.message : 'It was not saved.'} Your change is still here.`,
          true,
        );
      }
    },
    { variant: 'primary' },
  );
  const back = el('button', 'Back to the Map', 'btn btn-secondary');
  back.type = 'button';
  back.addEventListener('click', options.back);
  const numbers = el('div', '', 'row-tight');
  numbers.append(x.label, y.label);
  root.append(name.label, open.label, moveLabel, numbers, actions(save, back), status);

  return { root, refresh: fill };
}

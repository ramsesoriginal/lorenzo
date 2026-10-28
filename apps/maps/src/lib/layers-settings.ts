// The pictures under a Map, for those who may write (ADR 0362): add one, set where it lies, order
// them, replace one, say it was reviewed and remove one. The API decides every write; a refusal is
// shown as it is given.
import { client, LorenzoApiError, unwrap } from './api';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';
import {
  actions,
  button,
  card,
  el,
  empty,
  field,
  groupTitle,
  message,
  say,
  select,
  statusLine,
  submit,
} from './dom';
import type { LayerOut } from './layer-pictures';
import type { Header } from './map-api';

type Anchor = { image: [number, number]; at: [number, number] };
type Calibration = { anchors: Anchor[] } | null;

const PICTURE_TYPES = 'image/png,image/jpeg,image/webp,image/gif,image/svg+xml';

/** What a layer is sent as. */
type Item = {
  information_id: string;
  calibration: Calibration;
  opacity: number | null;
  reviewed: boolean;
};

const asItem = (layer: LayerOut): Item => ({
  information_id: layer.information_id,
  calibration: (layer.calibration ?? null) as Calibration,
  opacity: layer.opacity ?? null,
  reviewed: false,
});

/** An error body's own sentence, as the API gave it. */
async function failure(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return new Error(body.detail);
  } catch {
    // Not JSON: the status says enough.
  }
  return new Error(`The picture was refused (${response.status}).`);
}

async function upload(tenant: string, information: string, file: File): Promise<string> {
  const data = new FormData();
  data.set('file', file);
  const response = await fetch(
    `${API_BASE_URL}/tenants/${tenant}/information/${information}/payloads`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${await getAccessToken()}` },
      body: data,
    },
  );
  if (!response.ok) throw await failure(response);
  return ((await response.json()) as { id: string }).id;
}

async function removeInformation(tenant: string, information: string): Promise<void> {
  const current = await client.GET('/tenants/{tenant_id}/information/{information_id}', {
    params: { path: { tenant_id: tenant, information_id: information } },
    cache: 'no-cache',
  });
  await unwrap(current);
  await client.DELETE('/tenants/{tenant_id}/information/{information_id}', {
    params: { path: { tenant_id: tenant, information_id: information } },
    headers: { 'If-Match': current.response.headers.get('etag') ?? '' },
  });
}

export function picturesSection(context: {
  tenant: string;
  header: Header;
  version: string;
  again: () => Promise<void>;
}) {
  const { tenant, header, version, again } = context;
  const wrap = el('div', '', 'stack');

  /** Writes the list as it is to be, then draws the page again. */
  // The Map's version is read just before a write: adding the Information may have moved it.
  const put = async (list: Item[]) => {
    const current = await client.GET('/tenants/{tenant_id}/maps/{map_id}', {
      params: { path: { tenant_id: tenant, map_id: header.id } },
      cache: 'no-cache',
    });
    await unwrap(current);
    await unwrap(
      await client.PUT('/tenants/{tenant_id}/maps/{map_id}/layers', {
        params: { path: { tenant_id: tenant, map_id: header.id } },
        headers: { 'If-Match': current.response.headers.get('etag') ?? version },
        body: { layers: list },
      }),
    );
  };
  const write = async (list: Item[]) => {
    await put(list);
    await again();
  };
  const layers = header.layers ?? [];
  const items = layers.map(asItem);

  wrap.append(
    el(
      'p',
      'A picture is drawn under the places. It is a picture of this Map, seen by those who may see it.',
      'status-text',
    ),
  );
  if (layers.length === 0) wrap.append(empty('No pictures under this Map yet.'));

  layers.forEach((layer, index) => {
    const box = el('fieldset', '', 'card card-body stack-tight');
    box.append(el('legend', layer.title, 'group-title'));
    if (!layer.payload_id) {
      box.append(el('p', 'This one holds no picture yet.', 'status-text'));
    }
    if (layer.needs_review) {
      box.append(
        el(
          'p',
          'The picture was replaced after this was set up. Look at it against the places, then mark it reviewed, or set it up again.',
          'chip',
        ),
      );
    }
    const anchors = layer.calibration?.anchors as Anchor[] | undefined;
    const kept = anchors?.length === 3;
    const mode = select(
      'Where it lies',
      [
        ['fit', 'Fit the sheet'],
        ['two', 'Set by two points'],
        ...(kept ? ([['kept', 'Set by three points (kept as it is)']] as [string, string][]) : []),
      ],
      kept ? 'kept' : anchors ? 'two' : 'fit',
    );
    const points = el('div', '', 'stack-tight');
    const pair = (label: string, at: Anchor | undefined) => {
      const row = el('fieldset', '', 'map-point');
      row.append(el('legend', label, 'map-point-name'));
      const across = field(
        'Across the picture (%)',
        String(Math.round((at?.image[0] ?? 0) * 100)),
        'number',
      );
      const down = field(
        'Down the picture (%)',
        String(Math.round((at?.image[1] ?? 0) * 100)),
        'number',
      );
      const x = field('On the sheet, x', String(at?.at[0] ?? 0), 'number');
      const y = field('On the sheet, y', String(at?.at[1] ?? 0), 'number');
      for (const f of [across, down]) {
        f.input.min = '0';
        f.input.max = '100';
        f.input.step = 'any';
      }
      for (const f of [x, y]) f.input.step = 'any';
      row.append(across.label, down.label, x.label, y.label);
      return { row, across, down, x, y };
    };
    const a = pair('Point A', anchors?.[0]);
    const b = pair('Point B', anchors?.[1]);
    points.append(a.row, b.row);
    const opacity = field('Opacity (%)', String(Math.round((layer.opacity ?? 1) * 100)), 'number');
    opacity.input.min = '0';
    opacity.input.max = '100';
    opacity.input.step = 'any';
    const sync = () => {
      points.hidden = mode.input.value !== 'two';
    };
    mode.input.addEventListener('change', sync);
    sync();
    box.append(mode.label, points, opacity.label);

    const read = (): Item => {
      const percent = Number(opacity.input.value);
      if (!(percent >= 0 && percent <= 100))
        throw new Error('An opacity is from 0 to 100 percent.');
      let calibration: Calibration = null;
      if (mode.input.value === 'kept') calibration = items[index]?.calibration ?? null;
      else if (mode.input.value === 'two') {
        const anchor = (p: ReturnType<typeof pair>): Anchor => {
          const nums = [p.across.input, p.down.input, p.x.input, p.y.input].map((i) =>
            Number(i.value),
          );
          if (
            nums.some((n) => !Number.isFinite(n)) ||
            nums.slice(0, 2).some((n) => n < 0 || n > 100)
          )
            throw new Error(
              'Each point needs its place in the picture (0 to 100) and on the sheet.',
            );
          return {
            image: [(nums[0] as number) / 100, (nums[1] as number) / 100],
            at: [nums[2] as number, nums[3] as number],
          };
        };
        calibration = { anchors: [anchor(a), anchor(b)] };
      }
      return {
        information_id: layer.information_id,
        calibration,
        opacity: percent === 100 ? null : percent / 100,
        reviewed: false,
      };
    };
    const rewrite = (change: (list: Item[]) => Item[]) =>
      write(change(items.map((i) => ({ ...i }))));

    const status = statusLine();
    const save = button('Save this picture', async () => {
      await rewrite((list) => list.map((item, i) => (i === index ? read() : item)));
    });
    const up = button('Move up', () =>
      rewrite((list) => {
        const [moved] = list.splice(index, 1);
        if (moved) list.splice(index - 1, 0, moved);
        return list;
      }),
    );
    up.disabled = index === 0;
    const down = button('Move down', () =>
      rewrite((list) => {
        const [moved] = list.splice(index, 1);
        if (moved) list.splice(index + 1, 0, moved);
        return list;
      }),
    );
    down.disabled = index === layers.length - 1;
    const row = actions(save, up, down);
    if (layer.needs_review) {
      row.append(
        button('Mark reviewed', () =>
          rewrite((list) =>
            list.map((item, i) => (i === index ? { ...item, reviewed: true } : item)),
          ),
        ),
      );
    }

    // Replace the picture: the new one is added and the old one removed.
    const replace = field('Replace the picture', '', 'file');
    replace.input.accept = PICTURE_TYPES;
    const replaceNow = button('Replace', async () => {
      const file = replace.input.files?.[0];
      if (!file) throw new Error('Choose a picture first.');
      await upload(tenant, layer.information_id, file);
      if (layer.payload_id) {
        await fetch(`${API_BASE_URL}/tenants/${tenant}/payloads/${layer.payload_id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${await getAccessToken()}` },
        });
      }
      await again();
    });

    // Remove it: the layer and the Information that holds the picture.
    let sure = false;
    const remove = el('button', 'Remove', 'btn btn-secondary');
    remove.type = 'button';
    remove.addEventListener('click', () => {
      if (!sure) {
        sure = true;
        remove.textContent = `Really remove ${layer.title}?`;
        return;
      }
      remove.disabled = true;
      void (async () => {
        try {
          await put(items.filter((_, i) => i !== index));
          await removeInformation(tenant, layer.information_id);
          await again();
        } catch (error) {
          say(status, message(error), true);
          remove.disabled = false;
        }
      })();
    });
    row.append(remove);
    box.append(row, replace.label, actions(replaceNow), status);
    wrap.append(box);
  });

  // Add a picture.
  const form = el('form', '', 'stack-tight');
  const file = field('A picture', '', 'file');
  file.input.accept = PICTURE_TYPES;
  const title = field('What it is called');
  const open = field('Everyone in the library may see it', '', 'checkbox');
  open.input.checked = header.is_public === true;
  const status = statusLine();
  form.append(
    file.label,
    title.label,
    open.label,
    actions(submit('Add the picture', 'secondary')),
    status,
  );
  file.input.addEventListener('change', () => {
    const chosen = file.input.files?.[0];
    if (chosen && !title.input.value) title.input.value = chosen.name.replace(/\.[^.]+$/, '');
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const chosen = file.input.files?.[0];
    if (!chosen) {
      say(status, 'Choose a picture first.', true);
      return;
    }
    void (async () => {
      let made: string | null = null;
      try {
        const created = await unwrap(
          await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
            params: { path: { tenant_id: tenant, entity_id: header.id } },
            body: {
              title: title.input.value.trim() || chosen.name,
              type: 'picture',
              is_public: open.input.checked,
              content: '',
              locale: 'en-US',
            },
          }),
        );
        made = created.id;
        await upload(tenant, created.id, chosen);
        await write([
          ...items,
          { information_id: created.id, calibration: null, opacity: null, reviewed: false },
        ]);
      } catch (error) {
        // A picture that was refused leaves no Information behind.
        if (made) await removeInformation(tenant, made).catch(() => undefined);
        say(status, `${error instanceof LorenzoApiError ? error.message : message(error)}`, true);
      }
    })();
  });

  wrap.append(card(groupTitle('h3', 'Add a picture'), form).root);
  return wrap;
}

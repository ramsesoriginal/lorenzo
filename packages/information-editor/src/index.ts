import {
  fetchAllPages,
  LorenzoApiError,
  type LorenzoClient,
  type Schema,
  unwrap,
} from '@lorenzo/api-client';

export type Audience = Schema<'InformationAudience'>;

/** Normalize user selection without losing grants not offered by a picker. */
export function audienceWithRecipients(
  audience: Audience,
  entities: Iterable<string>,
  players: Iterable<string>,
): Audience {
  return {
    is_public: audience.is_public,
    entity_ids: [...new Set(entities)].sort(),
    player_ids: [...new Set(players)].sort(),
  };
}

type Options = {
  client: LorenzoClient;
  tenantId: string;
  informationId: string | (() => Promise<string | null>);
  onSaved?: () => void | Promise<void>;
};

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The audience could not be saved.';

/** A small, lazy audience editor. A reader never gets the recipients without the API's edit gate. */
export function renderAudienceControl(options: Options): HTMLDetailsElement {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Who can read this';
  const body = document.createElement('div');
  body.className = 'stack-tight';
  details.append(summary, body);
  let loaded = false;
  let loading = false;

  details.addEventListener('toggle', async () => {
    if (!details.open || loaded || loading) return;
    loading = true;
    body.textContent = 'Loading audience…';
    try {
      const id =
        typeof options.informationId === 'string'
          ? options.informationId
          : await options.informationId();
      if (!id) {
        body.textContent = 'Save the information before choosing its readers.';
        return;
      }
      const path = { tenant_id: options.tenantId, information_id: id };
      const result = await options.client.GET(
        '/tenants/{tenant_id}/information/{information_id}/audience',
        { params: { path } },
      );
      let audience = await unwrap(result);
      let version = result.response.headers.get('etag');
      if (!version)
        throw new Error('The audience version is missing. Reopen this section to try again.');
      const [knowers, characters, groups] = await Promise.all([
        unwrap(
          await options.client.GET('/tenants/{tenant_id}/information/{information_id}/knowers', {
            params: { path },
          }),
        ),
        fetchAllPages(async (page) =>
          unwrap(
            await options.client.GET('/tenants/{tenant_id}/characters', {
              params: {
                path: { tenant_id: options.tenantId },
                query: { page, size: 100 },
              },
            }),
          ),
        ),
        fetchAllPages(async (page) =>
          unwrap(
            await options.client.GET('/tenants/{tenant_id}/groups', {
              params: {
                path: { tenant_id: options.tenantId },
                query: { page, size: 100 },
              },
            }),
          ),
        ),
      ]);
      const entities = new Set(audience.entity_ids);
      const players = new Set(audience.player_ids);
      body.replaceChildren();
      const publicLabel = document.createElement('label');
      publicLabel.className = 'field-row';
      const isPublic = document.createElement('input');
      isPublic.type = 'checkbox';
      isPublic.checked = audience.is_public;
      publicLabel.append(isPublic, ' Everyone with access to the library');
      const hint = document.createElement('p');
      hint.className = 'caption';
      hint.textContent =
        'Applicable GMs, library administrators and authors can also have access through their roles. An entry’s own audience still applies.';
      const field = document.createElement('fieldset');
      const legend = document.createElement('legend');
      legend.textContent = 'Characters and groups';
      const search = document.createElement('input');
      search.type = 'search';
      search.className = 'text-input';
      search.placeholder = 'Find a character or group';
      search.setAttribute('aria-label', 'Find a character or group');
      field.append(legend, search);
      const names = new Map<string, string>();
      for (const k of knowers)
        if (k.knower_entity_id) names.set(k.knower_entity_id, k.name ?? 'Existing recipient');
      for (const c of characters) names.set(c.entity_id, c.name);
      for (const g of groups) names.set(g.id, `${g.name} (group)`);
      const rows: HTMLLabelElement[] = [];
      for (const [recipient, name] of [...names].sort((a, b) => a[1].localeCompare(b[1]))) {
        const label = document.createElement('label');
        label.className = 'field-row';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = entities.has(recipient);
        checkbox.addEventListener('change', () =>
          checkbox.checked ? entities.add(recipient) : entities.delete(recipient),
        );
        label.append(checkbox, ` ${name}`);
        field.append(label);
        rows.push(label);
      }
      search.addEventListener('input', () => {
        for (const row of rows)
          row.hidden = !row.textContent?.toLowerCase().includes(search.value.trim().toLowerCase());
      });
      for (const k of knowers)
        if (k.player_id) {
          const recipient = k.player_id;
          const label = document.createElement('label');
          label.className = 'field-row';
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.checked = players.has(recipient);
          checkbox.addEventListener('change', () =>
            checkbox.checked ? players.add(recipient) : players.delete(recipient),
          );
          label.append(checkbox, ` ${k.name ?? 'Existing player'} (player)`);
          field.append(label);
        }
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'btn btn-secondary';
      save.textContent = 'Save audience';
      const status = document.createElement('p');
      status.setAttribute('role', 'status');
      status.className = 'caption';
      save.addEventListener('click', async () => {
        save.disabled = true;
        status.textContent = 'Saving…';
        try {
          const replacement = audienceWithRecipients(
            { ...audience, is_public: isPublic.checked },
            entities,
            players,
          );
          const saved = await options.client.PUT(
            '/tenants/{tenant_id}/information/{information_id}/audience',
            {
              params: { path, header: { 'if-match': version } },
              body: replacement,
            },
          );
          audience = await unwrap(saved);
          version = saved.response.headers.get('etag');
          status.textContent = 'Audience saved.';
          await options.onSaved?.();
        } catch (error) {
          if (error instanceof LorenzoApiError && error.status === 412) {
            loaded = false;
            status.textContent =
              'Someone changed this audience. Close and reopen this section to review it.';
          } else status.textContent = message(error);
        } finally {
          save.disabled = false;
        }
      });
      const actions = document.createElement('div');
      actions.className = 'row';
      actions.append(save);
      body.append(publicLabel, field, hint, actions, status);
      loaded = true;
    } catch (error) {
      body.textContent = `${message(error)} Close and reopen to try again.`;
    } finally {
      loading = false;
    }
  });
  return details;
}

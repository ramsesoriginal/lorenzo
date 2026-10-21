import { client, fetchAllPages, unwrap } from './api';
import { button, el, select, sessionHref } from './dom';

export async function playPanel(
  tenant: string,
  sid: string,
  manager: boolean,
  refresh: () => Promise<void>,
) {
  const path = { tenant_id: tenant, session_id: sid };
  const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
    params: { path },
    cache: 'no-store',
  });
  const saved = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('section', '', 'panel stack');
  host.append(
    el('h2', 'Recorded play'),
    el(
      'p',
      'Presentation is separate from preparation and from the order Events happened. Unrecorded play stays unrecorded.',
      'caption',
    ),
  );
  let played = [...saved.played_appearance_ids];
  const statuses = new Map(saved.appearances.map((a) => [a.id, a.status]));
  const summary = el('ol', '', 'stack-tight');
  const drawSummary = () => {
    summary.replaceChildren();
    for (const id of played) {
      const row = el('li', saved.appearances.find((a) => a.id === id)?.name ?? '');
      if (manager) {
        const index = played.indexOf(id);
        if (index > 0)
          row.append(
            button('Earlier in played order', () => {
              [played[index - 1], played[index]] = [played[index], played[index - 1]];
              drawSummary();
            }),
          );
        if (index < played.length - 1)
          row.append(
            button('Later in played order', () => {
              [played[index + 1], played[index]] = [played[index], played[index + 1]];
              drawSummary();
            }),
          );
      }
      summary.append(row);
    }
  };
  drawSummary();
  host.append(summary);
  const status = el('p');
  status.setAttribute('role', 'status');
  if (manager) {
    const controls = el('details', '', 'stack');
    controls.append(el('summary', 'Review and record played scenes'));
    const inputs = saved.appearances.map((a) => {
      const choice = select(
        a.name,
        [
          ['planned', 'Planned'],
          ['played', 'Played'],
          ['skipped', 'Skipped'],
        ],
        a.status,
      );
      choice.input.addEventListener('change', () => {
        statuses.set(a.id, choice.input.value as 'planned' | 'played' | 'skipped');
        played = played.filter((id) => id !== a.id);
        if (choice.input.value === 'played') played.push(a.id);
        drawSummary();
      });
      controls.append(choice.label);
      return { id: a.id, input: choice.input };
    });
    controls.append(
      button('Propose played order from preparation', () => {
        played = saved.appearances.filter((a) => statuses.get(a.id) !== 'skipped').map((a) => a.id);
        for (const input of inputs) {
          const value = played.includes(input.id) ? 'played' : 'skipped';
          input.input.value = value;
          statuses.set(input.id, value);
        }
        drawSummary();
        status.textContent =
          'Proposal only. Review the scene statuses and order, then save explicitly.';
      }),
      button('Review saved play', async () => {
        const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
          params: { path },
          cache: 'no-store',
        });
        const current = await unwrap(result);
        version = result.response.headers.get('etag') ?? '';
        status.textContent = `Saved played scenes: ${current.played_appearance_ids.map((id) => current.appearances.find((a) => a.id === id)?.name).join(', ') || 'none'}. Your draft is unchanged. Review before saving again.`;
      }),
      button('Save played scenes', async () => {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/play', {
            params: { path, header: { 'if-match': version } },
            body: {
              played_appearance_ids: played,
              skipped_appearance_ids: [...statuses]
                .filter(([, status]) => status === 'skipped')
                .map(([id]) => id),
            },
          }),
        );
        await refresh();
      }),
      status,
    );
    host.append(controls);
  }
  const events = manager
    ? await fetchAllPages(async (page) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/entities', {
            params: { path: { tenant_id: tenant }, query: { kind: ['event'], page, size: 100 } },
          }),
        ),
      )
    : [];
  for (const appearance of saved.appearances) {
    const section = el('section', '', 'stack');
    section.append(el('h3', `${appearance.name} · ${appearance.status}`));
    const rows = saved.presentations.filter((p) => p.appearance_id === appearance.id);
    const list = el('ol', '', 'stack-tight');
    for (const presentation of rows) {
      const row = el('li', '', 'stack-tight');
      row.append(el('p', presentation.name));
      const targetPath = {
        ...path,
        appearance_id: appearance.id,
        presentation_id: presentation.id,
      };
      if (manager) {
        const index = rows.indexOf(presentation);
        const move = async (delta: number) => {
          const ids = rows.map((p) => p.id);
          [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
          await unwrap(
            await client.PUT(
              '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations/order',
              {
                params: {
                  path: { ...path, appearance_id: appearance.id },
                  header: { 'if-match': version },
                },
                body: { presentation_ids: ids },
              },
            ),
          );
          await refresh();
        };
        if (index > 0) row.append(button('Present earlier', () => move(-1)));
        if (index < rows.length - 1) row.append(button('Present later', () => move(1)));
        row.append(
          button(
            presentation.is_shared ? 'Make presentation private' : 'Share presentation',
            async () => {
              await unwrap(
                await client.PATCH(
                  '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations/{presentation_id}',
                  {
                    params: { path: targetPath, header: { 'if-match': version } },
                    body: { is_shared: !presentation.is_shared },
                  },
                ),
              );
              await refresh();
            },
          ),
          button('Remove presentation', async () => {
            await unwrap(
              await client.DELETE(
                '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations/{presentation_id}',
                { params: { path: targetPath, header: { 'if-match': version } } },
              ),
            );
            await refresh();
          }),
        );
      }
      list.append(row);
    }
    section.append(list);
    if (manager && events.length) {
      const picker = select(
        `Event presented in ${appearance.name}`,
        events.map((e) => [e.id, e.name]),
      );
      const id = crypto.randomUUID();
      section.append(
        picker.label,
        button('Record Event presentation', async () => {
          await unwrap(
            await client.POST(
              '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations',
              {
                params: {
                  path: { ...path, appearance_id: appearance.id },
                  header: { 'if-match': version },
                },
                body: { id, event_id: picker.input.value, is_shared: false },
              },
            ),
          );
          await refresh();
        }),
      );
    }
    host.append(section);
  }
  return host;
}

export async function sequencePanel(
  tenant: string,
  campaign: string,
  refresh: () => Promise<void>,
) {
  const path = { tenant_id: tenant, campaign_id: campaign };
  const result = await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence', {
    params: { path },
    cache: 'no-store',
  });
  const saved = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('section', '', 'panel stack');
  host.append(el('h2', 'Campaign session order'));
  const list = el('ol');
  for (const entry of saved.ordered) {
    const row = el('li');
    row.append(Object.assign(el('a', entry.name), { href: sessionHref(tenant, entry.id) }));
    list.append(row);
  }
  host.append(list);
  const unplaced = el(
    'p',
    `Unplaced sessions available to you: ${saved.unplaced.map((s) => s.name).join(', ') || 'none'}`,
    'caption',
  );
  host.append(unplaced);
  const manageable = [...saved.ordered, ...saved.unplaced].filter((s) => s.can_manage);
  if (!manageable.length) return host;
  let ids = saved.ordered.filter((s) => s.can_manage).map((s) => s.id);
  const editor = el('details', '', 'stack');
  editor.append(el('summary', 'Edit order of sessions I manage'));
  const draft = el('ol');
  const draw = () => {
    draft.replaceChildren();
    for (const id of ids) {
      const index = ids.indexOf(id);
      const row = el('li', manageable.find((s) => s.id === id)?.name ?? '');
      if (index > 0)
        row.append(
          button('Move session earlier', () => {
            [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
            draw();
          }),
        );
      if (index < ids.length - 1)
        row.append(
          button('Move session later', () => {
            [ids[index + 1], ids[index]] = [ids[index], ids[index + 1]];
            draw();
          }),
        );
      row.append(
        button('Leave session unplaced', () => {
          ids = ids.filter((i) => i !== id);
          draw();
        }),
      );
      draft.append(row);
    }
  };
  draw();
  const choice = select(
    'Session to place',
    manageable.map((s) => [s.id, s.name]),
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  editor.append(
    draft,
    choice.label,
    button('Place session at end', () => {
      if (!ids.includes(choice.input.value)) ids.push(choice.input.value);
      draw();
    }),
    button('Review saved session order', async () => {
      const result = await client.GET(
        '/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence',
        { params: { path }, cache: 'no-store' },
      );
      const current = await unwrap(result);
      version = result.response.headers.get('etag') ?? '';
      status.textContent = `Saved order: ${current.ordered.map((s) => s.name).join(', ') || 'none'}. Your draft is unchanged.`;
    }),
    button('Save session order', async () => {
      await unwrap(
        await client.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence', {
          params: { path, header: { 'if-match': version } },
          body: { session_ids: ids },
        }),
      );
      await refresh();
    }),
    status,
  );
  host.append(editor);
  return host;
}

import { client, fetchAllPages, unwrap } from './api';
import {
  actions,
  button,
  card,
  el,
  empty,
  panel,
  say,
  sectionHead,
  select,
  sessionHref,
  statusLine,
} from './dom';

export async function playPanel(
  tenant: string,
  sid: string,
  manager: boolean,
  refresh: () => Promise<void>,
) {
  const path = { tenant_id: tenant, session_id: sid };
  const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
    params: { path },
  });
  const saved = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('section', '', 'stack');
  host.append(
    sectionHead('Recorded play', { count: saved.played_appearance_ids.length }),
    el(
      'p',
      'Presentation is separate from preparation and from the order Events happened. Unrecorded play stays unrecorded.',
      'lede',
    ),
  );
  let played = [...saved.played_appearance_ids];
  const statuses = new Map(saved.appearances.map((a) => [a.id, a.status]));
  const summary = el('ol', '', 'list ordered');
  const none = empty('No Scenes are recorded as played yet.');
  const drawSummary = () => {
    summary.replaceChildren();
    none.hidden = played.length > 0;
    for (const id of played) {
      const row = el('li');
      row.append(el('span', saved.appearances.find((a) => a.id === id)?.name ?? '', 'grow'));
      if (manager) {
        const index = played.indexOf(id);
        if (index > 0)
          row.append(
            button(
              'Earlier in played order',
              () => {
                [played[index - 1], played[index]] = [played[index], played[index - 1]];
                drawSummary();
              },
              { icon: 'up' },
            ),
          );
        if (index < played.length - 1)
          row.append(
            button(
              'Later in played order',
              () => {
                [played[index + 1], played[index]] = [played[index], played[index + 1]];
                drawSummary();
              },
              { icon: 'down' },
            ),
          );
      }
      summary.append(row);
    }
  };
  drawSummary();
  host.append(summary, none);
  const status = statusLine();
  if (manager) {
    const controls = panel('Review and record played Scenes');
    const grid = el('div', '', 'grid');
    grid.style.setProperty('--grid-min', '240px');
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
      grid.append(choice.label);
      return { id: a.id, input: choice.input };
    });
    controls.body.append(
      grid,
      actions(
        button(
          'Save played Scenes',
          async () => {
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
          },
          { variant: 'primary' },
        ),
        button('Propose played order from preparation', () => {
          played = saved.appearances
            .filter((a) => statuses.get(a.id) !== 'skipped')
            .map((a) => a.id);
          for (const input of inputs) {
            const value = played.includes(input.id) ? 'played' : 'skipped';
            input.input.value = value;
            statuses.set(input.id, value);
          }
          drawSummary();
          say(status, 'Proposal only. Review the Scene statuses and order, then save explicitly.');
        }),
        button('Review saved play', async () => {
          const latest = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
            params: { path },
            cache: 'no-store',
          });
          const current = await unwrap(latest);
          version = latest.response.headers.get('etag') ?? '';
          say(
            status,
            `Saved played Scenes: ${current.played_appearance_ids.map((id) => current.appearances.find((a) => a.id === id)?.name).join(', ') || 'none'}. Your draft is unchanged. Review before saving again.`,
          );
        }),
      ),
      status,
    );
    host.append(controls.root);
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
  // The design's way to record play (screen 19): one dialog that proposes the outline as played,
  // with each Scene's status and the Events presented in it, saved on purpose. The API takes the
  // statuses and each presentation as separate writes against the Session's version, so a save is
  // those writes one after another, and one that stops says which were kept.
  if (manager && saved.appearances.length) {
    const open = button('Propose the outline as played', () => {
      const dialog = document.createElement('dialog');
      dialog.className = 'played-dialog';
      dialog.setAttribute('aria-label', 'Propose the outline as played');
      const body = el('div', '', 'stack');
      body.append(
        el('h2', 'Propose the outline as played'),
        el(
          'p',
          'This is a draft. Mark what was played or skipped and which Events were presented. Nothing is saved until you save the record. Later preparation edits will not change it.',
          'status-text',
        ),
      );
      const rows = saved.appearances.map((appearance) => {
        const already = new Set(
          saved.presentations
            .filter((p) => p.appearance_id === appearance.id)
            .map((p) => p.event_id),
        );
        const status = select(
          `${appearance.name}: played or skipped`,
          [
            ['played', 'Played'],
            ['skipped', 'Skipped'],
          ],
          appearance.status === 'skipped' ? 'skipped' : 'played',
        );
        const section = el('section', '', 'stack-tight');
        const head = el('div', '', 'row');
        head.append(el('h3', appearance.name, 'item-title grow'), status.label);
        const choices = el('div', '', 'row');
        const boxes = events.map((event) => {
          const label = el('label', '', 'row-tight');
          const input = el('input') as HTMLInputElement;
          input.type = 'checkbox';
          input.checked = already.has(event.id);
          input.disabled = already.has(event.id);
          label.append(input, document.createTextNode(event.name));
          choices.append(label);
          return { id: event.id, input };
        });
        section.append(head, choices);
        body.append(section);
        return { appearance, status, boxes, already };
      });
      body.append(
        el(
          'p',
          'Presenting an Event does not make it happen, and an Event can be presented in more than one Scene. One already recorded stays until it is removed in the list below.',
          'caption',
        ),
      );
      const note = statusLine();
      const save = button(
        'Save the record',
        async () => {
          save.disabled = true;
          let current = version;
          const kept: string[] = [];
          // Each write moves the version the next one must send, and the answer to a write does not
          // carry it, so it is read again from the record.
          const reread = async () => {
            const latest = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
              params: { path },
              cache: 'no-store',
            });
            await unwrap(latest);
            current = latest.response.headers.get('etag') ?? current;
          };
          try {
            const result = await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/play', {
              params: { path, header: { 'if-match': current } },
              body: {
                played_appearance_ids: rows
                  .filter((r) => r.status.input.value === 'played')
                  .map((r) => r.appearance.id),
                skipped_appearance_ids: rows
                  .filter((r) => r.status.input.value === 'skipped')
                  .map((r) => r.appearance.id),
              },
            });
            await unwrap(result);
            await reread();
            kept.push('the Scenes played and skipped');
            for (const row of rows)
              for (const box of row.boxes) {
                if (!box.input.checked || row.already.has(box.id)) continue;
                const made = await client.POST(
                  '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}/presentations',
                  {
                    params: {
                      path: { ...path, appearance_id: row.appearance.id },
                      header: { 'if-match': current },
                    },
                    body: { id: crypto.randomUUID(), event_id: box.id, is_shared: false },
                  },
                );
                await unwrap(made);
                await reread();
                kept.push(`${row.appearance.name}: ${box.input.parentElement?.textContent ?? ''}`);
              }
            dialog.close();
            dialog.remove();
            await refresh();
          } catch (error) {
            say(
              note,
              `${error instanceof Error ? error.message : String(error)} ${kept.length ? `Saved so far: ${kept.join('; ')}. ` : 'Nothing was saved. '}Your draft is still here; review the saved record before saving again.`,
              true,
            );
            save.disabled = false;
          }
        },
        { variant: 'primary' },
      );
      const cancel = button('Cancel', () => {
        dialog.close();
        dialog.remove();
      });
      body.append(note, actions(cancel, save));
      dialog.append(body);
      document.body.append(dialog);
      dialog.showModal();
    });
    summary.after(open);
  }
  for (const appearance of saved.appearances) {
    const section = card();
    section.body.append(el('h3', `${appearance.name} · ${appearance.status}`, 'item-title'));
    const rows = saved.presentations.filter((p) => p.appearance_id === appearance.id);
    const list = el('ol', '', 'list ordered');
    for (const presentation of rows) {
      const row = el('li');
      row.append(el('span', presentation.name, 'grow'));
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
        if (index > 0) row.append(button('Present earlier', () => move(-1), { icon: 'up' }));
        if (index < rows.length - 1)
          row.append(button('Present later', () => move(1), { icon: 'down' }));
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
    if (rows.length) section.body.append(list);
    else section.body.append(empty('No Events are presented in this Scene.'));
    if (manager && events.length) {
      const picker = select(
        `Event presented in ${appearance.name}`,
        events.map((e) => [e.id, e.name]),
      );
      const id = crypto.randomUUID();
      section.body.append(
        picker.label,
        actions(
          button(
            'Record Event presentation',
            async () => {
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
            },
            { icon: 'add' },
          ),
        ),
      );
    }
    host.append(section.root);
  }
  return host;
}

export async function sequencePanel(
  tenant: string,
  campaign: string,
  refresh: () => Promise<void>,
  current?: string,
) {
  const path = { tenant_id: tenant, campaign_id: campaign };
  const result = await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence', {
    params: { path },
  });
  const saved = await unwrap(result);
  let version = result.response.headers.get('etag') ?? '';
  const host = el('section', '', 'stack');
  host.append(sectionHead('Campaign Session order', { count: saved.ordered.length }));
  if (saved.ordered.length) {
    const list = el('ol', '', 'list ordered');
    for (const entry of saved.ordered) {
      const row = el('li');
      const name = Object.assign(el('a', entry.name, 'grow'), {
        href: sessionHref(tenant, entry.id),
      });
      row.append(name);
      if (entry.id === current) {
        name.setAttribute('aria-current', 'page');
        row.append(el('span', 'This Session', 'chip'));
      }
      list.append(row);
    }
    host.append(list);
  } else host.append(empty('No Sessions are placed in the campaign order yet.'));
  host.append(
    el(
      'p',
      `Unplaced Sessions available to you: ${saved.unplaced.map((s) => s.name).join(', ') || 'none'}`,
      'status-text',
    ),
  );
  const manageable = [...saved.ordered, ...saved.unplaced].filter((s) => s.can_manage);
  if (!manageable.length) return host;
  let ids = saved.ordered.filter((s) => s.can_manage).map((s) => s.id);
  const editor = panel('Edit order of Sessions I manage');
  const draft = el('ol', '', 'list ordered');
  const draw = () => {
    draft.replaceChildren();
    for (const id of ids) {
      const index = ids.indexOf(id);
      const row = el('li');
      row.append(el('span', manageable.find((s) => s.id === id)?.name ?? '', 'grow'));
      if (index > 0)
        row.append(
          button(
            'Move Session earlier',
            () => {
              [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
              draw();
            },
            { icon: 'up' },
          ),
        );
      if (index < ids.length - 1)
        row.append(
          button(
            'Move Session later',
            () => {
              [ids[index + 1], ids[index]] = [ids[index], ids[index + 1]];
              draw();
            },
            { icon: 'down' },
          ),
        );
      row.append(
        button('Leave Session unplaced', () => {
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
  const status = statusLine();
  editor.body.append(
    draft,
    choice.label,
    actions(
      button(
        'Save Session order',
        async () => {
          await unwrap(
            await client.PUT('/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence', {
              params: { path, header: { 'if-match': version } },
              body: { session_ids: ids },
            }),
          );
          await refresh();
        },
        { variant: 'primary' },
      ),
      button('Place Session at end', () => {
        if (!ids.includes(choice.input.value)) ids.push(choice.input.value);
        draw();
      }),
      button('Review saved Session order', async () => {
        const latest = await client.GET(
          '/tenants/{tenant_id}/campaigns/{campaign_id}/session-sequence',
          { params: { path }, cache: 'no-store' },
        );
        const fresh = await unwrap(latest);
        version = latest.response.headers.get('etag') ?? '';
        say(
          status,
          `Saved order: ${fresh.ordered.map((s) => s.name).join(', ') || 'none'}. Your draft is unchanged.`,
        );
      }),
    ),
    status,
  );
  host.append(editor.root);
  return host;
}

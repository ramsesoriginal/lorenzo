import { client, fetchAllPages, type Schema, unwrap } from './api';
import { coveragePanel, referencePanel } from './context';
import { button, el, field, link, message, select, sessionHref, suspendControls } from './dom';
import { livedLinkPanel } from './lived';
import { notes } from './notes';
import { playPanel, sequencePanel } from './play';
import { start } from './sign-in';

type StorySession = Schema<'SessionOut'>;
async function periodPicker(tenant: string, label: string, current: string | null = null) {
  const entries = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: {
          path: { tenant_id: tenant },
          query: { kind: ['calendar_period'], page, size: 100 },
        },
      }),
    ),
  );
  return select(
    label,
    [['', 'Not set'], ...entries.map((e) => [e.id, e.name] as [string, string])],
    current ?? '',
  );
}
export async function mountHome() {
  const host = document.querySelector<HTMLElement>('#sessions-home');
  if (!host) return;
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(el('h1', 'My sessions'));
    const sessions = await unwrap(await client.GET('/me/sessions', { cache: 'no-store' }));
    const list = el('ul', '', 'session-outline stack');
    for (const session of sessions) {
      const row = el('li', '', 'stack-tight');
      row.append(
        link(session.name, sessionHref(session.tenant_id, session.id, session.slug)),
        el(
          'p',
          `${session.real_date ?? 'Date not set'} · ${session.can_manage ? 'GM' : 'Player'}`,
          'caption',
        ),
      );
      list.append(row);
    }
    host.append(list);
    if (!sessions.length)
      host.append(
        el('p', 'Your sessions will appear here when you are added as a GM or player.', 'caption'),
      );
    const managed = await unwrap(await client.GET('/me/managed'));
    const campaigns = managed.tenants.flatMap((t) =>
      t.campaigns
        .filter((c) => c.is_gm)
        .map((c) => ({ tenant: t.tenant_id, id: c.campaign_id, name: `${t.name} · ${c.name}` })),
    );
    if (!campaigns.length) return;
    const form = el('form', '', 'panel stack');
    form.append(el('h2', 'Prepare a session'));
    const name = field('Session title');
    name.input.required = true;
    const campaign = select(
      'Campaign',
      campaigns.map((c) => [c.id, c.name]),
      campaigns[0].id,
    );
    const date = field('Real-world date', '', 'date');
    const slug = field('Link name (optional)');
    const status = el('p');
    status.setAttribute('role', 'status');
    const save = el('button', 'Create session', 'btn');
    save.type = 'submit';
    const id = crypto.randomUUID();
    form.append(name.label, campaign.label, date.label, slug.label, save, status);
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      const chosen = campaigns.find((c) => c.id === campaign.input.value);
      if (!chosen) return;
      void (async () => {
        try {
          const session = await unwrap(
            await client.POST('/tenants/{tenant_id}/sessions', {
              params: { path: { tenant_id: chosen.tenant } },
              body: {
                id,
                name: name.input.value,
                slug: slug.input.value || null,
                campaign_id: chosen.id,
                real_date: date.input.value || null,
              },
            }),
          );
          location.assign(sessionHref(chosen.tenant, session.id, session.slug));
        } catch (error) {
          status.textContent = `${message(error)} Your draft is still here.`;
          save.disabled = false;
        }
      })();
    });
    host.append(form);
  } catch (error) {
    host.append(el('p', message(error)));
  }
}
async function resolveSession(tenant: string, address: string, forceSlug = false) {
  if (!forceSlug && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(address)) return address;
  const rows = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path: { tenant_id: tenant }, query: { slug: [address] } },
    }),
  );
  const match = rows.find((r) => r.slug === address && r.kinds.includes('session'));
  if (!match) throw new Error('This session is not available.');
  return match.entity_id;
}
export async function mountSession() {
  const host = document.querySelector<HTMLElement>('#session-view');
  if (!host) return;
  const me = await start();
  if (!me || !host.isConnected) return;
  const query = new URLSearchParams(location.search);
  let tenant = query.get('tenant') ?? '';
  const address = query.get('slug') ?? query.get('id') ?? '';
  try {
    if (!tenant || !address) throw new Error('Open a session from My sessions.');
    if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(tenant)) {
      const tenants = await fetchAllPages(async (page) =>
        unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
      );
      const t = tenants.find((t) => t.slug === tenant);
      if (!t) throw new Error('This library is not available.');
      tenant = t.id;
    }
    const id = await resolveSession(tenant, address, query.has('slug'));
    let generation = 0;
    let releaseControls: (() => void) | undefined;
    const path = { tenant_id: tenant, session_id: id };
    const refresh = async () => {
      const turn = ++generation;
      releaseControls ??= suspendControls(host);
      try {
        const view = el('div', '', 'stack');
        const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
          params: { path },
          cache: 'no-store',
        });
        const session = await unwrap(result);
        const version = result.response.headers.get('etag') ?? '';
        if (!host.isConnected || turn !== generation) return;
        view.replaceChildren(
          link('My sessions', '/'),
          el('h1', session.name),
          link('Browse reusable scenes', `/scenes/?${new URLSearchParams({ tenant })}`),
          el('p', session.real_date ?? 'Real-world date not set', 'caption'),
        );
        if (session.can_manage)
          view.append(
            await detailsEditor(session, version, refresh),
            await rosterEditor(session, version, refresh),
          );
        view.append(
          await notes(tenant, id, () => void refresh()),
          await referencePanel(tenant, 'sessions', id, session.can_manage, refresh),
          await coveragePanel(tenant, id, session.can_manage, refresh),
        );
        const outline = el('section', '', 'stack');
        outline.append(el('h2', 'Scenes'));
        const list = el('ol', '', 'session-outline stack');
        for (const appearance of session.scenes) {
          const row = el('li', '', 'stack');
          row.append(
            el('h3'),
            el(
              'p',
              appearance.is_shared ? 'Shared with session participants' : 'GM preparation',
              'caption',
            ),
          );
          row
            .querySelector('h3')
            ?.append(
              link(
                appearance.name,
                `/scene/?${new URLSearchParams({ tenant, id: appearance.scene_entity_id })}`,
              ),
            );
          if (session.can_manage) {
            const index = session.scenes.indexOf(appearance);
            const move = async (delta: number) => {
              const ids = session.scenes.map((s) => s.id);
              [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
              await unwrap(
                await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/scenes/order', {
                  params: { path, header: { 'if-match': version } },
                  body: { appearance_ids: ids },
                }),
              );
              await refresh();
            };
            const controls = el('div', '', 'row');
            if (index > 0) controls.append(button('Move up', () => move(-1)));
            if (index < session.scenes.length - 1)
              controls.append(button('Move down', () => move(1)));
            controls.append(
              button(
                appearance.is_shared
                  ? 'Make preparation private'
                  : 'Share with session participants',
                async () => {
                  await unwrap(
                    await client.PATCH(
                      '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}',
                      {
                        params: {
                          path: { ...path, appearance_id: appearance.id },
                          header: { 'if-match': version },
                        },
                        body: { is_shared: !appearance.is_shared },
                      },
                    ),
                  );
                  await refresh();
                },
              ),
            );
            controls.append(
              button('Remove scene appearance', async () => {
                if (
                  !confirm(
                    'Remove this appearance and its session-specific notes? The reusable scene remains.',
                  )
                )
                  return;
                await unwrap(
                  await client.DELETE(
                    '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}',
                    {
                      params: {
                        path: { ...path, appearance_id: appearance.id },
                        header: { 'if-match': version },
                      },
                    },
                  ),
                );
                await refresh();
              }),
            );
            row.append(controls);
          }
          row.append(
            await referencePanel(tenant, 'scenes', appearance.scene_entity_id, false, refresh),
            await notes(tenant, appearance.id, () => void refresh()),
          );
          list.append(row);
        }
        outline.append(list);
        if (!session.scenes.length)
          outline.append(el('p', 'No scenes are available to you here.', 'caption'));
        view.append(
          outline,
          await playPanel(tenant, id, session.can_manage, refresh),
          await sequencePanel(tenant, session.campaign_id, refresh),
        );
        if (session.can_manage)
          view.append(
            await sceneAdder(session, version, refresh),
            await livedLinkPanel(tenant, id),
          );
        if (host.isConnected && turn === generation) {
          history.replaceState(history.state, '', sessionHref(tenant, id, session.slug));
          host.replaceChildren(...view.childNodes);
        }
      } finally {
        if (turn === generation) {
          releaseControls?.();
          releaseControls = undefined;
        }
      }
    };
    await refresh();
  } catch (error) {
    host.replaceChildren(link('My sessions', '/'), el('p', message(error)));
  }
}
async function detailsEditor(session: StorySession, version: string, refresh: () => Promise<void>) {
  const details = el('details', '', 'panel stack');
  details.append(el('summary', 'Session details'));
  const name = field('Session title', session.name);
  const date = field('Real-world date', session.real_date ?? '', 'date');
  const slug = field('Link name', session.slug ?? '');
  const period = await periodPicker(
    session.tenant_id,
    'In-world starting period',
    session.start_period_id,
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  details.append(
    button('Review saved session', async () => {
      const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
        cache: 'no-store',
      });
      const saved = await unwrap(result);
      version = result.response.headers.get('etag') ?? '';
      status.textContent = `Saved session: ${saved.name}; date ${saved.real_date ?? 'not set'}; link name ${saved.slug ?? 'not set'}. Your draft is unchanged. Review it before saving again.`;
    }),
    name.label,
    date.label,
    slug.label,
    period.label,
    button('Save session details', async () => {
      try {
        await unwrap(
          await client.PATCH('/tenants/{tenant_id}/sessions/{session_id}', {
            params: {
              path: { tenant_id: session.tenant_id, session_id: session.id },
              header: { 'if-match': version },
            },
            body: {
              name: name.input.value,
              real_date: date.input.value || null,
              ...((period.input.value || null) !== session.start_period_id
                ? { start_period_id: period.input.value || null }
                : {}),
              slug: slug.input.value || null,
            },
          }),
        );
        await refresh();
      } catch (error) {
        status.textContent = `${message(error)} Your draft is still here. Refresh the session before retrying a conflict.`;
      }
    }),
    status,
  );
  return details;
}
async function rosterEditor(session: StorySession, version: string, refresh: () => Promise<void>) {
  const path = { tenant_id: session.tenant_id, campaign_id: session.campaign_id };
  const [gms, players] = await Promise.all([
    unwrap(
      await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/gms', { params: { path } }),
    ),
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/campaigns/{campaign_id}/players', {
          params: { path, query: { page, size: 100 } },
        }),
      ),
    ),
  ]);
  const details = el('details', '', 'panel stack');
  details.append(el('summary', 'GMs and players'));
  const gmChecks = gms.map((gm) => {
    const f = field(gm.display_name ?? gm.nickname ?? 'GM', '', 'checkbox');
    f.input.checked = session.gm_user_ids.includes(gm.user_id);
    details.append(f.label);
    return { id: gm.user_id, input: f.input };
  });
  const playerChecks = players.map((player) => {
    const f = field(player.display_name ?? player.nickname ?? 'Player', '', 'checkbox');
    f.input.checked = session.players.some((p) => p.player_id === player.id);
    const group = el('fieldset', '', 'stack-tight');
    group.append(f.label);
    const chars = player.characters.map((c) => {
      const check = field(c.name, '', 'checkbox');
      check.input.checked = session.players.some(
        (p) => p.player_id === player.id && p.character_ids.includes(c.entity_id),
      );
      group.append(check.label);
      return { id: c.entity_id, input: check.input };
    });
    details.append(group);
    return { id: player.id, input: f.input, chars };
  });
  const status = el('p');
  status.setAttribute('role', 'status');
  details.append(
    button('Review saved roster', async () => {
      const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
        cache: 'no-store',
      });
      const saved = await unwrap(result);
      version = result.response.headers.get('etag') ?? '';
      const gmNames = gms
        .filter((g) => saved.gm_user_ids.includes(g.user_id))
        .map((g) => g.display_name ?? g.nickname ?? 'GM');
      const playerNames = players
        .filter((p) => saved.players.some((s) => s.player_id === p.id))
        .map((p) => p.display_name ?? p.nickname ?? 'Player');
      status.textContent = `Saved roster: GMs ${gmNames.join(', ')}; players ${playerNames.join(', ') || 'none'}. Your selection is unchanged. Review it before saving again.`;
    }),
    button('Save roster', async () => {
      try {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/roster', {
            params: {
              path: { tenant_id: session.tenant_id, session_id: session.id },
              header: { 'if-match': version },
            },
            body: {
              gm_user_ids: gmChecks.filter((c) => c.input.checked).map((c) => c.id),
              players: playerChecks
                .filter((c) => c.input.checked)
                .map((c) => ({
                  player_id: c.id,
                  character_ids: c.chars.filter((c) => c.input.checked).map((c) => c.id),
                })),
            },
          }),
        );
        await refresh();
      } catch (error) {
        status.textContent = `${message(error)} Your roster selection is still here.`;
      }
    }),
    status,
  );
  return details;
}
async function sceneAdder(session: StorySession, version: string, refresh: () => Promise<void>) {
  const host = el('section', '', 'panel stack');
  host.append(el('h2', 'Add a scene'));
  const existing = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: {
          path: { tenant_id: session.tenant_id },
          query: { kind: ['scene'], page, size: 100 },
        },
      }),
    ),
  );
  const picker = select('Existing scene', [
    ['', 'Create a new scene'],
    ...existing.map((s) => [s.id, s.name] as [string, string]),
  ]);
  const title = field('New scene title');
  const period = await periodPicker(session.tenant_id, 'Scene period');
  const publicScene = field('Make the reusable scene visible in this library', '', 'checkbox');
  const shared = field('Share this scene appearance with session participants', '', 'checkbox');
  const status = el('p');
  status.setAttribute('role', 'status');
  const sceneId = crypto.randomUUID();
  const appearanceId = crypto.randomUUID();
  host.append(
    picker.label,
    title.label,
    period.label,
    publicScene.label,
    shared.label,
    el(
      'p',
      'A reusable scene and its session appearance have separate audiences. Sharing this appearance does not open a restricted scene.',
      'caption',
    ),
    button('Review saved outline', async () => {
      const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
        cache: 'no-store',
      });
      const saved = await unwrap(result);
      version = result.response.headers.get('etag') ?? '';
      status.textContent = `Saved scenes: ${saved.scenes.map((s) => s.name).join(', ') || 'none'}. Your scene draft and retry identity are unchanged.`;
    }),
    button('Add scene', async () => {
      try {
        let scene = picker.input.value;
        if (!scene) {
          if (!title.input.value) throw new Error('Give the new scene a title.');
          scene = (
            await unwrap(
              await client.POST('/tenants/{tenant_id}/scenes', {
                params: { path: { tenant_id: session.tenant_id } },
                body: {
                  id: sceneId,
                  name: title.input.value,
                  period_entity_id: period.input.value || null,
                  is_public: publicScene.input.checked,
                },
              }),
            )
          ).id;
        }
        await unwrap(
          await client.POST('/tenants/{tenant_id}/sessions/{session_id}/scenes', {
            params: {
              path: { tenant_id: session.tenant_id, session_id: session.id },
              header: { 'if-match': version },
            },
            body: { id: appearanceId, scene_entity_id: scene, is_shared: shared.input.checked },
          }),
        );
        await refresh();
      } catch (error) {
        status.textContent = `${message(error)} Your scene selection and retry identity are kept.`;
      }
    }),
    status,
  );
  return host;
}

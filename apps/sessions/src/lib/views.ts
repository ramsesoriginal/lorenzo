import { client, fetchAllPages, type Schema, unwrap } from './api';
import { coveragePanel, referencePanel } from './context';
import {
  actions,
  audienceBadge,
  backLink,
  button,
  card,
  el,
  empty,
  errorNotice,
  field,
  link,
  linkButton,
  loading,
  message,
  metaLine,
  pageHead,
  panel,
  say,
  sectionHead,
  select,
  sessionHref,
  statusLine,
  submit,
  suspendControls,
} from './dom';
import { livedLinkPanel } from './lived';
import { campaignName, libraryName, libraryNames } from './names';
import { notes } from './notes';
import { periodControl } from './periods';
import { playPanel, sequencePanel } from './play';
import { start } from './sign-in';

type StorySession = Schema<'SessionOut'>;
/** What the Session page shares between its panels: the Session as last read and its version, which every conditional write sends and every write to the Session moves on. */
type PageState = { session: StorySession; version: string };
/** Controls laid out in columns that give way to one on a phone. */
function fields(...nodes: HTMLElement[]) {
  const grid = el('div', '', 'grid');
  grid.style.setProperty('--grid-min', '240px');
  grid.append(...nodes);
  return grid;
}
const roleBadge = (manager: boolean) => el('span', manager ? 'GM' : 'Player', 'chip');
export async function mountHome() {
  const host = document.querySelector<HTMLElement>('#sessions-home');
  if (!host) return;
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening your Sessions…'));
    // The Sessions, the libraries' names and the campaigns the person runs do not wait for one another.
    const [sessions, names, managed] = await Promise.all([
      client.GET('/me/sessions').then(unwrap),
      libraryNames(),
      client.GET('/me/managed').then(unwrap),
    ]);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('My Sessions', {
        lede: 'Sessions where you are a GM or a player, across your libraries.',
      }),
    );
    if (sessions.length) {
      const list = el('ul', '', 'list');
      for (const session of sessions) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        const where = names.get(session.tenant_id);
        text.append(
          link(session.name, sessionHref(session.tenant_id, session.id, session.slug)),
          el(
            'p',
            [where, session.real_date ?? 'Date not set'].filter(Boolean).join(' · '),
            'status-text',
          ),
        );
        row.append(text, roleBadge(session.can_manage));
        list.append(row);
      }
      view.append(list);
    } else
      view.append(empty('No Sessions yet. One appears here when you are added as a GM or player.'));
    host.replaceChildren(view);
    const campaigns = managed.tenants.flatMap((t) =>
      t.campaigns
        .filter((c) => c.is_gm)
        .map((c) => ({ tenant: t.tenant_id, id: c.campaign_id, name: `${t.name} · ${c.name}` })),
    );
    if (!campaigns.length) return;
    const form = el('form', '', 'stack');
    const name = field('Session title');
    name.input.required = true;
    const campaign = select(
      'Campaign',
      campaigns.map((c) => [c.id, c.name]),
      campaigns[0].id,
    );
    const date = field('Real-world date', '', 'date');
    const slug = field('Link name (optional)');
    const status = statusLine();
    const save = submit('Create Session');
    const id = crypto.randomUUID();
    form.append(fields(name.label, campaign.label, date.label, slug.label), actions(save), status);
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
          say(status, `${message(error)} Your draft is still here.`, true);
          save.disabled = false;
        }
      })();
    });
    const section = el('section', '', 'stack');
    section.append(sectionHead('Prepare a Session'), card(form).root);
    host.firstElementChild?.append(section);
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
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
  if (!match) throw new Error('This Session is not available.');
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
    host.replaceChildren(loading('Opening this Session…'));
    if (!tenant || !address) throw new Error('Open a Session from My Sessions.');
    if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(tenant)) {
      const tenants = await fetchAllPages(async (page) =>
        unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
      );
      const t = tenants.find((t) => t.slug === tenant);
      if (!t) throw new Error('This library is not available.');
      tenant = t.id;
    }
    const id = await resolveSession(tenant, address, query.has('slug'));
    const path = { tenant_id: tenant, session_id: id };
    // The Session as last read and its version, shared by every panel: a conditional write sends
    // the version the page holds now, whichever panel read it last.
    const ctx: PageState = { session: undefined as unknown as StorySession, version: '' };
    const readSession = async () => {
      const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
        params: { path },
      });
      ctx.session = await unwrap(result);
      ctx.version = result.response.headers.get('etag') ?? '';
      history.replaceState(history.state, '', sessionHref(tenant, id, ctx.session.slug));
    };

    // The page is drawn in regions. A save reads the Session again and then draws again only the
    // regions it can have changed, each when its own data is ready, so what is being typed in the
    // other panels, and which panels are open, is left as it is.
    const regionOf = (name: string) =>
      host.querySelector<HTMLElement>(`[data-region="${CSS.escape(name)}"]`);
    const region = <T extends HTMLElement>(node: T, name: string): T => {
      node.dataset.region = name;
      return node;
    };
    const refreshOf =
      (...names: string[]) =>
      () =>
        refreshRegions(names);
    const sceneRefresh = (appearance: string) => refreshOf(`scene:${appearance}`);

    const sceneCard = async (
      appearance: StorySession['scenes'][number],
      index: number,
    ): Promise<HTMLElement> => {
      const session = ctx.session;
      const row = region(el('li', '', 'card'), `scene:${appearance.id}`);
      row.dataset.index = String(index);
      const body = el('div', '', 'card-body stack');
      row.append(body);
      const heading = el('h3', '', 'item-title grow');
      heading.append(
        link(
          appearance.name,
          `/scene/?${new URLSearchParams({ tenant, id: appearance.scene_entity_id })}`,
        ),
      );
      const number = el('span', String(index + 1), 'chip');
      number.setAttribute('aria-hidden', 'true');
      const title = el('div', '', 'row');
      title.append(
        number,
        heading,
        audienceBadge(
          appearance.is_shared ? 'Shared with Session participants' : 'GM preparation',
          appearance.is_shared,
        ),
      );
      body.append(title);
      if (session.can_manage) {
        const move = async (delta: number) => {
          const ids = ctx.session.scenes.map((s) => s.id);
          [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
          await unwrap(
            await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/scenes/order', {
              params: { path, header: { 'if-match': ctx.version } },
              body: { appearance_ids: ids },
            }),
          );
          await refreshRegions(['order', 'play']);
        };
        const controls = el('div', '', 'row');
        if (index > 0) controls.append(button('Move up', () => move(-1), { icon: 'up' }));
        if (index < session.scenes.length - 1)
          controls.append(button('Move down', () => move(1), { icon: 'down' }));
        controls.append(
          button(
            appearance.is_shared ? 'Make preparation private' : 'Share with Session participants',
            async () => {
              await unwrap(
                await client.PATCH(
                  '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}',
                  {
                    params: {
                      path: { ...path, appearance_id: appearance.id },
                      header: { 'if-match': ctx.version },
                    },
                    body: { is_shared: !appearance.is_shared },
                  },
                ),
              );
              await refreshRegions([`scene:${appearance.id}`]);
            },
          ),
        );
        controls.append(
          button(
            'Remove Scene appearance',
            async () => {
              if (
                !confirm(
                  'Remove this appearance and its Session-specific notes? The reusable Scene remains.',
                )
              )
                return;
              await unwrap(
                await client.DELETE(
                  '/tenants/{tenant_id}/sessions/{session_id}/scenes/{appearance_id}',
                  {
                    params: {
                      path: { ...path, appearance_id: appearance.id },
                      header: { 'if-match': ctx.version },
                    },
                  },
                ),
              );
              await refreshRegions(['scenes', 'play']);
            },
            { variant: 'danger', icon: 'delete' },
          ),
        );
        body.append(controls);
      }
      body.append(
        ...(await Promise.all([
          referencePanel(
            tenant,
            'scenes',
            appearance.scene_entity_id,
            false,
            sceneRefresh(appearance.id),
            4,
          ),
          notes(tenant, appearance.id, () => void sceneRefresh(appearance.id)(), 'session', 4),
        ])),
      );
      return row;
    };

    const build: Record<string, () => Promise<HTMLElement | null>> = {
      head: async () => {
        const session = ctx.session;
        const [library, campaign] = await Promise.all([
          libraryName(tenant),
          campaignName(tenant, session.campaign_id),
        ]);
        return region(
          pageHead(session.name, {
            crumbs: [backLink('My Sessions', '/')],
            lede: [library, campaign].filter(Boolean).join(' · ') || undefined,
            meta: [
              metaLine('kind-calendar', session.real_date ?? 'Real-world date not set'),
              roleBadge(session.can_manage),
            ],
            actions: [
              linkButton('Browse reusable Scenes', `/scenes/?${new URLSearchParams({ tenant })}`),
            ],
          }),
          'head',
        );
      },
      details: async () =>
        ctx.session.can_manage
          ? region(await detailsEditor(ctx, refreshOf('head', 'details')), 'details')
          : null,
      roster: async () =>
        ctx.session.can_manage ? region(rosterEditor(ctx, refreshOf('roster')), 'roster') : null,
      notes: async () => region(await notes(tenant, id, () => void refreshOf('notes')()), 'notes'),
      references: async () =>
        region(
          await referencePanel(
            tenant,
            'sessions',
            id,
            ctx.session.can_manage,
            refreshOf('references'),
          ),
          'references',
        ),
      coverage: async () =>
        region(
          await coveragePanel(tenant, id, ctx.session.can_manage, refreshOf('coverage')),
          'coverage',
        ),
      scenes: async () => {
        const session = ctx.session;
        const outline = region(el('section', '', 'stack'), 'scenes');
        outline.append(sectionHead('Scenes', { count: session.scenes.length }));
        if (session.scenes.length) {
          const list = el('ol', '', 'stack');
          list.append(...(await Promise.all(session.scenes.map(sceneCard))));
          outline.append(list);
        } else outline.append(empty('No Scenes are available to you here.'));
        return outline;
      },
      adder: async () =>
        ctx.session.can_manage
          ? region(await sceneAdder(ctx, refreshOf('scenes', 'adder', 'play')), 'adder')
          : null,
      play: async () =>
        region(await playPanel(tenant, id, ctx.session.can_manage, refreshOf('play')), 'play'),
      sequence: async () =>
        region(
          await sequencePanel(tenant, ctx.session.campaign_id, refreshOf('sequence'), id),
          'sequence',
        ),
      lived: async () =>
        ctx.session.can_manage ? region(await livedLinkPanel(tenant, id), 'lived') : null,
    };

    const openPanels = () =>
      new Set(
        [...host.querySelectorAll<HTMLDetailsElement>('details[open]')].map(
          (d) => d.querySelector('summary')?.textContent ?? '',
        ),
      );
    const reopen = (root: ParentNode, open: Set<string>) => {
      for (const d of root.querySelectorAll<HTMLDetailsElement>('details.panel')) {
        if (open.has(d.querySelector('summary')?.textContent ?? '')) d.open = true;
      }
    };

    // Everything drawn again: the first time, and when what the person may do has changed.
    const drawAll = async () => {
      const names = Object.keys(build);
      const nodes = new Map(
        await Promise.all(names.map(async (name) => [name, await build[name]?.()] as const)),
      );
      if (!host.isConnected) return;
      const view = el('div', '', 'stack view');
      const editors = el('div', '', 'stack-tight');
      for (const name of ['details', 'roster']) {
        const node = nodes.get(name);
        if (node) editors.append(node);
      }
      const outline = el('div', '', 'stack');
      for (const name of ['scenes', 'adder']) {
        const node = nodes.get(name);
        if (node) outline.append(node);
      }
      const put = (name: string) => nodes.get(name) ?? [];
      view.append(
        ...[put('head')].flat(),
        ...(editors.childElementCount ? [editors] : []),
        ...[put('notes'), put('references'), put('coverage')].flat(),
        outline,
        ...[put('play'), put('sequence'), put('lived')].flat(),
      );
      const open = openPanels();
      host.replaceChildren(...view.childNodes);
      reopen(host, open);
    };

    const turns = new Map<string, number>();
    const stamp = (name: string) => {
      const turn = (turns.get(name) ?? 0) + 1;
      turns.set(name, turn);
      return turn;
    };

    // A region drawn again, its open panels kept open. Null leaves the page as it is.
    const swap = (old: HTMLElement | null, next: HTMLElement | null) => {
      if (!old) return false;
      const open = openPanels();
      if (next) {
        old.replaceWith(next);
        reopen(next, open);
      } else old.remove();
      return true;
    };

    const drawRegion = async (name: string): Promise<boolean> => {
      const turn = stamp(name);
      if (name === 'order') {
        const list = host.querySelector<HTMLElement>('[data-region="scenes"] > ol');
        if (!list) return false;
        const have = new Map(
          [...list.children].map((card) => [
            (card as HTMLElement).dataset.region ?? '',
            card as HTMLElement,
          ]),
        );
        const cards = await Promise.all(
          ctx.session.scenes.map(async (appearance, index) => {
            const known = have.get(`scene:${appearance.id}`);
            // A card keeps its drafts unless its number, and so its buttons, changed.
            return known && Number(known.dataset.index) === index
              ? known
              : sceneCard(appearance, index);
          }),
        );
        if (turns.get(name) !== turn || !host.isConnected) return true;
        list.replaceChildren(...cards);
        return true;
      }
      if (name.startsWith('scene:')) {
        const appearance = ctx.session.scenes.find((s) => `scene:${s.id}` === name);
        const next = appearance
          ? await sceneCard(appearance, ctx.session.scenes.indexOf(appearance))
          : null;
        if (turns.get(name) !== turn || !host.isConnected) return true;
        return swap(regionOf(name), next);
      }
      const make = build[name];
      if (!make) return false;
      const next = await make();
      if (turns.get(name) !== turn || !host.isConnected) return true;
      return swap(regionOf(name), next);
    };

    const refreshRegions = async (names: string[]) => {
      const wasManager = ctx.session.can_manage;
      const nodes = names
        .map((name) =>
          name === 'order'
            ? host.querySelector<HTMLElement>('[data-region="scenes"] > ol')
            : regionOf(name),
        )
        .filter((node): node is HTMLElement => node !== null);
      const releases = nodes.map((node) => suspendControls(node));
      try {
        await readSession();
        if (!host.isConnected) return;
        if (ctx.session.can_manage !== wasManager) {
          await drawAll();
          return;
        }
        const drawn = await Promise.all(names.map(drawRegion));
        // A region that is not on the page cannot be drawn in place: draw the page again.
        if (drawn.includes(false)) await drawAll();
      } finally {
        for (const release of releases) release();
      }
    };

    await readSession();
    await drawAll();
  } catch (error) {
    host.replaceChildren(backLink('My Sessions', '/'), errorNotice(error));
  }
}
async function detailsEditor(ctx: PageState, refresh: () => Promise<void>) {
  const session = ctx.session;
  const details = panel('Session details', 'title, date, link name, starting period');
  const name = field('Session title', session.name);
  const date = field('Real-world date', session.real_date ?? '', 'date');
  const slug = field('Link name', session.slug ?? '');
  const period = periodControl({
    tenant: session.tenant_id,
    label: 'In-world starting period',
    mode: 'single',
    initial: session.start_period_id ? [session.start_period_id] : [],
  });
  const status = statusLine();
  details.body.append(
    fields(name.label, date.label, slug.label, period.root),
    actions(
      button(
        'Save Session details',
        async () => {
          try {
            const picked = await period.value();
            await unwrap(
              await client.PATCH('/tenants/{tenant_id}/sessions/{session_id}', {
                params: {
                  path: { tenant_id: session.tenant_id, session_id: session.id },
                  header: { 'if-match': ctx.version },
                },
                body: {
                  name: name.input.value,
                  real_date: date.input.value || null,
                  ...(picked !== null ? { start_period_id: picked[0] ?? null } : {}),
                  slug: slug.input.value || null,
                },
              }),
            );
            await refresh();
          } catch (error) {
            say(
              status,
              `${message(error)} Your draft is still here. Refresh the Session before retrying a conflict.`,
              true,
            );
          }
        },
        { variant: 'primary' },
      ),
      button('Review saved Session', async () => {
        const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
          params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
          cache: 'no-store',
        });
        const saved = await unwrap(result);
        ctx.version = result.response.headers.get('etag') ?? '';
        say(
          status,
          `Saved Session: ${saved.name}; date ${saved.real_date ?? 'not set'}; link name ${saved.slug ?? 'not set'}. Your draft is unchanged. Review it before saving again.`,
        );
      }),
    ),
    status,
  );
  return details.root;
}
function rosterEditor(ctx: PageState, refresh: () => Promise<void>) {
  const session = ctx.session;
  const details = panel(
    'GMs and players',
    `${session.gm_user_ids.length} GMs, ${session.players.length} players`,
  );
  // The campaign's GMs and players are only read when the panel is first opened.
  let started = false;
  details.root.addEventListener('toggle', () => {
    if (!details.root.open || started) return;
    started = true;
    details.body.append(loading('Loading the campaign…'));
    void rosterContent(details.body, ctx, refresh).catch((error) =>
      details.body.replaceChildren(errorNotice(error)),
    );
  });
  return details.root;
}
async function rosterContent(body: HTMLElement, ctx: PageState, refresh: () => Promise<void>) {
  const session = ctx.session;
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
  const gmGroup = el('fieldset');
  gmGroup.append(el('legend', 'GMs'));
  const gmChecks = gms.map((gm) => {
    const f = field(gm.display_name ?? gm.nickname ?? 'GM', '', 'checkbox');
    f.input.checked = session.gm_user_ids.includes(gm.user_id);
    gmGroup.append(f.label);
    return { id: gm.user_id, input: f.input };
  });
  const playerGroup = el('fieldset');
  playerGroup.append(el('legend', 'Players and their Characters'));
  const playerChecks = players.map((player) => {
    const f = field(player.display_name ?? player.nickname ?? 'Player', '', 'checkbox');
    f.input.checked = session.players.some((p) => p.player_id === player.id);
    const group = el('div', '', 'stack-tight');
    group.append(f.label);
    const chars = player.characters.map((c) => {
      const check = field(c.name, '', 'checkbox');
      check.input.checked = session.players.some(
        (p) => p.player_id === player.id && p.character_ids.includes(c.entity_id),
      );
      check.label.classList.add('nested');
      group.append(check.label);
      return { id: c.entity_id, input: check.input };
    });
    playerGroup.append(group);
    return { id: player.id, input: f.input, chars };
  });
  if (!gms.length) gmGroup.append(empty('This campaign has no GMs.'));
  if (!players.length) playerGroup.append(empty('This campaign has no players.'));
  const status = statusLine();
  body.replaceChildren(
    fields(gmGroup, playerGroup),
    actions(
      button(
        'Save roster',
        async () => {
          try {
            await unwrap(
              await client.PUT('/tenants/{tenant_id}/sessions/{session_id}/roster', {
                params: {
                  path: { tenant_id: session.tenant_id, session_id: session.id },
                  header: { 'if-match': ctx.version },
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
            say(status, `${message(error)} Your roster selection is still here.`, true);
          }
        },
        { variant: 'primary' },
      ),
      button('Review saved roster', async () => {
        const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
          params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
          cache: 'no-store',
        });
        const saved = await unwrap(result);
        ctx.version = result.response.headers.get('etag') ?? '';
        const gmNames = gms
          .filter((g) => saved.gm_user_ids.includes(g.user_id))
          .map((g) => g.display_name ?? g.nickname ?? 'GM');
        const playerNames = players
          .filter((p) => saved.players.some((s) => s.player_id === p.id))
          .map((p) => p.display_name ?? p.nickname ?? 'Player');
        say(
          status,
          `Saved roster: GMs ${gmNames.join(', ')}; players ${playerNames.join(', ') || 'none'}. Your selection is unchanged. Review it before saving again.`,
        );
      }),
    ),
    status,
  );
}
async function sceneAdder(ctx: PageState, refresh: () => Promise<void>) {
  const session = ctx.session;
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
  const picker = select('Existing Scene', [
    ['', 'Create a new Scene'],
    ...existing.map((s) => [s.id, s.name] as [string, string]),
  ]);
  const title = field('New Scene title');
  const period = periodControl({
    tenant: session.tenant_id,
    label: 'Scene period',
    mode: 'single',
    initial: [],
  });
  const publicScene = field('Make the reusable Scene visible in this library', '', 'checkbox');
  const shared = field('Share this Scene appearance with Session participants', '', 'checkbox');
  const status = statusLine();
  const sceneId = crypto.randomUUID();
  const appearanceId = crypto.randomUUID();
  const choices = el('div', '', 'stack-tight');
  choices.append(publicScene.label, shared.label);
  const added = card(el('h3', 'Add a Scene', 'item-title'));
  added.body.append(
    fields(picker.label, title.label, period.root),
    choices,
    el(
      'p',
      'A reusable Scene and its Session appearance have separate audiences. Sharing this appearance does not open a restricted Scene.',
      'status-text',
    ),
    actions(
      button(
        'Add Scene',
        async () => {
          try {
            let scene = picker.input.value;
            if (!scene) {
              if (!title.input.value) throw new Error('Give the new Scene a title.');
              const picked = await period.value();
              scene = (
                await unwrap(
                  await client.POST('/tenants/{tenant_id}/scenes', {
                    params: { path: { tenant_id: session.tenant_id } },
                    body: {
                      id: sceneId,
                      name: title.input.value,
                      period_entity_id: picked?.[0] ?? null,
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
                  header: { 'if-match': ctx.version },
                },
                body: {
                  id: appearanceId,
                  scene_entity_id: scene,
                  is_shared: shared.input.checked,
                },
              }),
            );
            await refresh();
          } catch (error) {
            say(
              status,
              `${message(error)} Your Scene selection and retry identity are kept.`,
              true,
            );
          }
        },
        { variant: 'primary', icon: 'add' },
      ),
      button('Review saved outline', async () => {
        const result = await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
          params: { path: { tenant_id: session.tenant_id, session_id: session.id } },
          cache: 'no-store',
        });
        const saved = await unwrap(result);
        ctx.version = result.response.headers.get('etag') ?? '';
        say(
          status,
          `Saved Scenes: ${saved.scenes.map((s) => s.name).join(', ') || 'none'}. Your Scene draft and retry identity are unchanged.`,
        );
      }),
    ),
    status,
  );
  return added.root;
}

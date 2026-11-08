import { openMenu } from '@lorenzo/app-shell';
import { client, fetchAllPages, type Schema, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
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
  icon,
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
import { byCampaign, dateWords, nextSession, stateOf } from './home';
import { livedLinkPanel } from './lived';
import { campaignName, libraryName, libraryNames } from './names';
import { notes } from './notes';
import { periodControl } from './periods';
import { playPanel, sequencePanel } from './play';
import {
  BUILT_IN,
  footLine,
  PARTS,
  type PartKey,
  partOf,
  readViews,
  toggled,
  viewName,
  withView,
  writeViews,
} from './regions';
import { currentShell, start } from './sign-in';

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
    const campaigns = managed.tenants.flatMap((t) =>
      t.campaigns
        .filter((c) => c.is_gm)
        .map((c) => ({ tenant: t.tenant_id, id: c.campaign_id, name: `${t.name} · ${c.name}` })),
    );
    const view = el('div', '', 'stack view home');
    const head = pageHead('Sessions', {
      lede: 'Where you play and run games, across your libraries.',
    });
    view.append(head);
    // The page's main action opens the form that makes a Session; until then it is not there.
    const create = campaigns.length ? createForm(campaigns) : null;
    if (create) {
      const open = el('button', '', 'btn btn-primary');
      open.type = 'button';
      open.append(icon('add'), document.createTextNode('New Session'));
      open.addEventListener('click', () => {
        create.hidden = false;
        create.scrollIntoView({ block: 'start' });
        create.querySelector<HTMLInputElement>('input')?.focus();
      });
      head.querySelector('.row')?.append(open);
    }
    if (create) view.append(create);
    const today = new Date().toISOString().slice(0, 10);
    const next = nextSession(sessions, today);
    if (next) {
      const block = el('section', '', 'stack-tight');
      block.append(el('h2', 'Next', 'group-title'));
      const row = el('div', '', 'card card-body row home-next');
      const text = el('div', '', 'stack-tight grow');
      text.append(
        link(next.name, sessionHref(next.tenant_id, next.id, next.slug)),
        el(
          'p',
          [names.get(next.tenant_id), dateWords(next.real_date)].filter(Boolean).join(' · '),
          'status-text',
        ),
      );
      row.append(icon('kind-session'), text);
      block.append(row);
      view.append(block);
    }
    for (const group of byCampaign(sessions)) {
      const block = el('section', '', 'stack-tight');
      const title = el('h2', names.get(group.tenant) ?? 'Sessions', 'group-title');
      block.append(title);
      void campaignName(group.tenant, group.campaign).then((name) => {
        if (name) title.textContent = [names.get(group.tenant), name].filter(Boolean).join(' · ');
      });
      const list = el('ul', '', 'list home-list');
      for (const session of group.sessions) {
        const row = el('li', '', 'row');
        row.append(icon('kind-session'));
        const text = el('div', '', 'stack-tight grow');
        text.append(
          link(session.name, sessionHref(session.tenant_id, session.id, session.slug)),
          el('p', dateWords(session.real_date), 'status-text'),
        );
        row.append(text);
        const state = stateOf(session, today, next);
        if (state) {
          const chip = el('span', state === 'past' ? 'Past' : 'Next', 'state-chip');
          chip.dataset.state = state === 'past' ? 'synced' : 'stale';
          row.append(chip);
        }
        row.append(el('span', session.can_manage ? 'You are a GM' : 'You play', 'chip'));
        list.append(row);
      }
      block.append(list);
      view.append(block);
    }
    if (!sessions.length) {
      // No Session yet (screen 24): what it means, and how one comes to be here.
      const none = el('section', '', 'stack-tight home-empty');
      none.append(
        el('h2', 'No Session yet'),
        el(
          'p',
          'You will see a Session here once a GM assigns you to it. An invite link from a GM adds you to a campaign.',
          'status-text',
        ),
      );
      view.append(none);
    }
    host.replaceChildren(view);
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

/** The form that makes a Session: shut until New Session opens it, and keeping its draft when a save fails. */
function createForm(campaigns: Array<{ tenant: string; id: string; name: string }>) {
  const root = card();
  root.root.hidden = true;
  const form = el('form', '', 'stack');
  const name = field('Session title');
  name.input.required = true;
  const campaign = select(
    'Campaign',
    campaigns.map((c) => [c.id, c.name]),
    campaigns[0]?.id,
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
  root.body.append(sectionHead('Prepare a Session'), form);
  return root.root;
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
    // The parts shown (CS4): a Session opens in Prepare, every time. A region drawn again keeps what
    // the view says of it.
    let visible: PartKey[] = [...BUILT_IN.Prepare];
    let viewChosen = false;
    let savedViews = readViews();
    const shown = (name: string) => {
      const part = partOf(name);
      return part === undefined || visible.includes(part);
    };
    // Each part has a control to hide it (screen 15); the View menu brings it back. It hides only the
    // drawing, so it is the same choice as unticking the part there.
    const hideControl = (node: HTMLElement, name: string) => {
      const part = partOf(name);
      const label = PARTS.find((p) => p.key === part)?.label;
      if (part === undefined || !label) return;
      // In a heading row only: a control inside a <summary> is nested interactive content. A part that
      // folds is hidden from the View menu, which every part has.
      const head = node.querySelector<HTMLElement>(':scope > .section-head');
      if (!head || head.querySelector('.region-hide')) return;
      const hide = el('button', '', 'btn btn-text region-hide');
      hide.type = 'button';
      hide.setAttribute('aria-label', `Hide ${label}`);
      hide.title = `Hide ${label}`;
      hide.append(icon('eye-off'));
      hide.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        visible = toggled(visible, part);
        syncView();
      });
      head.append(hide);
    };
    const region = <T extends HTMLElement>(node: T, name: string): T => {
      node.dataset.region = name;
      node.hidden = !shown(name);
      hideControl(node, name);
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
      // A player has fewer parts and nothing to prepare, so a Session opens in All for them (screen
      // 20); the first drawing is when the person's part is known.
      if (!viewChosen) {
        viewChosen = true;
        if (!ctx.session.can_manage) visible = [...BUILT_IN.All];
      }
      const names = Object.keys(build);
      const nodes = new Map(
        await Promise.all(names.map(async (name) => [name, await build[name]?.()] as const)),
      );
      if (!host.isConnected) return;
      const view = el('div', '', 'stack view');
      // The parts are cards in two columns where there is room (screen 15), in the order the menu lists.
      const grid = el('div', '', 'session-grid');
      for (const name of [
        'details',
        'roster',
        'notes',
        'references',
        'coverage',
        'scenes',
        'adder',
        'play',
        'sequence',
        'lived',
      ]) {
        const node = nodes.get(name);
        if (node) grid.append(node);
      }
      const head = nodes.get('head');
      if (head) view.append(head);
      view.append(grid);
      const foot = el('p', '', 'caption view-foot');
      view.append(foot);
      const open = openPanels();
      host.replaceChildren(...view.childNodes);
      reopen(host, open);
      mountViewMenu(foot);
    };

    // The View menu and the line at the foot that says what is hidden (CS4, CS6, screens 15 to 18).
    const syncView = () => {
      for (const node of host.querySelectorAll<HTMLElement>('[data-region]')) {
        const name = node.dataset.region ?? '';
        if (partOf(name) !== undefined) {
          node.hidden = !shown(name);
          // The heading is there once the part is drawn, so the control is added now, once.
          hideControl(node, name);
        }
      }
      const foot = host.querySelector<HTMLElement>('.view-foot');
      if (foot) {
        foot.textContent = footLine(visible);
        foot.hidden = !foot.textContent;
      }
      const label = host.querySelector<HTMLElement>('[data-view-label]');
      if (label) label.textContent = `View: ${viewName(visible, savedViews)}`;
    };
    const mountViewMenu = (foot: HTMLElement) => {
      const title = host.querySelector<HTMLElement>('[data-region="head"] .row');
      if (!title) return syncView();
      const button = el('button', '', 'btn btn-secondary view-button');
      button.type = 'button';
      button.setAttribute('aria-haspopup', 'menu');
      const label = el('span', '', 'view-label');
      label.dataset.viewLabel = '';
      button.append(icon('settings'), label);
      const choose = (parts: readonly PartKey[]) => {
        visible = [...parts];
        syncView();
      };
      button.addEventListener('click', () => {
        const current = viewName(visible, savedViews);
        openMenu(
          button,
          [
            { heading: 'View' },
            ...(['Prepare', 'Played', 'All'] as const).map((name) => ({
              label: name,
              checked: current === name,
              run: () => choose(BUILT_IN[name]),
            })),
            ...savedViews.map((v) => ({
              label: v.name,
              checked: current === v.name,
              run: () => choose(v.parts),
            })),
            { separator: true as const },
            { heading: 'Parts' },
            ...PARTS.map((part) => ({
              label: part.label,
              checked: visible.includes(part.key),
              run: () => choose(toggled(visible, part.key)),
            })),
            { separator: true as const },
            {
              label: 'Save this view…',
              icon: 'add',
              run: () => {
                const name = prompt('Name this view');
                const next = name === null ? null : withView(savedViews, name, visible);
                if (!next) return;
                savedViews = next;
                writeViews(savedViews);
                syncView();
              },
            },
          ],
          { label: 'View', sprite: `${BRANDING_CSS_URL}/icons.svg` },
        );
      });
      title.append(button);
      syncView();
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

    // The status bar says the part the person has and the in-world date of this Session (CS1): the date
    // of the Session being looked at, and nothing on any other page.
    const showBar = async () => {
      const startId = ctx.session.start_period_id;
      const started = startId
        ? await client
            .GET('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenant, entity_id: startId } },
            })
            .then((r) => r.data?.name ?? null)
            .catch(() => null)
        : null;
      if (!host.isConnected) return;
      currentShell()?.statusBar({
        meta: [
          ctx.session.can_manage ? 'You are a GM' : 'You play',
          started ? `In-world: ${started}` : null,
        ]
          .filter(Boolean)
          .join(' · '),
      });
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
        void showBar();
        if (ctx.session.can_manage !== wasManager) {
          await drawAll();
          return;
        }
        const drawn = await Promise.all(names.map(drawRegion));
        syncView();
        // A region that is not on the page cannot be drawn in place: draw the page again.
        if (drawn.includes(false)) await drawAll();
      } finally {
        for (const release of releases) release();
      }
    };

    await readSession();
    await drawAll();
    void showBar();
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

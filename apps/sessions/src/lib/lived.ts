import { client, fetchAllPages, unwrap } from './api';
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
  linkButton,
  loading,
  pageHead,
  say,
  sectionHead,
  select,
  sessionHref,
  statusLine,
  suspendControls,
} from './dom';
import { libraryName } from './names';
import { start } from './sign-in';

export async function livedLinkPanel(tenant: string, sid: string) {
  const beings = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id: tenant }, query: { kind: ['being'], page, size: 100 } },
      }),
    ),
  );
  const host = el('section', '', 'stack');
  host.append(
    sectionHead('Personal lived order'),
    el(
      'p',
      'Review a being’s existing Event participations. Recording lived order is optional and separate from play order.',
      'lede',
    ),
  );
  if (!beings.length) {
    host.append(empty('No beings exist in this library yet.'));
    return host;
  }
  const picker = select(
    'Being whose lived order to review',
    beings.map((b) => [b.id, b.name]),
  );
  const open = linkButton('Review personal lived order', '');
  const update = () => {
    open.href = `/lived/?${new URLSearchParams({ tenant, being: picker.input.value, session: sid })}`;
  };
  update();
  picker.input.addEventListener('change', update);
  host.append(card(picker.label, actions(open)).root);
  return host;
}

export async function mountLived() {
  const host = document.querySelector<HTMLElement>('#lived-view');
  if (!host || !(await start())) return;
  try {
    host.replaceChildren(loading('Opening this being’s lived order…'));
    const query = new URLSearchParams(location.search);
    let tenant = query.get('tenant') ?? '';
    const being = query.get('being') ?? '';
    const sid = query.get('session');
    if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(tenant)) {
      const tenants = await fetchAllPages(async (page) =>
        unwrap(await client.GET('/tenants', { params: { query: { page, size: 100 } } })),
      );
      const found = tenants.find((t) => t.slug === tenant);
      if (!found) throw new Error('This library is not available.');
      tenant = found.id;
    }
    const path = { tenant_id: tenant, being_id: being };
    let generation = 0;
    let releaseControls: (() => void) | undefined;
    const refresh = async () => {
      const turn = ++generation;
      releaseControls ??= suspendControls(host);
      try {
        const view = el('div', '', 'stack view');
        const publish = () => {
          if (host.isConnected && turn === generation) host.replaceChildren(...view.childNodes);
        };
        const result = await client.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
          params: { path },
        });
        const saved = await unwrap(result);
        let version = result.response.headers.get('etag') ?? '';
        view.replaceChildren(
          pageHead(`${saved.name} · personal lived order`, {
            crumbs: [
              backLink('My Sessions', '/'),
              ...(sid ? [backLink('Return to Session', sessionHref(tenant, sid))] : []),
            ],
            lede: (await libraryName(tenant)) ?? undefined,
          }),
          el(
            'p',
            'Only explicitly saved assertions are evidence. Dates, presentation and a linearized Event display never become personal lived history.',
            'lede',
          ),
        );
        const assertions = el('section', '', 'stack');
        assertions.append(sectionHead('Lived-before evidence', { count: saved.assertions.length }));
        const list = el('ul', '', 'list');
        for (const assertion of saved.assertions) {
          const row = el('li');
          row.append(
            el('span', `${assertion.from_name} → ${assertion.to_name}`, 'grow'),
            audienceBadge(
              assertion.is_shared ? 'Shared lived evidence' : 'Private lived evidence',
              assertion.is_shared,
            ),
          );
          if (saved.can_manage)
            row.append(
              button(
                assertion.is_shared ? 'Make lived evidence private' : 'Share lived evidence',
                async () => {
                  await unwrap(
                    await client.PUT('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
                      params: { path, header: { 'if-match': version } },
                      body: {
                        assertions: [
                          {
                            from_event_id: assertion.from_event_id,
                            to_event_id: assertion.to_event_id,
                            is_shared: !assertion.is_shared,
                          },
                        ],
                      },
                    }),
                  );
                  await refresh();
                },
              ),
              button(
                'Remove lived assertion',
                async () => {
                  await unwrap(
                    await client.DELETE(
                      '/tenants/{tenant_id}/beings/{being_id}/lived-order/{from_event_id}/{to_event_id}',
                      {
                        params: {
                          path: {
                            ...path,
                            from_event_id: assertion.from_event_id,
                            to_event_id: assertion.to_event_id,
                          },
                          header: { 'if-match': version },
                        },
                      },
                    ),
                  );
                  await refresh();
                },
                { variant: 'danger', icon: 'delete' },
              ),
            );
          list.append(row);
        }
        if (saved.assertions.length) assertions.append(list);
        else assertions.append(empty('No lived assertions are available to you here.'));
        view.append(assertions);
        const available = el('section', '', 'stack');
        available.append(
          sectionHead('Recorded participations', { count: saved.participations.length }),
        );
        if (saved.participations.length) {
          const participants = el('ul', '', 'row');
          for (const p of saved.participations) participants.append(el('li', p.name, 'chip'));
          available.append(participants);
        } else available.append(empty('This being has no recorded participations.'));
        available.append(
          el(
            'p',
            'This list is alphabetical, not a recorded life sequence. Unplaced participations stay unplaced.',
            'status-text',
          ),
        );
        view.append(available);
        if (!saved.can_manage) {
          publish();
          return;
        }
        const options = saved.participations.map((p) => [p.event_id, p.name] as [string, string]);
        const earlier = select('Experienced earlier', options);
        const later = select('Experienced later', options);
        const shared = field('Share new lived evidence', '', 'checkbox');
        const status = statusLine();
        const review = button('Review saved lived order', async () => {
          const result = await client.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
            params: { path },
            cache: 'no-store',
          });
          const current = await unwrap(result);
          version = result.response.headers.get('etag') ?? '';
          say(
            status,
            `Saved assertions: ${current.assertions.map((a) => `${a.from_name} before ${a.to_name}`).join('; ') || 'none'}. Your draft is unchanged. Review before retrying.`,
          );
        });
        const savePairs = async (pairs: [string, string][]) => {
          if (!pairs.length) throw new Error('Choose two distinct recorded participations.');
          await unwrap(
            await client.PUT('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
              params: { path, header: { 'if-match': version } },
              body: {
                assertions: pairs.map(([from, to]) => ({
                  from_event_id: from,
                  to_event_id: to,
                  is_shared:
                    saved.assertions.find((a) => a.from_event_id === from && a.to_event_id === to)
                      ?.is_shared ?? shared.input.checked,
                })),
              },
            }),
          );
          await refresh();
        };
        const pair = el('div', '', 'grid');
        pair.style.setProperty('--grid-min', '240px');
        pair.append(earlier.label, later.label);
        const form = el('section', '', 'stack');
        form.append(
          sectionHead('Record lived-before evidence'),
          card(
            pair,
            shared.label,
            actions(
              button(
                'Save lived-before assertion',
                async () => {
                  if (!earlier.input.value || earlier.input.value === later.input.value)
                    throw new Error('Choose two distinct recorded participations.');
                  await savePairs([[earlier.input.value, later.input.value]]);
                },
                { variant: 'primary' },
              ),
              review,
            ),
            status,
          ).root,
        );
        view.append(form);
        if (sid) {
          const source = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
            params: { path: { tenant_id: tenant, session_id: sid } },
          });
          if (!source.response.ok) {
            publish();
            return;
          }
          const play = await unwrap(source);
          const presented = play.played_appearance_ids.flatMap((id) =>
            play.presentations.filter((p) => p.appearance_id === id),
          );
          const ids = [
            ...new Set(
              presented
                .filter((p) => saved.participations.some((s) => s.event_id === p.event_id))
                .map((p) => p.event_id),
            ),
          ];
          const proposal = el('section', '', 'stack');
          proposal.append(
            sectionHead('Review a proposal from played Events'),
            el(
              'p',
              'Only this being’s existing participations are eligible. Repeated presentations name one participation. Reorder this proposal if a flashback differs from lived experience. Nothing is saved automatically.',
              'lede',
            ),
          );
          const proposalStatus = statusLine();
          let draft: string[] = [];
          const order = el('ol', '', 'list ordered');
          const draw = () => {
            order.replaceChildren();
            for (const id of draft) {
              const index = draft.indexOf(id);
              const row = el('li');
              row.append(
                el('span', saved.participations.find((p) => p.event_id === id)?.name ?? '', 'grow'),
              );
              if (index > 0)
                row.append(
                  button(
                    'Experienced earlier in proposal',
                    () => {
                      [draft[index - 1], draft[index]] = [draft[index], draft[index - 1]];
                      draw();
                    },
                    { icon: 'up' },
                  ),
                );
              if (index < draft.length - 1)
                row.append(
                  button(
                    'Experienced later in proposal',
                    () => {
                      [draft[index + 1], draft[index]] = [draft[index], draft[index + 1]];
                      draw();
                    },
                    { icon: 'down' },
                  ),
                );
              row.append(
                button('Leave participation unplaced', () => {
                  draft = draft.filter((e) => e !== id);
                  draw();
                }),
              );
              order.append(row);
            }
          };
          proposal.append(
            card(
              actions(
                button('Propose from played participations', () => {
                  draft = [...ids];
                  draw();
                  say(
                    proposalStatus,
                    'Proposal only. Review this being and the participation order before saving.',
                  );
                }),
              ),
              order,
              actions(
                button(
                  'Save reviewed lived proposal',
                  async () => {
                    await savePairs(draft.slice(1).map((id, index) => [draft[index], id]));
                  },
                  { variant: 'primary' },
                ),
              ),
              proposalStatus,
            ).root,
          );
          view.append(proposal);
        }
        publish();
      } finally {
        if (turn === generation) {
          releaseControls?.();
          releaseControls = undefined;
        }
      }
    };
    await refresh();
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

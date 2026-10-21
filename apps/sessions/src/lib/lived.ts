import { client, fetchAllPages, unwrap } from './api';
import { button, el, field, link, message, select, sessionHref, suspendControls } from './dom';
import { start } from './sign-in';

export async function livedLinkPanel(tenant: string, sid: string) {
  const beings = await fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities', {
        params: { path: { tenant_id: tenant }, query: { kind: ['being'], page, size: 100 } },
      }),
    ),
  );
  const host = el('section', '', 'panel stack');
  host.append(
    el('h2', 'Personal lived order'),
    el(
      'p',
      'Review a being’s existing Event participations. Recording lived order is optional and separate from play order.',
      'caption',
    ),
  );
  if (!beings.length) return host;
  const picker = select(
    'Being whose lived order to review',
    beings.map((b) => [b.id, b.name]),
  );
  const open = link('Review personal lived order', '');
  const update = () => {
    open.href = `/lived/?${new URLSearchParams({ tenant, being: picker.input.value, session: sid })}`;
  };
  update();
  picker.input.addEventListener('change', update);
  host.append(picker.label, open);
  return host;
}

export async function mountLived() {
  const host = document.querySelector<HTMLElement>('#lived-view');
  if (!host || !(await start())) return;
  try {
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
        const view = el('div', '', 'stack');
        const publish = () => {
          if (host.isConnected && turn === generation) host.replaceChildren(...view.childNodes);
        };
        const result = await client.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
          params: { path },
          cache: 'no-store',
        });
        const saved = await unwrap(result);
        let version = result.response.headers.get('etag') ?? '';
        view.replaceChildren(
          link('My sessions', '/'),
          el('h1', `${saved.name} · personal lived order`),
          el(
            'p',
            'Only explicitly saved assertions are evidence. Dates, presentation and a linearized Event display never become personal lived history.',
            'caption',
          ),
        );
        if (sid) view.append(link('Return to session', sessionHref(tenant, sid)));
        const list = el('ul', '', 'stack');
        for (const assertion of saved.assertions) {
          const row = el('li', '', 'panel stack-tight');
          row.append(
            el('p', `${assertion.from_name} → ${assertion.to_name}`),
            el(
              'p',
              assertion.is_shared ? 'Shared lived evidence' : 'Private lived evidence',
              'caption',
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
              button('Remove lived assertion', async () => {
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
              }),
            );
          list.append(row);
        }
        view.append(list);
        if (!saved.assertions.length)
          view.append(el('p', 'No lived assertions are available to you here.', 'caption'));
        const available = el('section', '', 'stack');
        available.append(el('h2', 'Recorded participations'));
        const participants = el('ul');
        for (const p of saved.participations) participants.append(el('li', p.name));
        available.append(
          participants,
          el(
            'p',
            'This list is alphabetical, not a recorded life sequence. Unplaced participations stay unplaced.',
            'caption',
          ),
        );
        view.append(available);
        if (!saved.can_manage) {
          publish();
          return;
        }
        const form = el('section', '', 'panel stack');
        form.append(el('h2', 'Record lived-before evidence'));
        const options = saved.participations.map((p) => [p.event_id, p.name] as [string, string]);
        const earlier = select('Experienced earlier', options);
        const later = select('Experienced later', options);
        const shared = field('Share new lived evidence', '', 'checkbox');
        const status = el('p');
        status.setAttribute('role', 'status');
        const review = button('Review saved lived order', async () => {
          const result = await client.GET('/tenants/{tenant_id}/beings/{being_id}/lived-order', {
            params: { path },
            cache: 'no-store',
          });
          const current = await unwrap(result);
          version = result.response.headers.get('etag') ?? '';
          status.textContent = `Saved assertions: ${current.assertions.map((a) => `${a.from_name} before ${a.to_name}`).join('; ') || 'none'}. Your draft is unchanged. Review before retrying.`;
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
        form.append(
          earlier.label,
          later.label,
          shared.label,
          review,
          button('Save lived-before assertion', async () => {
            if (!earlier.input.value || earlier.input.value === later.input.value)
              throw new Error('Choose two distinct recorded participations.');
            await savePairs([[earlier.input.value, later.input.value]]);
          }),
          status,
        );
        view.append(form);
        if (sid) {
          const source = await client.GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
            params: { path: { tenant_id: tenant, session_id: sid } },
            cache: 'no-store',
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
          const proposal = el('section', '', 'panel stack');
          proposal.append(
            el('h2', 'Review a proposal from played Events'),
            el(
              'p',
              'Only this being’s existing participations are eligible. Repeated presentations name one participation. Reorder this proposal if a flashback differs from lived experience. Nothing is saved automatically.',
              'caption',
            ),
          );
          let draft: string[] = [];
          const order = el('ol', '', 'stack-tight');
          const draw = () => {
            order.replaceChildren();
            for (const id of draft) {
              const index = draft.indexOf(id);
              const row = el('li', saved.participations.find((p) => p.event_id === id)?.name ?? '');
              if (index > 0)
                row.append(
                  button('Experienced earlier in proposal', () => {
                    [draft[index - 1], draft[index]] = [draft[index], draft[index - 1]];
                    draw();
                  }),
                );
              if (index < draft.length - 1)
                row.append(
                  button('Experienced later in proposal', () => {
                    [draft[index + 1], draft[index]] = [draft[index], draft[index + 1]];
                    draw();
                  }),
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
            button('Propose from played participations', () => {
              draft = [...ids];
              draw();
              status.textContent =
                'Proposal only. Review this being and the participation order before saving.';
            }),
            order,
            button('Save reviewed lived proposal', async () => {
              await savePairs(draft.slice(1).map((id, index) => [draft[index], id]));
            }),
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
    host.append(el('p', message(error)));
  }
}

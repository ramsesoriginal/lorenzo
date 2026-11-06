/* Account hub, part 3: notifications and the glue to the shell. Profile, access tokens and connecting a device are the shell's pages (PT1 to PT5). */
function pNotifications() {
  const all = S.notifications; const list = all.filter((n) => H.notifFilter === 'All' || n.unread); const unread = all.filter((n) => n.unread).length;
  const rows = list.length ? list.map((n) => `<div class="notif" ${n.unread ? 'data-unread' : ''}><span aria-hidden="true" style="width:14px;flex:none;margin-top:6px">${n.unread ? '<span class="dot"></span>' : ''}</span><div class="tx">${n.unread ? '<span class="visually-hidden">Unread. </span>' : ''}<a href="#/${n.go}" data-read="${n.id}" style="color:var(--text-primary);text-decoration:none"><b>${esc(n.text)}</b></a><div class="t-meta">${esc(n.when)}</div></div>${n.unread ? `<button type="button" class="btn btn--quiet" data-act="mark-read" data-id="${n.id}">Mark read</button>` : ''}</div>`).join('') : `<div class="empty-inline">${slot('caught-up', 'Catileo, curled sleep')}<div class="t-sub" style="margin-top:var(--s-2h)">You’re all caught up.</div></div>`;
  return `<div class="page page-enter" style="max-width:760px"><div class="head-row"><div class="grow"><h1 class="t-title page-title">Notifications</h1><p class="page-sub" style="margin-bottom:0">${unread ? unread + ' unread' : 'Nothing unread'}</p></div><div class="row2"><div class="seg" role="radiogroup" aria-label="Show">${['All', 'Unread'].map((f) => `<button type="button" role="radio" aria-checked="${H.notifFilter === f}" data-act="notif-filter" data-v="${f}">${f}</button>`).join('')}</div><button type="button" class="btn" data-act="mark-all" ${unread ? '' : 'aria-disabled="true"'}>Mark all as read</button></div></div><div class="listcard" style="margin-top:var(--s-3)">${rows}</div></div>`;
}
Object.assign(window.HUB_ACTS2, {
  'notif-filter': (a) => { H.notifFilter = a.dataset.v; refresh(); },
  'mark-read': (a) => { const n = S.notifications.find((x) => x.id === a.dataset.id); n.unread = false; renderHeader(); refresh(); },
  'mark-all': (a) => { if (a.getAttribute('aria-disabled') === 'true') return; markAllRead(); refresh(); }
});

document.addEventListener('click', (e) => { const r = e.target.closest('[data-read]'); if (r) { const n = S.notifications.find((x) => x.id === r.dataset.read); if (n) { n.unread = false; renderHeader(); } } });

/* ---------------------------------------------------------------- glue to the shell */
window.START_ROUTE = 'hub';
window.TAB_HIDE = (t) => t === 'discover' && !S.publicRepos;
window.GO_EXT = { h: 'hub', a: 'hub' };
const metaOf = (f) => () => f();
window.ROUTES_EXT = {
  hub: { app: 'account', tab: 'hub', render: pHubHome, after: () => { if (H.acct === 'new') { afterFirstRun(); } else hubAfter(); }, meta: () => (H.acct === 'new' ? 'No library yet' : `${needs().length} need you`) },
  libraries: { app: 'account', tab: 'libraries', render: pLibraries, after: hubAfter, meta: () => `${myLibs().length} libraries` },
  library: { app: 'account', tab: 'libraries', render: pLibrary, after: hubAfter, meta: () => { const l = hl(parts()[1]); return l ? `${pl(l.people.length || 1, 'person', 'people')} · ${pl(l.campaigns.length, 'campaign', 'campaigns')}` : ''; } },
  repositories: { app: 'account', tab: 'repositories', render: pRepositories, after: afterRepositories, meta: () => `${HUB.repos.length} repositories` },
  repo: { app: 'account', tab: 'repositories', render: pRepo, after: hubAfter, meta: () => { const r = hr(parts()[1]); return r ? `${r.counts.entries} entries` : ''; } },
  discover: { app: 'account', tab: 'discover', render: pDiscover, after: afterDiscover, meta: () => `${HUB.discover.length} public repositories` },
  notifications: { app: 'account', tab: 'hub', render: pNotifications, after: hubAfter, meta: () => `${S.notifications.filter((n) => n.unread).length} unread` },
};
/* The controls bar: the unsettled layouts and the roles, to compare by clicking */
const PB = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Account</b>${[['busy', 'Busy'], ['quiet', 'Quiet'], ['new', 'New']].map(([v, t]) => PB('acct', v, t, H.acct === v)).join('')}</span><span class="group"><b>Your role in a library or repository</b>${[['asis', 'As is'], ['Owner', 'Owner'], ['Organizer', 'Organizer'], ['Author', 'Author'], ['Player', 'No role']].map(([v, t]) => PB('hrole', v, t, H.role === v)).join('')}</span><span class="group"><b>May create</b>${[['1', 'Yes'], ['0', 'No']].map(([v, t]) => PB('hcreate', v, t, String(+H.create) === v)).join('')}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p]').forEach((b) => { const k = b.dataset.p, v = b.dataset.v; if (k === 'acct') b.setAttribute('aria-pressed', H.acct === v); else if (k === 'hrole') b.setAttribute('aria-pressed', H.role === v); else if (k === 'hcreate') b.setAttribute('aria-pressed', String(+H.create) === v); }); };
window.PROTO_CLICK = (k, v) => {
  if (k === 'acct') { H.acct = v; go('hub'); return true; }
  if (k === 'hrole') { H.role = v; render(true); return true; }
  if (k === 'hcreate') { H.create = v === '1'; render(true); return true; }
  return false;
};

/* App: routes, the shell (header, strip, status bar, tab bar, drawer), account and overlays, keyboard, controls, boot. */
const ROUTES = {
  home: { app: 'sessions', tab: 'home', render: pHome, meta: () => 'Next: Thu 19:30', after: () => { $('#main').onclick = genericClick; } },
  beings: { app: 'beings', tab: 'beings', render: pBeings, after: afterBeings, meta: () => '' },
  board: { app: 'inventory', tab: 'board', render: pBoard, after: afterBoard },
  read: { app: 'writing', tab: 'read', render: pRead, after: afterRead, meta: () => '6 min read', noFade: true },
  write: { app: 'writing', tab: 'write', render: pWrite, after: afterWrite, full: true },
  settings: { app: 'account', tab: 'settings', render: pSettings, after: afterSettings },
  map: { app: 'maps', tab: 'map', render: pMap, after: afterMap, full: true },
  'first-run': { app: 'account', tab: 'settings', render: pFirstRun, after: afterFirstRun, meta: () => 'No library yet' },
  join: { app: 'account', tab: 'settings', render: () => pJoin(false), after: afterJoin, meta: () => 'Invite link' },
  states: { app: 'account', tab: 'settings', render: pStates, after: afterStates, meta: () => '8 states' }
};
if (window.ROUTES_EXT) Object.assign(ROUTES, window.ROUTES_EXT);
function parseRoute(r) {
  const [name, arg] = r.split('/');
  if (name === 'stub') return { app: arg, tab: 'stub/' + arg, render: () => pStub(arg), meta: () => '', after: () => { $('#main').onclick = genericClick; } };
  if (name === 'join' && arg === 'dead') return { ...ROUTES.join, render: () => pJoin(true), meta: () => 'Invite link' };
  if (ROUTES[name]) return { ...ROUTES[name], name, arg };
  for (const [appId, tabs] of Object.entries(DATA.appTabs)) { if (tabs.some((t) => t[1] === name)) return { app: appId, tab: name, render: () => pStub(appId), meta: () => '', after: () => { $('#main').onclick = genericClick; } }; }
  return { app: 'sessions', tab: 'home', render: () => pStub('sessions'), meta: () => '' };
}
function genericClick(e) {
  const a = e.target.closest('[data-act]'); if (!a) return;
  if (a.dataset.act === 'toast') toast({ title: a.dataset.title });
  else if (a.dataset.act === 'palette') openPalette();
}
const cur = () => parseRoute(S.route);
const isMac = /Mac|iPhone|iPad/.test(navigator.platform || '');
const modKey = isMac ? '⌘' : 'Ctrl';

function go(route) { const h = '#/' + route; if (location.hash === h) render(); else location.hash = h; }
function render(initial) {
  S.route = location.hash.replace(/^#\/?/, '') || 'home';
  const run = () => {
    if (OV.el) closeOv(true);
    renderMain(!initial); renderHeader(); renderTabbar(); renderStrip(); updateStatus();
  };
  if (document.startViewTransition && !reducedMotion() && !initial) document.startViewTransition(run); else run();
}
function renderMain(focus) {
  const r = cur(); const m = $('#main');
  m.onclick = m.oninput = m.onchange = m.onscroll = m.onkeydown = null;
  clearTimeout(BL.timer); clearTimeout(BL.msgTimer); clearTimeout(saveTimer);
  $('#savebar').toggleAttribute('data-open', false);
  if (r.name === 'beings' && r.arg && DATA.beings.some((b) => b.id === r.arg)) S.focus = r.arg;
  S.meta = r.meta ? r.meta() : '';
  m.innerHTML = r.render();
  m.scrollTop = 0; m.style.overflow = r.full ? 'hidden' : '';
  m.classList.toggle('scroll-fade', !r.full && !r.noFade);
  if (r.after) r.after();
  const a = appOf(r.app); document.title = `${a ? a.name : 'Lorenzo'} · Web design prototype`;
  if (focus) m.focus({ preventScroll: true });
}
const LOCKUP = window.LOCKUP || { light: '../../../brand/assets/lorenzo_horizontal_lockup_light_bg.svg', dark: '../../../brand/assets/lorenzo_horizontal_lockup_dark_bg.svg' };
function renderHeader() {
  const r = cur(); const a = appOf(r.app); const tabs = (DATA.appTabs[a.id] || []).filter((t) => !window.TAB_HIDE || !window.TAB_HIDE(t[1]));
  const unread = S.notifications.filter((n) => n.unread).length;
  const one = S.libs <= 1;
  const tabLinks = tabs.map(([n, t]) => `<a class="tab" href="#/${t}" ${t === r.tab ? 'aria-current="page"' : ''}>${n}</a>`).join('');
  const lib = S.libs > 1 ? `<button type="button" id="lib-btn" class="lib-btn" aria-haspopup="menu" aria-expanded="false" data-act="lib" data-keep-open>${esc(lib_())}${ic('expand')}</button>` : '';
  const right = `<button type="button" class="palette-btn" data-act="palette" data-keep-open>${ic('search')}<span>Find or go anywhere</span><kbd>${modKey} K</kbd></button><button type="button" class="icon-btn only-phone" aria-label="Find or go anywhere" data-act="palette">${ic('search')}</button><button type="button" id="bell" class="icon-btn" aria-label="Notifications, ${unread} unread" aria-haspopup="menu" aria-expanded="false" data-act="bell" data-keep-open>${ic('notifications')}${unread ? `<span class="num">${unread}</span>` : ''}</button><button type="button" id="acct-btn" class="avatar" aria-label="${DATA.user.initials}, account menu for ${DATA.user.name}" aria-haspopup="menu" aria-expanded="false" data-act="acct" data-keep-open><span aria-hidden="true">${DATA.user.initials}</span></button>`;
  const prod = `<span class="prod">${ic(a.icon)}${a.name}</span>`;
  if (one) {
    /* One library: nothing to switch, so the header is one row: the mark, the app, its links, then the global controls */
    $('#hdr').innerHTML = `<div class="hdr1 hdr-one"><a class="brand-link" href="#/${a.route}" aria-label="${a.name} home" title="${a.name} home">${MARK()}</a>${prod}<nav aria-label="${a.name}" class="hdr-nav">${tabLinks}</nav><span class="grow"></span>${right}</div>`;
  } else {
    /* More than one library: two tiers. The wordmark sits between the mark and the library switcher (a phone keeps the mark alone, identity 12.2) */
    $('#hdr').innerHTML = `<div class="hdr1"><a class="brand-link brand-lockup" href="#/${a.route}" aria-label="${a.name} home" title="${a.name} home"><span class="lockup"><img class="wm-light" src="${LOCKUP.light}" alt="" height="28"><img class="wm-dark" src="${LOCKUP.dark}" alt="" height="28"></span><span class="mark-only">${MARK()}</span></a>${lib}<span class="grow"></span>${right}</div><div class="hdr2">${prod}<nav aria-label="${a.name}">${tabLinks}</nav></div>`;
  }
}
const lib_ = () => DATA.libraries[S.lib];
function renderTabbar() {
  const r = cur(); const a = appOf(r.app); const tabs = (DATA.appTabs[a.id] || []).filter((t) => !window.TAB_HIDE || !window.TAB_HIDE(t[1])).slice(0, 3);
  const icons = ['kinds', 'layout-compare', 'kind-fact'];
  $('#tabbar').innerHTML = tabs.map(([n, t], i) => `<a href="#/${t}" ${t === r.tab ? 'aria-current="page"' : ''}>${ic(TAB_ICONS[t] || icons[i])}${n}</a>`).join('') + `<button type="button" data-act="more" aria-haspopup="dialog" data-keep-open>${ic('more')}More</button>`;
  $('#tabbar').setAttribute('aria-label', a.name);
}
function renderStrip() {
  const s = $('#strip'); let k = null, msg = '', act = '';
  if (S.conflict) { k = 'conflict'; msg = '<b>A change you made conflicts with one from Mara Quill.</b> Orla Venn needs a decision.'; act = '<button type="button" class="btn" data-act="review-strip">Review</button>'; }
  else if (S.offline) { k = 'offline'; msg = S.waiting ? `<b>Offline.</b> ${S.waiting} change${S.waiting > 1 ? 's are' : ' is'} waiting to sync.` : '<b>Offline.</b> Changes are kept on this device and sent when you are back.'; }
  if (k) { s.innerHTML = `<div><div class="strip-in" data-kind="${k}" role="status">${ic(k === 'conflict' ? 'conflict' : 'offline')}<span class="msg">${msg}</span><span class="grow"></span>${act}</div></div>`; s.setAttribute('data-open', ''); }
  else s.removeAttribute('data-open');
}
const clock = () => new Date().toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }).replace(',', '');
function updateStatus() {
  const k = S.offline ? 'offline' : S.waiting > 0 ? 'waiting' : 'synced';
  const t = S.offline ? 'Offline' : S.waiting > 0 ? `Waiting to sync (${S.waiting})` : 'Synced 19:40';
  const i = S.offline ? 'offline' : S.waiting > 0 ? 'waiting' : 'select-item';
  const o = window.STATUS_SYNC && window.STATUS_SYNC();
  const k2 = o ? o[0] : k, t2 = o ? o[1] : t, i2 = o ? o[2] : i;
  $('#status').innerHTML = `<span class="sync" data-kind="${k2}">${ic(i2)}${t2}</span><span class="num">${esc(S.meta || '')}</span>${(window.INWORLD ? window.INWORLD() : 'In-world: Year 4, day 112') ? `<span class="only-wide">${window.INWORLD ? window.INWORLD() : 'In-world: Year 4, day 112'}</span>` : ''}<span class="grow"></span><span class="only-wide" style="color:var(--text-tertiary)">${clock()}</span><button type="button" class="btn only-wide" id="about-btn" aria-haspopup="dialog" aria-expanded="${OV.el === $('#drawer')}" data-act="about" data-keep-open>Apps and about ${ic('collapse')}</button>`;
}
function openAbout() {
  const d = $('#drawer'); const a = appOf(cur().app);
  const grp = (g) => DATA.apps.filter((x) => x.group === g).map((x) => `<a class="l" href="#/${x.route}" data-close>${ic(x.icon)}${x.name}</a>`).join('');
  d.className = 'ov drawer'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-label', 'Apps and about');
  d.innerHTML = `<div class="cols"><div class="apps">${['Play', 'World', 'Build', 'You'].map((g) => `<div><div class="t-micro" style="margin-bottom:6px">${g}</div>${grp(g)}</div>`).join('')}</div><div><div class="t-micro" style="margin-bottom:6px">About</div><a class="l" href="#" data-legal="Legal notice">Legal notice</a><a class="l" href="#" data-legal="Privacy policy">Privacy policy</a><a class="l" href="#" data-legal="Source code">Source code</a></div></div><div class="foot">Lorenzo ${a.name} 0.12.0 · API 1.8.3 · licensed AGPL-3.0 · ${clock()}</div>`;
  d.onclick = (e) => { const l = e.target.closest('[data-legal]'); if (l) { e.preventDefault(); toast({ title: `${l.dataset.legal} is not written yet`, text: 'The page does not exist in the prototype.' }); return; } if (e.target.closest('[data-close]')) closeOv(true); };
  openOv(d, { modal: false, onClose: updateStatus });
  updateStatus();
}
function openMore(btn) {
  const items = [];
  const extra = (DATA.appTabs[cur().app] || []).filter((t) => !window.TAB_HIDE || !window.TAB_HIDE(t[1])).slice(3);
  if (extra.length) { items.push({ label: 'In ' + appOf(cur().app).name, heading: true }); extra.forEach(([n, t]) => items.push({ label: n, fn: () => go(t) })); }
  ['Play', 'World', 'Build', 'You'].forEach((g) => { items.push({ label: g, heading: true }); DATA.apps.filter((x) => x.group === g).forEach((x) => items.push({ label: x.name, icon: x.icon, check: x.id === cur().app ? true : undefined, fn: () => go(x.route) })); });
  items.push({ sep: true }, { label: 'Legal notice', fn: () => toast({ title: 'Legal notice is not written yet' }) }, { label: 'Privacy policy', fn: () => toast({ title: 'Privacy policy is not written yet' }) }, { label: 'Source code', fn: () => toast({ title: 'The source link opens the repository' }) }, { text: `Lorenzo ${appOf(cur().app).name} 0.12.0 · API 1.8.3 · AGPL-3.0 · ${clock()}` });
  openMenu(btn, items, { label: 'More' });
}

/* ---- account, library and notifications */
function openLibraryMenu(btn) {
  openMenu(btn, [{ label: 'Libraries', heading: true }, ...DATA.libraries.slice(0, S.libs).map((l, i) => ({ label: l, check: i === S.lib, fn: () => { S.lib = i; S.form = null; render(); toast({ title: `Switched to ${l}` }); } })), { sep: true }, { label: 'Create a library…', icon: 'library-plus', fn: openSetup }, { label: 'Manage libraries', icon: 'settings', kbd: 'G A', fn: () => go('settings') }], { label: 'Libraries', align: 'left' });
}
function openAcct(btn) {
  const n = S.notifications.filter((x) => x.unread).length;
  openMenu(btn, [{ head: `<div style="font-weight:600">${DATA.user.name}</div><div class="t-meta">${DATA.user.email}</div>` }, { label: 'Profile', icon: 'account', fn: () => go('profile') }, { label: 'Notifications', icon: 'notifications', badge: n || '', fn: () => openBell($('#bell')) }, { label: 'Libraries and people', icon: 'library', fn: () => go('settings') }, { label: 'Access tokens and devices', icon: 'token', fn: () => go('tokens') }, { sep: true }, { label: 'Appearance…', icon: 'appearance', fn: openAppearance }, { label: 'Keyboard shortcuts', icon: 'command', kbd: '?', fn: openShortcuts }, { sep: true }, { label: 'Sign out…', icon: 'logout', fn: openSignOut }], { label: 'Account' });
}
function openBell(btn) {
  const items = [{ label: 'Notifications', heading: true }, ...S.notifications.map((n) => ({ label: n.text, fn: () => { n.unread = false; renderHeader(); if (n.go) go(n.go); } })), { sep: true }, { label: 'Mark all as read', icon: 'select-item', fn: markAllRead }];
  openMenu(btn, items, { label: 'Notifications' });
}
function markAllRead() { S.notifications.forEach((n) => (n.unread = false)); renderHeader(); toast({ title: 'All notifications marked as read' }); }
function setDensity(d) { S.density = d; applyAppearance(); $$('[data-act="density"]').forEach((b) => b.setAttribute('aria-checked', b.dataset.d === d)); }
function setOffline(on) {
  S.offline = on; renderStrip(); updateStatus(); syncProto();
  if (!on) { const n = S.waiting; if (n) setTimeout(() => { S.waiting = 0; DATA.beings.forEach((b) => { if (b.state === 'waiting') b.state = 'synced'; }); BL.extra.forEach((b) => { if (b.state === 'waiting') b.state = 'synced'; }); renderStrip(); updateStatus(); if (S.route.startsWith('beings')) refreshBeings(); toast({ title: 'Back online', text: `${n} change${n > 1 ? 's' : ''} sent.` }); }, 900); else toast({ title: 'Back online' }); }
  else toast({ title: 'You are offline', text: 'What you change is saved on this device.', kind: 'ok' });
}
function openAppearance() {
  const seg = (id, label, opts, val) => `<div style="margin-bottom:var(--s-3)"><div class="label">${label}</div><div class="seg" role="radiogroup" aria-label="${label}">${opts.map(([v, t]) => `<button type="button" role="radio" aria-checked="${val === v}" data-k="${id}" data-v="${v}">${t}</button>`).join('')}</div></div>`;
  openDialog({ title: 'Appearance', body: `${seg('theme', 'Theme', [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']], S.theme)}${seg('density', 'Density of lists and tables', [['comfortable', 'Comfortable'], ['compact', 'Compact'], ['dense', 'Dense']], S.density)}<div class="help" style="margin-top:-8px;margin-bottom:var(--s-3)">The starting point for every list. A saved view can override it. Not offered on a phone.</div>${seg('motion', 'Motion', [['system', 'System'], ['reduced', 'Reduced']], S.motion)}<div class="t-meta">Remembered in your account. (The prototype keeps it on this device.)</div>`, actions: [{ label: 'Done', kind: 'primary', auto: true }], init: (d) => { d.onclick = (e) => { const b = e.target.closest('[data-k]'); if (b) { S[b.dataset.k] = b.dataset.v; applyAppearance(); $$(`[data-k="${b.dataset.k}"]`, d).forEach((x) => x.setAttribute('aria-checked', x === b)); syncProto(); const a = e.target.closest('[data-a]'); return; } const a = e.target.closest('[data-a]'); if (a) closeOv(); }; } });
}
function openShortcuts() {
  const k = (w, ...ks) => `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:30px"><span>${w}</span><span style="display:inline-flex;gap:4px">${ks.map((x) => `<kbd>${x}</kbd>`).join('')}</span></div>`;
  const col = (t, rows) => `<div><div class="t-micro" style="margin-bottom:8px">${t}</div>${rows}</div>`;
  openDialog({ title: 'Keyboard shortcuts', wide: true, body: `<p class="muted" style="margin-bottom:var(--s-3)">On a Mac, Ctrl is Cmd.</p><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:12px 14px;margin-bottom:var(--s-4);border:1px solid var(--border-control);border-radius:var(--r-card)"><div><div style="font-weight:500">Single-key shortcuts</div><div class="t-meta" style="color:var(--text-secondary)">Keys such as J, K and G then a letter. Turn them off if you press keys by accident, or use voice control or a screen reader that needs them. Shortcuts with Ctrl keep working.</div></div><button type="button" class="switch" role="switch" aria-checked="${S.singleKeys}" aria-label="Single-key shortcuts" id="sk"></button></div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--s-4)">${col('Anywhere', k('Find or go anywhere', 'Ctrl', 'K') + k('Show these shortcuts', '?') + k('Close, or go back', 'Esc') + k('Switch library', 'G', 'L') + k('Change theme', 'G', 'T') + k('Undo', 'Ctrl', 'Z'))}${col('Go to (G, then)', [['Home', 'H'], ['Sessions', 'S'], ['Beings', 'B'], ['Inventory', 'I'], ['Calendars', 'C'], ['Maps', 'M'], ['Writing', 'W'], ['Social', 'O'], ['Bench', 'R'], ['Account', 'A']].map(([w, c]) => k(w, 'G', c)).join(''))}${col('In a list', k('Move down, up', 'J', 'K') + k('Open', 'Enter') + k('Select', 'X') + k('New', 'N') + k('Edit', 'E') + k('Filter', '/'))}${col('In the editor', k('Bold', 'Ctrl', 'B') + k('Link an entry', 'Ctrl', 'K') + k('Find or go anywhere', 'Ctrl', 'Shift', 'K'))}</div>`, actions: [{ label: 'Done', kind: 'primary', auto: true }], init: (d) => { $('#sk', d).onclick = (e) => { S.singleKeys = !S.singleKeys; e.currentTarget.setAttribute('aria-checked', S.singleKeys); }; } });
}
function openSignOut() {
  const n = S.waiting;
  openDialog({ title: 'Sign out?', label: 'alertdialog', body: n ? `<div class="strip-in" style="--c:var(--warning);border:1px solid var(--c);border-radius:var(--r-ctl);background-image:repeating-linear-gradient(45deg,color-mix(in srgb,var(--c) 22%,transparent) 0 2px,transparent 2px 7px);align-items:flex-start;padding:10px 12px">${ic('waiting')}<span class="msg t-body"><b>${n} change${n > 1 ? 's are' : ' is'} only on this device.</b> ${n > 1 ? 'They have' : 'It has'} not been sent yet. If you sign out now, ${n > 1 ? 'they stay' : 'it stays'} here and ${n > 1 ? 'are' : 'is'} sent when you sign back in on this device.</span></div>` : '<p class="muted t-body">You can sign back in at any time. Everything you changed has been sent.</p>', actions: [{ label: 'Cancel' }, { label: n ? 'Sign out anyway' : 'Sign out', kind: n ? undefined : 'primary', fn: () => toast({ title: 'Signed out', text: 'The prototype does not sign anyone out.' }) }, ...(n ? [{ label: 'Wait and send first', kind: 'primary', fn: () => { if (S.offline) toast({ title: 'Still offline', text: 'Go online to send them.' }); else { S.waiting = 0; updateStatus(); renderStrip(); toast({ title: 'Sent', text: 'Nothing is waiting.' }); } } }] : [])] });
}

/* ---- the controls above the frame (not part of the design) */
const WIDTHS = [['fit', 'Fit'], [430, '430'], [834, '834'], [1440, '1440'], [2200, '2200']];
function buildProto() {
  const g = (label, inner) => `<span class="group"><b>${label}</b>${inner}</span>`;
  const btn = (act, v, t, pressed) => `<button type="button" data-p="${act}" data-v="${v}" aria-pressed="${pressed}">${t}</button>`;
  $('#proto').innerHTML = `<details ${innerWidth >= 900 ? 'open' : ''} style="width:100%"><summary style="cursor:pointer;font-weight:600;color:var(--text-primary)">Prototype controls (not part of the design)</summary><div style="display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin-top:6px">` + g('Width', WIDTHS.map(([v, t]) => btn('width', v, t, v === (S.w || 'fit'))).join('')) + g('Theme', ['system', 'light', 'dark'].map((t) => btn('theme', t, t[0].toUpperCase() + t.slice(1), S.theme === t)).join('')) + g('Libraries', [[1, 'One'], [3, 'Three']].map(([v, t]) => btn('libs', v, t, S.libs === v)).join('')) + g('You are', [['gm', 'GM'], ['player', 'A player']].map(([v, t]) => btn('role', v, t, S.role === v)).join('')) + g('Connection', [[0, 'Online'], [1, 'Offline']].map(([v, t]) => btn('offline', v, t, +S.offline === v)).join('')) + g('Loading', [['normal', 'Normal'], ['slow', 'Slow'], ['once', 'Fails once'], ['always', 'Keeps failing']].map(([v, t]) => btn('load', v, t, S.load === v)).join('')) + g('Show', [['first-run', 'First run'], ['join', 'Join link'], ['states', 'States']].map(([v, t]) => btn('goto', v, t, false)).join('') + btn('conflict', 1, 'Conflict', S.conflict) + btn('error', 1, 'Error toast', false) + btn('public', 1, 'Public repositories', !!S.publicRepos)) + (window.PROTO_EXT ? window.PROTO_EXT() : '') + `<button type="button" data-p="reset" data-v="1">Reset</button></div></details>`;
}
function syncProto() { if (window.PROTO_SYNC) window.PROTO_SYNC(); $$('#proto [data-p]').forEach((b) => { const k = b.dataset.p, v = b.dataset.v; let on = null; if (k === 'width') on = String(S.w || 'fit') === v; else if (k === 'theme') on = S.theme === v; else if (k === 'libs') on = String(S.libs) === v; else if (k === 'role') on = S.role === v; else if (k === 'offline') on = String(+S.offline) === v; else if (k === 'load') on = S.load === v; else if (k === 'conflict') on = S.conflict; else if (k === 'public') on = !!S.publicRepos; if (on !== null) b.setAttribute('aria-pressed', on); }); }
function protoClick(e) {
  const b = e.target.closest('[data-p]'); if (!b) return; const k = b.dataset.p, v = b.dataset.v;
  if (window.PROTO_CLICK && window.PROTO_CLICK(k, v)) { syncProto(); return; }
  if (k === 'width') { S.w = v === 'fit' ? 'fit' : +v; const f = frame(); if (v === 'fit') { f.style.removeProperty('--frame-w'); f.setAttribute('data-fit', ''); } else { f.style.setProperty('--frame-w', v + 'px'); f.removeAttribute('data-fit'); } setTimeout(() => { render(true); }, 340); }
  else if (k === 'theme') { S.theme = v; applyAppearance(); }
  else if (k === 'libs') { S.libs = +v; S.lib = Math.min(S.lib, S.libs - 1); renderHeader(); }
  else if (k === 'role') { S.role = v; render(true); }
  else if (k === 'offline') setOffline(v === '1');
  else if (k === 'load') { S.load = v; if (S.route.startsWith('beings')) render(true); }
  else if (k === 'goto') go(v);
  else if (k === 'conflict') { S.conflict = !S.conflict; const o = DATA.beings.find((x) => x.id === 'orla-venn'); o.state = S.conflict ? 'conflict' : 'synced'; renderStrip(); if (S.route.startsWith('beings')) refreshBeings(); }
  else if (k === 'error') toast({ kind: 'error', title: 'Couldn’t save the note', text: 'The connection dropped. Your text is kept on this device.', action: { label: 'Try again', fn: () => toast({ title: 'Saved' }) } });
  else if (k === 'public') { S.publicRepos = !S.publicRepos; if (S.route === 'first-run') render(true); }
  else if (k === 'reset') { location.hash = '#/home'; location.reload(); }
  syncProto();
}

/* ---- keyboard (D25) */
let gPending = false, gTimer = null;
const GO = { h: 'home', s: 'home', b: 'beings', i: 'board', c: 'stub/calendars', m: 'map', w: 'read', o: 'webs', r: 'stub/bench', a: 'settings' };
if (window.GO_EXT) Object.assign(GO, window.GO_EXT);
document.addEventListener('keydown', (e) => {
  const mod = e.ctrlKey || e.metaKey; const t = e.target;
  const typing = t.matches && (t.matches('input, textarea, select') || t.isContentEditable);
  if (mod && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (t.closest && t.closest('#doc') && !e.shiftKey) { linkEntry(); return; }
    if (OV.el === $('#palette')) { closeOv(); return; }
    openPalette(); return;
  }
  if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey && !typing) { const u = S.undo.pop(); if (u) { e.preventDefault(); u.undo(); toast({ title: 'Undone', text: u.title }); } return; }
  if (OV.el || typing || e.altKey || mod) return;
  if (e.key === '?') { e.preventDefault(); openShortcuts(); return; }
  if (!S.singleKeys) return;
  const k = e.key.toLowerCase();
  if (gPending) { gPending = false; clearTimeout(gTimer); if (k === 'l') { e.preventDefault(); if (S.libs > 1) openLibraryMenu($('#lib-btn')); else toast({ title: 'There is only one library' }); } else if (k === 't') { e.preventDefault(); S.theme = S.theme === 'light' ? 'dark' : S.theme === 'dark' ? 'system' : 'light'; applyAppearance(); syncProto(); toast({ title: 'Theme: ' + S.theme }); } else if (GO[k]) { e.preventDefault(); go(GO[k]); } return; }
  if (k === 'g') { gPending = true; gTimer = setTimeout(() => (gPending = false), 1200); return; }
  if (S.route.startsWith('beings') && BL.phase === 'ready') {
    const list = visibleBeings(); const i = list.findIndex((b) => b.id === S.focus);
    if (k === 'j') { e.preventDefault(); const n = list[Math.min(list.length - 1, i + 1)]; if (n) focusBeing(n.id); }
    else if (k === 'k') { e.preventDefault(); const n = list[Math.max(0, i - 1)]; if (n) focusBeing(n.id); }
    else if (e.key === 'Enter') { e.preventDefault(); focusBeing(S.focus, true); }
    else if (k === 'x') { e.preventDefault(); const id = S.focus; S.selected.has(id) ? S.selected.delete(id) : S.selected.add(id); const cb = $(`[data-sel="${id}"]`); if (cb) cb.checked = S.selected.has(id); refreshBulk(); }
    else if (k === 'n') { e.preventDefault(); openNewEntry(); }
    else if (k === 'e') { toast({ title: 'Editing opens in Beings' }); }
    else if (k === '/') { e.preventDefault(); $('#q').focus(); }
  }
});

/* ---- boot */
function boot() {
  frame().innerHTML = `<div class="app" id="app" data-density="${S.density}"><a class="skip visually-hidden" href="#main" onclick="event.preventDefault();$('#main').focus()">Skip to content</a><div id="shell-inert"><header class="hdr" id="hdr"></header><div class="strip" id="strip"></div><main class="main" id="main" tabindex="-1" aria-label="Content"></main><div class="savebar" id="savebar"></div><div class="status" id="status" role="status" aria-label="Status"></div><nav class="tabbar" id="tabbar"></nav></div><div class="scrim" id="scrim"></div><div class="ov menu" id="menu" role="menu"></div><div class="ov dialog" id="dialog"></div><div class="ov palette" id="palette"></div><div class="ov drawer" id="drawer"></div><div class="ov detail-sheet" id="dsheet"></div><div class="toasts" id="toasts" role="region" aria-label="Messages"></div></div>`;
  $('#frame').setAttribute('data-fit', '');
  applyAppearance();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyAppearance);
  $('#proto').addEventListener('click', protoClick);
  buildProto();
  $('#hdr').addEventListener('click', (e) => {
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.getAttribute('aria-expanded') === 'true') { closeOv(); return; }
    const k = a.dataset.act;
    if (k === 'palette') openPalette(); else if (k === 'lib') openLibraryMenu(a); else if (k === 'acct') openAcct(a); else if (k === 'bell') openBell(a);
  });
  $('#status').addEventListener('click', (e) => { const a = e.target.closest('[data-act="about"]'); if (!a) return; if (OV.el === $('#drawer')) closeOv(); else openAbout(); });
  $('#tabbar').addEventListener('click', (e) => { const a = e.target.closest('[data-act="more"]'); if (a) { if (a.getAttribute('aria-expanded') === 'true') closeOv(); else openMore(a); } });
  $('#strip').addEventListener('click', (e) => { if (e.target.closest('[data-act="review-strip"]')) openConflictReview(); });
  addEventListener('hashchange', () => { if (window.NAV_GUARD && window.NAV_GUARD() === false) return; render(); });
  setInterval(() => { if (!document.hidden) updateStatus(); }, 20000);
  if (!location.hash) location.hash = window.START_ROUTE ? '#/' + window.START_ROUTE : '#/home';
  render(true);
}
boot();

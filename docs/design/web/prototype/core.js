/* Core: state, helpers, appearance, toasts, overlays, the palette. Plain JavaScript, no framework.
   The prototype fakes the server: nothing is saved, nothing is sent. */
const ICONS = window.ICONS_PATH || '../../../../apps/brand/icons.svg';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ic = (n, cls = '') => `<svg class="icon ${cls}" aria-hidden="true"><use href="${ICONS}#icon-${n}"></use></svg>`;
const MARK_PATH = 'M 256 20 C 268 126, 282 193, 309 217 C 333 239, 394 250, 492 256 C 394 262, 333 273, 309 295 C 282 319, 268 386, 256 492 C 244 386, 230 319, 203 295 C 179 273, 118 262, 20 256 C 118 250, 179 239, 203 217 C 230 193, 244 126, 256 20 Z M 256 218 C 261 232, 280 251, 294 256 C 280 261, 261 280, 256 294 C 251 280, 232 261, 218 256 C 232 251, 251 232, 256 218 Z';
const MARK = (cls = '') => `<svg class="${cls}" viewBox="0 0 512 512" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="${MARK_PATH}"></path></svg>`;

const S = {
  route: 'home',
  theme: 'system', density: 'comfortable', motion: 'system',
  libs: 3, lib: 0, role: 'gm', offline: false, waiting: 0, conflict: false,
  load: 'normal', // normal | slow | once | always
  singleKeys: true,
  query: '', filter: { kind: 'All', seen: 'All', state: 'All' },
  selected: new Set(), focus: 'imani-roe', detailOpen: false,
  removed: new Set(), seenOverride: {},
  inv: null, dirty: {}, join: 'preview-out', place: 'outer-ring', zoom: 1, chapter: 2,
  notifications: JSON.parse(JSON.stringify(DATA.notifications)),
  undo: [], lastFocus: null
};
S.inv = DATA.inventory.items.map((i) => ({ ...i }));

try { const a = JSON.parse(localStorage.getItem('web-design-appearance') || '{}'); ['theme', 'density', 'motion'].forEach((k) => { if (a[k]) S[k] = a[k]; }); } catch (e) { /* not available: fine */ }

const frame = () => $('#frame');
const app = () => $('#app');
const W = () => frame().clientWidth;
const isPhone = () => W() <= 720;
const isSmall = () => W() <= 1099;
const isLarge = () => W() >= 1700;
const lib = () => DATA.libraries[S.lib];
const reducedMotion = () => S.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;

function applyAppearance() {
  const dark = S.theme === 'dark' || (S.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.dataset.motion = S.motion === 'reduced' ? 'reduced' : '';
  app().dataset.density = S.density;
  try { localStorage.setItem('web-design-appearance', JSON.stringify({ theme: S.theme, density: S.density, motion: S.motion })); } catch (e) { /* ignore */ }
}

/* ------------------------------------------------------------------ toasts (D26) */
const TOAST_MS = 10000;
function toast(o) {
  const host = $('#toasts');
  const kind = o.kind || 'ok';
  const timed = kind !== 'error';
  const el = document.createElement('div');
  el.className = 'toast';
  el.dataset.kind = kind;
  el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  const icon = kind === 'error' ? 'warning' : kind === 'ok' ? 'select-item' : (o.icon || 'delete');
  el.innerHTML = `${ic(icon)}<div class="t-text"><div class="toast-title">${esc(o.title)}</div>${o.text ? `<div class="t-meta">${esc(o.text)}</div>` : ''}${o.action && kind === 'error' ? `<button type="button" class="btn" style="margin-top:8px" data-t-act>${esc(o.action.label)}</button>` : ''}</div>${o.action && kind !== 'error' ? `<button type="button" class="btn btn--quiet" style="background:var(--fill-soft);font-weight:500" data-t-act>${esc(o.action.label)}</button>` : ''}<button type="button" class="icon-btn" aria-label="Dismiss" data-t-close>${ic('close')}</button>${timed ? '<span class="toast-bar" aria-hidden="true"></span>' : ''}`;
  host.appendChild(el);
  while (host.children.length > 3) dismiss(host.firstElementChild, true);
  let anim = null;
  if (timed) {
    anim = el.querySelector('.toast-bar').animate([{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }], { duration: TOAST_MS, easing: 'linear', fill: 'forwards' });
    anim.onfinish = () => dismiss(el);
    const hold = () => { anim.pause(); anim.currentTime = 0; };
    const release = () => { if (!el.matches(':hover') && !el.contains(document.activeElement)) anim.play(); };
    el.addEventListener('pointerenter', hold); el.addEventListener('pointerleave', release);
    el.addEventListener('focusin', hold); el.addEventListener('focusout', () => setTimeout(release, 0));
  }
  el.addEventListener('click', (e) => {
    if (e.target.closest('[data-t-close]')) dismiss(el);
    if (e.target.closest('[data-t-act]')) { o.action.fn(); dismiss(el); }
  });
  return el;
}
function dismiss(el, now) {
  if (!el || !el.isConnected || el.classList.contains('out')) return;
  if (now || reducedMotion()) { el.remove(); return; }
  el.classList.add('out'); setTimeout(() => el.remove(), 230);
}
/* Do now, offer Undo (D26). `redo` is what Undo calls. */
function withUndo(title, undo, text) {
  S.undo.push({ title, undo });
  toast({ kind: 'undo', title, text, action: { label: 'Undo', fn: () => { undo(); S.undo = S.undo.filter((u) => u.undo !== undo); } } });
}

/* ------------------------------------------------------------------ overlays */
const OV = { el: null, opener: null, onClose: null, modal: false };
function focusables(root) { return $$('a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]', root).filter((e) => e.offsetParent !== null || e === document.activeElement); }
function openOv(el, { modal = true, focus = true, onClose = null } = {}) {
  closeOv(true);
  OV.el = el; OV.opener = document.activeElement; OV.onClose = onClose; OV.modal = modal;
  el.dataset.open = '';
  if (modal) { $('#scrim').dataset.open = ''; $('#shell-inert').inert = true; }
  if (focus) requestAnimationFrame(() => { const f = el.querySelector('[data-autofocus]') || focusables(el)[0]; if (f) f.focus({ preventScroll: true }); });
}
function closeOv(silent) {
  const el = OV.el; if (!el) return;
  delete el.dataset.open; delete $('#scrim').dataset.open; $('#shell-inert').inert = false;
  const cb = OV.onClose, op = OV.opener; OV.el = null; OV.onClose = null;
  if (!silent && op && op.isConnected) op.focus({ preventScroll: true });
  if (cb) cb();
}
document.addEventListener('keydown', (e) => {
  if (!OV.el) return;
  if (e.key === 'Escape') { e.preventDefault(); closeOv(); return; }
  if (e.key === 'Tab') {
    const f = focusables(OV.el); if (!f.length) return;
    const i = f.indexOf(document.activeElement);
    if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && (i === f.length - 1 || i === -1)) { e.preventDefault(); f[0].focus(); }
  }
});
document.addEventListener('pointerdown', (e) => {
  if (!OV.el) return;
  if (e.target.closest('#scrim')) { closeOv(); return; }
  if (!OV.modal && !OV.el.contains(e.target) && !e.target.closest('[data-keep-open]')) closeOv(true);
});

/* A menu: a popover on a tablet and wider, a bottom sheet on a phone (D26) */
function openMenu(anchor, items, { label = 'Menu', align } = {}) {
  const m = $('#menu');
  const sheet = isPhone();
  m.className = 'ov menu' + (sheet ? ' as-sheet' : '');
  m.setAttribute('aria-label', label);
  m.innerHTML = (sheet ? '<div class="sheet-grip"></div>' : '') + items.map((it, i) => {
    if (it.sep) return '<div class="menu-sep" role="separator"></div>';
    if (it.head) return `<div class="menu-head">${it.head}</div>`;
    if (it.text) return `<div class="t-meta" style="padding:6px 10px">${esc(it.text)}</div>`;
    if (it.label && it.heading) return `<div class="menu-label">${esc(it.label)}</div>`;
    const role = it.check !== undefined ? 'menuitemradio' : 'menuitem';
    return `<button type="button" class="menu-item${it.danger ? ' danger' : ''}" role="${role}" ${it.check !== undefined ? `aria-checked="${it.check}"` : ''} data-i="${i}">${it.icon ? ic(it.icon) : ''}<span class="grow">${esc(it.label)}</span>${it.badge ? `<b class="num" style="font-size:var(--fs-meta)">${it.badge}</b>` : ''}${it.kbd ? `<kbd>${esc(it.kbd)}</kbd>` : ''}${it.check ? ic('select-item') : ''}</button>`;
  }).join('');
  m.onclick = (e) => { const b = e.target.closest('.menu-item'); if (!b) return; const it = items[+b.dataset.i]; closeOv(); if (it.fn) setTimeout(it.fn, 0); };
  m.onkeydown = (e) => {
    const list = $$('.menu-item', m); const i = list.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); list[(i + 1) % list.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); list[(i - 1 + list.length) % list.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); list[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); list[list.length - 1].focus(); }
  };
  if (sheet) { m.style.left = m.style.right = m.style.top = m.style.bottom = ''; }
  else {
    const f = frame().getBoundingClientRect(), a = anchor.getBoundingClientRect();
    m.style.left = m.style.right = m.style.bottom = ''; m.style.top = Math.max(8, a.bottom - f.top + 6) + 'px';
    const rightHalf = (a.left + a.width / 2 - f.left) > f.width / 2;
    if (align === 'left' || !rightHalf) m.style.left = Math.max(8, a.left - f.left) + 'px'; else m.style.right = Math.max(8, f.right - a.right) + 'px';
  }
  if (anchor) { anchor.setAttribute('aria-expanded', 'true'); }
  openMenuEl(m, anchor, sheet);
}
function openMenuEl(m, anchor, sheet) {
  openOv(m, { modal: sheet, onClose: () => { if (anchor) anchor.setAttribute('aria-expanded', 'false'); } });
  if (!sheet) requestAnimationFrame(() => { const first = $('.menu-item', m); if (first) first.focus({ preventScroll: true }); });
}

/* A dialog: centered on a desktop, a bottom sheet from the tablet step down (D26) */
function openDialog({ title, body, actions = [], wide = false, init, label }) {
  const d = $('#dialog');
  d.className = 'ov dialog' + (wide ? ' dialog--wide' : '');
  d.setAttribute('role', 'dialog'); d.setAttribute('aria-labelledby', 'dlg-t');
  d.innerHTML = `<div class="sheet-grip"></div><h2 id="dlg-t">${title}</h2><div class="dlg-body">${body}</div><div class="actions">${actions.map((a, i) => `<button type="button" class="btn${a.kind === 'primary' ? ' btn--primary' : ''}${a.kind === 'danger' ? ' btn--danger solid' : ''}" data-a="${i}" ${a.disabled ? 'aria-disabled="true"' : ''} ${a.auto ? 'data-autofocus' : ''}>${esc(a.label)}</button>`).join('')}</div>`;
  d.onclick = (e) => { const b = e.target.closest('[data-a]'); if (!b) return; const a = actions[+b.dataset.a]; if (b.getAttribute('aria-disabled') === 'true') return; if (a.fn) { const keep = a.fn(d); if (keep === false) return; } if (a.close !== false) closeOv(); };
  d.onkeydown = (e) => { if (e.key === 'Enter' && e.target.matches('input')) { e.preventDefault(); const p = $('.btn--primary, .btn--danger', d); if (p) p.click(); } };
  openOv(d, { modal: true });
  if (init) init(d);
  return d;
}
const setDisabled = (btn, off, reason) => { btn.setAttribute('aria-disabled', off ? 'true' : 'false'); if (reason !== undefined) btn.title = off ? reason : ''; };

/* ------------------------------------------------------------------ the palette (D16, D25) */
const PAL = { scope: 'Everything', q: '', i: 0, items: [], mode: 'go', onPick: null };
function palActions() {
  const a = [
    { name: 'New entry…', icon: 'add', kbd: 'N', run: () => openNewEntry() },
    { name: 'Change theme', icon: 'theme-system', run: () => { S.theme = S.theme === 'light' ? 'dark' : S.theme === 'dark' ? 'system' : 'light'; applyAppearance(); toast({ title: 'Theme: ' + S.theme }); } },
    { name: 'Density: Comfortable', icon: 'appearance', run: () => setDensity('comfortable') },
    { name: 'Density: Compact', icon: 'appearance', run: () => setDensity('compact') },
    { name: 'Density: Dense', icon: 'appearance', run: () => setDensity('dense') },
    { name: 'Mark all notifications as read', icon: 'notifications', run: () => markAllRead() },
    { name: 'Appearance…', icon: 'appearance', run: () => openAppearance() },
    { name: 'Show keyboard shortcuts', icon: 'command', kbd: '?', run: () => openShortcuts() },
    { name: S.offline ? 'Go online' : 'Go offline', icon: S.offline ? 'online' : 'offline', run: () => setOffline(!S.offline) },
    { name: 'Sign out…', icon: 'logout', run: () => openSignOut() }
  ];
  if (S.libs > 1) a.splice(1, 0, { name: 'Switch library…', icon: 'library', kbd: 'G L', run: () => openLibraryMenu($('#lib-btn') || $('#acct-btn')) });
  return a;
}
function palData() {
  const q = PAL.q.trim().toLowerCase();
  const entries = [...DATA.beings.map((b) => ({ id: b.id, name: b.name, kind: b.kind, app: 'Beings', appId: 'beings', route: 'beings/' + b.id, blurb: b.blurb, seen: b.seen })), ...DATA.others.map((o) => ({ ...o, seen: 'Everyone' }))];
  const apps = DATA.apps.map((a) => ({ id: a.id, name: a.name, kind: 'Open the app', icon: a.icon, route: a.route, kbd: { sessions: 'G S', beings: 'G B', inventory: 'G I', calendars: 'G C', maps: 'G M', writing: 'G W', bench: 'G R', account: 'G A' }[a.id] }));
  const acts = palActions();
  const m = (s) => !q || s.toLowerCase().includes(q);
  const out = [];
  if (PAL.mode === 'link') { entries.filter((e) => m(e.name)).forEach((e) => out.push({ g: 'Entries', ...e })); return out; }
  const showE = PAL.scope === 'Everything' || PAL.scope === 'Entries';
  const showA = PAL.scope === 'Everything' || PAL.scope === 'Apps';
  const showC = PAL.scope === 'Everything' || PAL.scope === 'Actions';
  if (!q && PAL.scope === 'Everything') { ['mara-quill', 'orbital-station-4', 'chapter-3'].forEach((id) => { const e = entries.find((x) => x.id === id); if (e) out.push({ g: 'Recent', ...e }); }); }
  if (showE) entries.filter((e) => q && m(e.name)).slice(0, 6).forEach((e) => out.push({ g: 'Entries', ...e }));
  if (showA) apps.filter((a) => m(a.name)).forEach((a) => out.push({ g: 'Go to', type: 'app', ...a }));
  if (showC) acts.filter((a) => m(a.name)).forEach((a) => out.push({ g: 'Actions', type: 'action', ...a }));
  return out;
}
function palRender() {
  const p = $('#palette');
  PAL.items = palData();
  if (PAL.i >= PAL.items.length) PAL.i = Math.max(0, PAL.items.length - 1);
  const q = PAL.q.trim();
  const hl = (s) => { if (!q) return esc(s); const i = s.toLowerCase().indexOf(q.toLowerCase()); return i < 0 ? esc(s) : `${esc(s.slice(0, i))}<mark>${esc(s.slice(i, i + q.length))}</mark>${esc(s.slice(i + q.length))}`; };
  let g = '';
  const rows = PAL.items.map((it, i) => {
    const head = it.g !== g ? `<div class="p-group" role="presentation">${it.g}</div>` : ''; g = it.g;
    const icon = it.icon || ({ Person: 'kind-being', Character: 'kind-being', NPC: 'kind-being', Place: 'kind-location', Map: 'map', Item: 'kind-item', Chapter: 'kind-chapter', Collection: 'kind-books', Session: 'kind-session', Library: 'library', Repository: 'kind-repository' }[it.kind] || 'kind-entity');
    return `${head}<div class="p-opt" role="option" id="po${i}" data-i="${i}" aria-selected="${i === PAL.i}">${ic(icon)}<span class="grow">${hl(it.name)}<span class="meta">${esc(it.type === 'action' ? '' : it.kind || '')}</span></span>${it.kbd ? it.kbd.split(' ').map((k) => `<kbd>${k}</kbd>`).join('') : ''}${it.app && !it.type ? `<span class="t-micro">${it.app}</span>` : ''}</div>`;
  }).join('');
  const sel = PAL.items[PAL.i];
  const prev = sel && !sel.type ? `<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px"><span class="detail avatar-lg" style="position:static;border:0;padding:0;width:56px;height:56px;flex:none;border-radius:12px;background:var(--surface-selected);display:inline-flex;align-items:center;justify-content:center;font-family:var(--font-display);font-size:1.4rem">${esc(sel.name.split(' ').map((w) => w[0]).slice(0, 2).join(''))}</span><div><div class="t-title" style="font-size:1.4rem">${esc(sel.name)}</div><div class="t-meta">${esc(sel.kind)} · ${esc(sel.app)}</div></div></div><p class="muted" style="margin-bottom:12px">${esc(sel.blurb || '')}</p><p class="t-meta" style="margin-bottom:14px">Seen by ${esc(sel.seen || 'Everyone')}</p><div class="menu-item" style="background:var(--surface-selected);pointer-events:none"><span class="grow">Open in ${esc(sel.app)}</span><kbd>Enter</kbd></div>` : '<p class="muted">Choose an entry to preview it.</p>';
  p.innerHTML = `<div class="p-in">${ic('search')}<input id="p-input" type="text" role="combobox" aria-expanded="true" aria-controls="p-list" aria-activedescendant="po${PAL.i}" aria-label="${PAL.mode === 'link' ? 'Link an entry' : 'Find or go anywhere'}" placeholder="${PAL.mode === 'link' ? 'Link an entry' : 'Find or go anywhere'}" value="${esc(PAL.q)}" autocomplete="off"><kbd>Esc</kbd></div>${PAL.mode === 'link' ? '' : `<div class="p-tabs" role="tablist" aria-label="Narrow to">${['Everything', 'Entries', 'Apps', 'Actions'].map((t) => `<button type="button" role="tab" aria-selected="${PAL.scope === t}" data-scope="${t}" tabindex="-1">${t}</button>`).join('')}</div>`}<div class="p-body"><div class="p-list" id="p-list" role="listbox" aria-label="Results">${rows || '<div class="p-empty">Nothing matches. Try a different word.</div>'}</div><aside class="p-prev" aria-label="Preview">${prev}</aside></div><div class="p-foot"><span>Up and down to move</span><span>Enter to ${PAL.mode === 'link' ? 'link' : 'open'}</span><span>Tab to narrow</span><span>Esc to close</span><span style="flex:1"></span><span>? for all shortcuts</span></div>`;
  const inp = $('#p-input'); inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
  const act = $('#po' + PAL.i, p); if (act) act.scrollIntoView({ block: 'nearest' });
}
function openPalette(scope = 'Everything', mode = 'go', onPick = null) {
  PAL.scope = scope; PAL.q = ''; PAL.i = 0; PAL.mode = mode; PAL.onPick = onPick;
  const p = $('#palette'); p.className = 'ov palette';
  p.setAttribute('role', 'dialog'); p.setAttribute('aria-label', mode === 'link' ? 'Link an entry' : 'Find or go anywhere');
  p.onkeydown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); PAL.i = Math.min(PAL.items.length - 1, PAL.i + 1); palRender(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); PAL.i = Math.max(0, PAL.i - 1); palRender(); }
    else if (e.key === 'Enter') { e.preventDefault(); palPick(PAL.i); }
    else if (e.key === 'Tab' && PAL.mode !== 'link') { e.preventDefault(); const t = ['Everything', 'Entries', 'Apps', 'Actions']; PAL.scope = t[(t.indexOf(PAL.scope) + (e.shiftKey ? 3 : 1)) % 4]; PAL.i = 0; palRender(); }
  };
  p.oninput = (e) => { if (e.target.id === 'p-input') { PAL.q = e.target.value; PAL.i = 0; palRender(); } };
  p.onclick = (e) => { const o = e.target.closest('.p-opt'); if (o) palPick(+o.dataset.i); const t = e.target.closest('[data-scope]'); if (t) { PAL.scope = t.dataset.scope; PAL.i = 0; palRender(); } };
  palRender();
  openOv(p, { modal: true, focus: false });
  $('#p-input').focus();
}
function palPick(i) {
  const it = PAL.items[i]; if (!it) return;
  const cb = PAL.onPick; closeOv();
  setTimeout(() => {
    if (cb) { cb(it); return; }
    if (it.type === 'action') it.run(); else go(it.route);
  }, 0);
}

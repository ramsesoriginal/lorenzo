/* Pages: one function per template. Each returns HTML for #main; a few have an `after` that binds behaviour. */
const AUD_ICON = { 'GM only': 'private', 'Some characters': 'kind-beings', 'Player note': 'kind-being' };
const ST = { synced: ['Synced', 'select-item'], waiting: ['Waiting to sync', 'waiting'], stale: ['Out of date', 'stale'], conflict: ['Needs review', 'conflict'] };
const stChip = (k) => `<span class="st st--${k}">${ic(ST[k][1])}<span>${ST[k][0]}</span></span>`;
const visBadge = (seen) => seen === 'Everyone' ? `<span class="everyone">Everyone</span>` : `<span class="vis">${ic(AUD_ICON[seen] || 'private')}${esc(seen)}</span>`;
const slot = (id, text, extra = '') => `<div class="art-slot ${extra}" role="img" aria-label="Illustration slot: ${esc(id)}">Illustration<br>${esc(id)}<br>${esc(text)}</div>`;
const appOf = (id) => DATA.apps.find((a) => a.id === id);

/* ---------------------------------------------------------------- home (D16, D21) */
function pHome() {
  const s = DATA.sessions[0];
  const tile = (a) => `<a class="card tile" href="#/${a.route}">${ic(a.icon)}<span><b>${a.name}</b><span class="t-meta" style="display:block">${a.desc}</span></span></a>`;
  return `<div class="page page--wide page-enter">
  <h1 class="t-title page-title">Sessions</h1><p class="page-sub">${esc(lib())}</p>
  <div class="grid top stagger">
    <section class="card" aria-labelledby="h-next" style="padding:var(--s-4)"><div class="t-meta">Next session</div><h2 id="h-next" class="t-title" style="font-size:1.5rem;margin:2px 0 6px">${esc(s.name)}</h2><p class="muted">${esc(s.date)} · <span class="stat-count num" style="--stat-value:4"></span> of 5 players confirmed</p><div style="display:flex;gap:8px;margin-top:14px"><button type="button" class="btn btn--primary" data-act="toast" data-title="Preparing opens in Sessions">Prepare</button><button type="button" class="btn" data-act="toast" data-title="The session opens in Sessions">Open</button></div></section>
    <section class="card" aria-labelledby="h-dec" style="padding:var(--s-4)"><div class="t-meta">Needs a decision</div><h2 id="h-dec" class="visually-hidden">Needs a decision</h2><p style="margin:6px 0">2 scenes have no order yet.</p><p>Mara asked to move Thursday to Friday.</p></section>
  </div>
  <h2 class="sec-title">Continue</h2>
  <div class="grid cont stagger">
    <a class="card tile reveal" href="#/home" style="display:block"><b>Night on Station 4</b><span class="t-meta" style="display:block">Session · Sessions · edited today</span></a>
    <a class="card tile reveal" href="#/beings/harbour-master" style="display:block"><b>Harbour master</b><span class="t-meta" style="display:block">Character · Beings · edited yesterday</span></a>
    <a class="card tile reveal" href="#/read" style="display:block"><b>Chapter 3: The blackout</b><span class="t-meta" style="display:block">Chapter · Writing · edited 2 days ago</span></a>
  </div>
  <h2 class="sec-title">What do you want to do?</h2>
  <div class="grid apps stagger">${DATA.apps.map(tile).join('')}</div></div>`;
}

/* ---------------------------------------------------------------- beings: list and detail (D20, D21, D22) */
const BL = { phase: 'ready', attempt: 0, timer: null, msgTimer: null, extra: [] };
const allBeings = () => [...BL.extra, ...DATA.beings].filter((b) => !S.removed.has(b.id)).map((b) => ({ ...b, seen: S.seenOverride[b.id] || b.seen }));
const visibleBeings = () => allBeings().filter((b) => (!S.query || b.name.toLowerCase().includes(S.query.toLowerCase())) && (S.filter.kind === 'All' || b.kind === S.filter.kind) && (S.filter.seen === 'All' || b.seen === S.filter.seen) && (S.filter.state === 'All' || ST[b.state][0] === S.filter.state));
function pBeings() {
  const f = S.filter; const fl = (k, label) => f[k] === 'All' ? label : `${label}: ${f[k]}`;
  return `<div class="page page--wide page-enter" style="max-width:1760px"><div class="ld"><div class="lst">
  <div class="toolbar"><h1 class="t-title" style="font-size:1.75rem;margin-right:auto">All beings</h1></div>
  <div class="toolbar"><div class="search"><span class="visually-hidden"><label for="q">Search beings</label></span>${ic('search')}<input id="q" class="input" type="search" placeholder="Search beings" value="${esc(S.query)}" autocomplete="off"></div>
   <button type="button" class="btn" data-act="filter" data-k="kind" aria-haspopup="menu" aria-expanded="false">${esc(fl('kind', 'Kind'))}</button><button type="button" class="btn" data-act="filter" data-k="seen" aria-haspopup="menu" aria-expanded="false">${esc(fl('seen', 'Seen by'))}</button><button type="button" class="btn" data-act="filter" data-k="state" aria-haspopup="menu" aria-expanded="false">${esc(fl('state', 'State'))}</button>
   <span class="grow" style="flex:1"></span>
   <div class="seg only-wide" role="radiogroup" aria-label="Density">${['comfortable', 'compact', 'dense'].map((d) => `<button type="button" role="radio" aria-checked="${S.density === d}" data-act="density" data-d="${d}">${d[0].toUpperCase() + d.slice(1)}</button>`).join('')}</div>
   <button type="button" class="btn btn--primary" data-act="new">${ic('add')}New being</button></div>
  <div class="bulk" id="bulk"><div><div class="bulk-in" id="bulk-in"></div></div></div>
  <div id="bl" role="table" aria-label="Beings"></div></div>
  <aside class="detail only-wide" id="detail" aria-label="Details"></aside>
  <aside class="detail related" id="related" aria-label="Used in"></aside></div></div>`;
}
function rowHtml(b) {
  return `<div class="row" role="row" data-id="${b.id}" aria-selected="${S.focus === b.id}"><div class="cb" role="cell"><label><input type="checkbox" data-sel="${b.id}" aria-label="Select ${esc(b.name)}" ${S.selected.has(b.id) ? 'checked' : ''}></label></div><div class="name" role="cell">${esc(b.name)}<span class="sub">${esc(b.kind)} · ${esc(b.seen)}</span></div><div class="kind muted" role="cell">${esc(b.kind)}</div><div class="seen" role="cell">${visBadge(b.seen)}</div><div class="state" role="cell">${stChip(b.state)}</div><div class="more" role="cell"><button type="button" class="icon-btn" aria-label="Actions for ${esc(b.name)}" aria-haspopup="menu" aria-expanded="false" data-act="row-menu" data-id="${b.id}">${ic('more')}</button></div></div>`;
}
function detailHtml(b, sheet) {
  if (!b) return '<p class="muted">Choose a being to see its details.</p>';
  const note = { waiting: ['waiting', 'Waiting to sync.', '2 changes are saved on this device.'], stale: ['stale', 'Out of date.', 'A value here could not be recalculated just now.'], conflict: ['conflict', 'Needs review.', 'Mara Quill changed this while you were editing.'] }[b.state];
  return `${sheet ? `<div class="sheet-grip only-phone" style="display:block"></div><div style="display:flex;justify-content:flex-end"><button type="button" class="icon-btn" aria-label="Close" data-act="close-detail">${ic('close')}</button></div>` : ''}<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px"><span class="avatar-lg detail" style="position:static;border:0;padding:0;width:56px;height:56px;flex:none;display:inline-flex;align-items:center;justify-content:center;border-radius:12px;background:var(--surface-selected);font-family:var(--font-display);font-size:1.4rem">${esc(b.initials)}</span><div><h2 class="t-title" style="font-size:1.5rem">${esc(b.name)}</h2><div class="t-meta">${esc(b.kind)} · at ${esc(b.place || 'nowhere in particular')}</div></div></div>
  ${note ? `<div class="strip-in" style="--c:var(--${b.state === 'conflict' ? 'danger' : 'warning'});border:1px solid var(--c);border-radius:var(--r-ctl);margin-bottom:12px;${b.state === 'conflict' ? 'background-image:repeating-linear-gradient(45deg,color-mix(in srgb,var(--c) 22%,transparent) 0 2px,transparent 2px 7px),repeating-linear-gradient(-45deg,color-mix(in srgb,var(--c) 22%,transparent) 0 2px,transparent 2px 7px)' : 'background-image:repeating-linear-gradient(45deg,color-mix(in srgb,var(--c) 22%,transparent) 0 2px,transparent 2px 7px)'}">${ic(note[0])}<span class="msg"><b>${note[1]}</b> ${note[2]}</span></div>` : ''}
  <p class="muted">${esc(b.blurb)}</p>
  <dl><dt>Seen by</dt><dd>${esc(b.seen)}</dd><dt>Link name</dt><dd><code>${b.id}</code></dd><dt>Changed</dt><dd>Today, 09:40</dd></dl>
  <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn btn--primary" data-act="toast" data-title="${esc(b.name)} opens in Beings">Open</button><button type="button" class="btn" data-act="duplicate" data-id="${b.id}">Duplicate</button>${b.state === 'conflict' ? '<button type="button" class="btn" data-act="review">Review changes</button>' : ''}</div>`;
}
function relatedHtml(b) {
  if (!b) return '';
  return `<h2 class="sec-title" style="margin-top:0">Used in</h2><a class="l" style="display:block;padding:8px 0;border-top:1px solid var(--border-subtle);text-decoration:none;color:var(--text-primary)" href="#/home">Night on Station 4<span class="t-meta" style="display:block">Scene · Sessions ${ic('next')}</span></a><a style="display:block;padding:8px 0;border-top:1px solid var(--border-subtle);text-decoration:none;color:var(--text-primary)" href="#/read">Chapter 3: The blackout<span class="t-meta" style="display:block">Chapter · Writing ${ic('next')}</span></a><a style="display:block;padding:8px 0;border-top:1px solid var(--border-subtle);text-decoration:none;color:var(--text-primary)" href="#/map">Outer ring<span class="t-meta" style="display:block">Map · Maps ${ic('next')}</span></a>`;
}
function skeletonList(msg) {
  return `<div role="status" aria-label="Loading beings">${Array.from({ length: 7 }, (_, i) => `<div class="row" style="grid-template-columns:44px minmax(0,1fr) 120px;cursor:default"><span></span><div class="skel" style="width:${50 + (i * 13) % 40}%"></div><div class="skel" style="width:70%"></div></div>`).join('')}<p class="muted" style="padding:var(--s-3) 0" id="load-msg">${msg || ''}</p></div>`;
}
function errorState(n, giveUp) {
  return `<div class="state-cell" style="margin-top:var(--s-3)">${ic('warning')}<div class="t-sub">Couldn’t load beings</div><div class="muted" style="max-width:340px">${giveUp ? 'The connection dropped before this finished. Nothing you wrote is lost.' : `The connection dropped. Trying again in a moment (${n}).`}</div><div class="t-code t-meta">503 · request 4f2a91</div><div class="acts"><button type="button" class="btn btn--primary" data-act="retry">Try again</button></div></div>`;
}
function startLoad() {
  clearTimeout(BL.timer); clearTimeout(BL.msgTimer);
  BL.attempt = 0;
  attempt();
}
function attempt() {
  const host = $('#bl'); if (!host) return;
  BL.attempt++;
  const fail = S.load === 'always' || (S.load === 'once' && BL.attempt === 1);
  if (S.load === 'normal') { BL.phase = 'ready'; refreshBeings(); return; }
  BL.phase = 'loading';
  host.innerHTML = skeletonList('');
  BL.msgTimer = setTimeout(() => { const m = $('#load-msg'); if (m) m.textContent = 'Still loading. This is taking longer than usual.'; }, 900);
  BL.timer = setTimeout(() => {
    if (!$('#bl')) return;
    if (!fail) { BL.phase = 'ready'; refreshBeings(); return; }
    if (BL.attempt >= 3) { BL.phase = 'error'; $('#bl').innerHTML = errorState(0, true); return; }
    let n = BL.attempt === 1 ? 3 : 4;
    BL.phase = 'error'; $('#bl').innerHTML = errorState(n, false);
    (function tick() { const el = $('#bl .muted'); if (!el || BL.phase !== 'error') return; if (n <= 0) { attempt(); return; } el.textContent = `The connection dropped. Trying again in a moment (${n}).`; n--; BL.timer = setTimeout(tick, 1000); })();
  }, 1500);
}
function afterBeings() {
  startLoad();
  const q = $('#q');
  q.addEventListener('input', () => { S.query = q.value; refreshRows(); });
  const m = $('#main');
  m.onclick = (e) => {
    const a = e.target.closest('[data-act]');
    if (a) { beingsAct(a, e); return; }
    const cb = e.target.closest('[data-sel]');
    if (cb) { cb.checked ? S.selected.add(cb.dataset.sel) : S.selected.delete(cb.dataset.sel); refreshBulk(); return; }
    const row = e.target.closest('.row[data-id]');
    if (row && !e.target.closest('label, button')) focusBeing(row.dataset.id, true);
  };
}
function refreshBeings() { refreshRows(); refreshBulk(); refreshDetail(); }
function refreshRows() {
  const host = $('#bl'); if (!host || BL.phase !== 'ready') return;
  const list = visibleBeings();
  const head = `<div class="tbl-head" role="row"><span role="columnheader"><span class="visually-hidden">Select</span></span><span role="columnheader">Name</span><span role="columnheader">Kind</span><span role="columnheader">Seen by</span><span role="columnheader">State</span><span role="columnheader"><span class="visually-hidden">Actions</span></span></div>`;
  host.innerHTML = list.length ? head + list.map(rowHtml).join('') : `<div class="state-cell" style="margin-top:var(--s-3)">${ic('search')}<div class="t-sub">No beings match</div><div class="muted">Try a different word, or clear the filters.</div><div class="acts"><button type="button" class="btn" data-act="clear">Clear filters</button></div></div>`;
  const total = allBeings().length;
  S.meta = `${list.length} of ${total} beings`; updateStatus();
}
function refreshBulk() {
  const b = $('#bulk'); if (!b) return;
  const n = S.selected.size;
  if (n) $('#bulk-in').innerHTML = `<b class="num">${n} selected</b><button type="button" class="btn" data-act="bulk-seen">Change who sees them</button><button type="button" class="btn" data-act="toast" data-title="Moved ${n} (nothing is saved in the prototype)">Move to…</button><button type="button" class="btn btn--danger" data-act="bulk-delete">Delete</button><button type="button" class="btn btn--quiet" data-act="bulk-clear">Clear</button>`;
  b.toggleAttribute('data-open', n > 0);
}
function refreshDetail() {
  const b = allBeings().find((x) => x.id === S.focus);
  const d = $('#detail'); if (d) d.innerHTML = detailHtml(b);
  const r = $('#related'); if (r) r.innerHTML = relatedHtml(b);
  const s = $('#dsheet'); if (s) s.innerHTML = detailHtml(b, true);
}
function focusBeing(id, open) {
  S.focus = id;
  $$('.row[data-id]').forEach((r) => r.setAttribute('aria-selected', r.dataset.id === id));
  refreshDetail();
  if (open && isSmall()) { const s = $('#dsheet'); s.className = 'ov detail-sheet'; s.setAttribute('role', 'dialog'); s.setAttribute('aria-label', 'Details'); s.onclick = (e) => { if (e.target.closest('[data-act="close-detail"]')) closeOv(); else { const a = e.target.closest('[data-act]'); if (a) beingsAct(a, e); } }; openOv(s, { modal: isPhone() }); }
}
function beingsAct(a, e) {
  const act = a.dataset.act, id = a.dataset.id;
  if (act === 'toast') toast({ title: a.dataset.title });
  else if (act === 'new') openNewEntry();
  else if (act === 'retry') startLoad();
  else if (act === 'clear') { S.filter = { kind: 'All', seen: 'All', state: 'All' }; S.query = ''; go('beings'); }
  else if (act === 'density') setDensity(a.dataset.d);
  else if (act === 'filter') filterMenu(a);
  else if (act === 'row-menu') rowMenu(a, id);
  else if (act === 'duplicate') { const b = allBeings().find((x) => x.id === id); const copy = { ...b, id: b.id + '-copy', name: b.name + ' (copy)', state: S.offline ? 'waiting' : 'synced' }; BL.extra.unshift(copy); refreshRows(); withUndo(`Duplicated ${b.name}`, () => { BL.extra = BL.extra.filter((x) => x.id !== copy.id); refreshRows(); }); }
  else if (act === 'review') openConflictReview();
  else if (act === 'bulk-clear') { S.selected.clear(); $$('[data-sel]').forEach((c) => (c.checked = false)); refreshBulk(); }
  else if (act === 'bulk-delete') { const ids = [...S.selected]; ids.forEach((i) => S.removed.add(i)); S.selected.clear(); refreshBeings(); withUndo(`${ids.length} deleted`, () => { ids.forEach((i) => S.removed.delete(i)); refreshBeings(); }); }
  else if (act === 'bulk-seen') seenMenu(a, [...S.selected]);
}
function filterMenu(btn) {
  const k = btn.dataset.k;
  const opts = { kind: ['All', 'Character', 'NPC'], seen: ['All', 'Everyone', 'GM only', 'Some characters', 'Player note'], state: ['All', 'Synced', 'Waiting to sync', 'Out of date', 'Needs review'] }[k];
  openMenu(btn, [{ label: { kind: 'Kind', seen: 'Seen by', state: 'State' }[k], heading: true }, ...opts.map((o) => ({ label: o, check: S.filter[k] === o, fn: () => { S.filter[k] = o; go('beings'); } }))], { label: 'Filter', align: 'left' });
}
function rowMenu(btn, id) {
  const b = allBeings().find((x) => x.id === id);
  openMenu(btn, [
    { label: 'Open', kbd: 'Enter', fn: () => focusBeing(id, true) },
    { label: 'Edit', kbd: 'E', fn: () => toast({ title: `${b.name} opens in Beings to edit` }) },
    { label: 'Duplicate', fn: () => beingsAct({ dataset: { act: 'duplicate', id } }) },
    { label: 'Move to…', fn: () => toast({ title: 'Choosing where to move it opens a picker' }) },
    { label: 'Change who sees it…', fn: () => seenMenu(btn, [id]) },
    { sep: true },
    { label: 'Delete', danger: true, fn: () => { S.removed.add(id); S.selected.delete(id); refreshBeings(); withUndo(`${b.name} deleted`, () => { S.removed.delete(id); refreshBeings(); }); } }
  ], { label: `Actions for ${b.name}` });
}
function seenMenu(btn, ids) {
  openMenu(btn, [{ label: 'Who can see it', heading: true }, ...['Everyone', 'GM only', 'Some characters', 'Player note'].map((a) => ({ label: a, icon: AUD_ICON[a], fn: () => { const prev = ids.map((i) => [i, S.seenOverride[i]]); ids.forEach((i) => (S.seenOverride[i] = a)); refreshBeings(); withUndo(`Now seen by ${a}`, () => { prev.forEach(([i, v]) => { if (v === undefined) delete S.seenOverride[i]; else S.seenOverride[i] = v; }); refreshBeings(); }, `${ids.length} being${ids.length > 1 ? 's' : ''}`); } }))], { label: 'Change who sees it', align: 'left' });
}
function openNewEntry() {
  openDialog({ title: 'New being', body: `<div style="display:flex;flex-direction:column;gap:var(--s-3)"><div><label class="label" for="ne-n">Name</label><input id="ne-n" class="input" type="text" value="Harbour office" data-autofocus></div><div><label class="label" for="ne-k">Kind</label><span class="selectwrap"><select id="ne-k" class="select"><option>Character</option><option>NPC</option></select>${ic('expand')}</span></div><div><label class="label" for="ne-i">At</label><span class="selectwrap"><select id="ne-i" class="select"><option>Nowhere in particular</option><option>Harbour</option><option>Orbital Station 4</option></select>${ic('expand')}</span><div class="help">You can change this later.</div></div></div>`,
    actions: [{ label: 'Cancel' }, { label: 'Create being', kind: 'primary', fn: (d) => { const n = $('#ne-n', d).value.trim() || 'Untitled'; const e = { id: 'new-' + Date.now(), name: n, kind: $('#ne-k', d).value, seen: 'GM only', state: S.offline ? 'waiting' : 'synced', blurb: 'Nothing written yet.', initials: n.slice(0, 2).toUpperCase(), place: $('#ne-i', d).value }; BL.extra.unshift(e); if (S.offline) { S.waiting++; renderStrip(); } if (S.route.startsWith('beings')) refreshBeings(); toast({ title: `${n} created`, text: S.offline ? 'Saved on this device. It is sent when you are back online.' : undefined }); } }] });
}
function openConflictReview() {
  openDialog({ title: 'Review changes to Orla Venn', wide: true, body: `<p class="muted" style="margin-bottom:var(--s-3)">Mara Quill changed the description at 19:38. Yours and theirs both exist. Choose, field by field, what stays.</p><div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--s-3)"><div class="card"><div class="t-micro">The version you started from</div><p style="margin-top:6px">An inspector with one question.</p></div><div class="card"><div class="t-micro">Yours</div><p style="margin-top:6px">An inspector with one question and a long memory.</p></div><div class="card"><div class="t-micro">Theirs, Mara Quill</div><p style="margin-top:6px">An inspector who stopped asking questions.</p></div></div>`, actions: [{ label: 'Cancel' }, { label: 'Take theirs', fn: resolveConflict }, { label: 'Keep mine', kind: 'primary', fn: resolveConflict }] });
}
function resolveConflict() { const b = DATA.beings.find((x) => x.id === 'orla-venn'); b.state = 'synced'; S.conflict = false; renderStrip(); if (S.route.startsWith('beings')) refreshBeings(); toast({ title: 'Conflict resolved' }); }

/* ---------------------------------------------------------------- board (D21) */
const carried = () => 25 + S.inv.filter((i) => i.col < 2).reduce((n, i) => n + i.w, 0);
function pBoard() {
  return `<div class="page page--wide page-enter"><div style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:var(--s-3);margin-bottom:var(--s-4)"><div><h1 class="t-title">Imani Roe</h1><p class="muted">Character · what she carries</p></div><div style="min-width:240px;flex:0 1 320px"><div style="display:flex;justify-content:space-between;font-size:var(--fs-meta);color:var(--text-secondary);margin-bottom:4px"><span>Carried weight</span><span class="num" id="wtxt"></span></div><div class="meter" role="progressbar" aria-label="Carried weight" aria-valuemin="0" aria-valuemax="${DATA.inventory.capacity}" id="wbar"><span></span></div></div></div><div class="board" id="board"></div></div>`;
}
function afterBoard() { refreshBoard(); $('#main').onclick = (e) => { const b = e.target.closest('[data-item]'); if (b) itemMenu(b, b.dataset.item); }; }
function refreshBoard(movedId) {
  const board = $('#board'); if (!board) return;
  board.innerHTML = DATA.inventory.columns.map((c, ci) => `<section class="col" aria-labelledby="c${ci}"><h2 id="c${ci}">${c}<span class="num">${S.inv.filter((i) => i.col === ci).length}</span></h2>${S.inv.filter((i) => i.col === ci).map((i) => `<div class="item${i.id === movedId ? ' new' : ''}"><span style="font-weight:500">${esc(i.name)}</span><span style="display:inline-flex;align-items:center;gap:4px"><span class="w num">${i.w} lb</span><button type="button" class="icon-btn" aria-label="Actions for ${esc(i.name)}" aria-haspopup="menu" aria-expanded="false" data-item="${i.id}">${ic('more')}</button></span></div>`).join('') || '<p class="t-meta">Nothing here.</p>'}</section>`).join('');
  const w = carried(), cap = DATA.inventory.capacity;
  $('#wtxt').innerHTML = `<span class="stat-count" style="--stat-value:${w}"></span> of ${cap} lb`;
  $('#wbar').setAttribute('aria-valuenow', w); $('#wbar span').style.width = Math.min(100, w / cap * 100) + '%';
  S.meta = `Carried ${w} of ${cap} lb`; updateStatus();
}
function itemMenu(btn, id) {
  const it = S.inv.find((x) => x.id === id);
  openMenu(btn, [{ label: 'Move to', heading: true }, ...DATA.inventory.columns.map((c, ci) => ({ label: c, check: it.col === ci, fn: () => { const from = it.col; if (from === ci) return; it.col = ci; refreshBoard(id); withUndo(`${it.name} moved to ${c}`, () => { it.col = from; refreshBoard(id); }); } })), { sep: true }, { label: 'Delete', danger: true, fn: () => { const i = S.inv.indexOf(it); S.inv.splice(i, 1); refreshBoard(); withUndo(`${it.name} deleted`, () => { S.inv.splice(i, 0, it); refreshBoard(it.id); }); } }], { label: `Actions for ${it.name}` });
}

/* ---------------------------------------------------------------- reading (D21: a 680px measure) */
function pRead() {
  const P = [
    'The lights went out a little after nineteen forty. Nobody on the station said anything for a moment; the hum of the air system was the only thing left, and then even that faltered.',
    '<a href="#/beings/imani-roe">Imani</a> counted to ten, the way her mother had taught her, and reached for the lantern she had been told to leave on the shelf by the door.',
    'Down the ring, a door closed. It was not a loud sound. It was the kind a person makes when they are trying very hard to be somewhere else.',
    'The second dock had been quiet since Tuesday. Everyone said so. Nobody said why, and the maintenance unit logged it, as it logged everything, and reported nothing.'
  ];
  const more = ['Mara kept two ledgers. The large one was for the station and the small one was for herself, and in all the years she had worked there only one of them had ever been wrong.', 'By the time the emergency lamps came on, the corridor had filled with people holding things: a blanket, a child, a tool, a cup that was still warm. Nobody asked who was missing.', 'Behind her, somebody laughed, once, and stopped.', 'She took the lantern down from the shelf. It was warmer than it should have been.'];
  const restricted = S.role === 'gm' ? `<div class="restricted"><span class="vis" style="flex:none">${ic('private')}GM only</span><div>The lantern was not left on the shelf by accident. Only the GM knows who moved it.</div></div>` : '';
  return `<div class="read-progress" aria-hidden="true"></div><div class="page page--capped page-enter"><div class="reading"><article><p class="t-meta" style="margin-bottom:var(--s-2)">Manuscripts / The Blackout / Chapter 3</p><h1 class="t-title" style="margin-bottom:var(--s-2)">Chapter 3: The blackout</h1><p class="muted" style="margin-bottom:var(--s-4)">Dana Okafor · 6 min read · updated 2 days ago</p>
  <h2 id="s1" class="t-sub" style="margin-bottom:var(--s-2)">The dark</h2>${P.map((p) => `<p class="t-reading reveal">${p}</p>`).join('')}
  <div class="fig" style="overflow:hidden;border-radius:var(--r-surf);height:260px"><div class="art-slot parallax" style="height:316px;margin-top:-28px">Illustration slot<br>Picture: the outer ring in the dark</div></div><p class="t-meta" style="margin-bottom:var(--s-4)">The outer ring, seen from the dock. Picture by the author.</p>
  <h2 id="s2" class="t-sub" style="margin-bottom:var(--s-2)">The lantern</h2>${restricted}${more.slice(0, 2).map((p) => `<p class="t-reading reveal">${p}</p>`).join('')}
  <h2 id="s3" class="t-sub" style="margin:var(--s-4) 0 var(--s-2)">Behind her</h2>${more.slice(2).map((p) => `<p class="t-reading reveal">${p}</p>`).join('')}${P.slice(0, 2).map((p) => `<p class="t-reading reveal">${p}</p>`).join('')}</article>
  <nav class="toc" aria-label="On this page"><div class="t-micro" style="margin-bottom:8px">On this page</div><a href="#s1" data-toc="s1" aria-current="true">The dark</a><a href="#s2" data-toc="s2">The lantern</a><a href="#s3" data-toc="s3">Behind her</a></nav></div></div>`;
}
function afterRead() {
  const m = $('#main');
  const upd = () => { let cur = 's1'; ['s1', 's2', 's3'].forEach((id) => { const el = $('#' + id); if (el && el.getBoundingClientRect().top - m.getBoundingClientRect().top < 140) cur = id; }); $$('[data-toc]').forEach((a) => a.setAttribute('aria-current', a.dataset.toc === cur)); };
  m.onscroll = upd; m.onclick = (e) => { const a = e.target.closest('[data-toc]'); if (a) { e.preventDefault(); $('#' + a.dataset.toc).scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' }); } };
}

/* ---------------------------------------------------------------- editor (D21: autosave) */
function pWrite() {
  return `<div class="editor-wrap page-enter"><nav class="outline" aria-label="Outline"><div class="t-micro" style="padding:0 8px 8px">The Blackout</div>${DATA.outline.map((o, i) => `<a href="#/write" data-ch="${i}" ${i === S.chapter ? 'aria-current="true"' : ''}>${o}</a>`).join('')}</nav><div class="editor-main"><div class="etoolbar" role="toolbar" aria-label="Formatting"><button type="button" class="btn only-phone" data-act="chapter-menu">Chapter 3 ${ic('expand')}</button><button type="button" class="icon-btn" aria-label="Bold" aria-pressed="false" data-cmd="bold">${ic('bold')}</button><button type="button" class="icon-btn" aria-label="Italic" aria-pressed="false" data-cmd="italic">${ic('italic')}</button><button type="button" class="btn btn--quiet" data-act="link-entry">${ic('link')}Link an entry</button><button type="button" class="btn btn--quiet only-wide" data-act="toast" data-title="Pictures are chosen in a picker">${ic('picture')}Picture</button><span class="grow"></span><span id="save-state" class="t-meta" role="status" style="display:inline-flex;align-items:center;gap:6px"></span></div><div class="editor-scroll scroll-fade"><div class="editor-doc" contenteditable="true" role="textbox" aria-multiline="true" aria-label="Chapter 3: The blackout" id="doc"><h1 class="t-title">Chapter 3: The blackout</h1><p class="t-reading">The lights went out a little after nineteen forty. Nobody on the station said anything for a moment; the hum of the air system was the only thing left, and then even that faltered.</p><p class="t-reading">Imani counted to ten, the way her mother had taught her, and reached for the lantern she had been told to leave on the shelf by the door.</p></div></div></div></div>`;
}
let saveTimer = null;
function setSave(kind) {
  const el = $('#save-state'); if (!el) return;
  el.innerHTML = { saving: `${ic('refresh', 'spin')}Saving…`, saved: `<span style="color:var(--success);display:inline-flex">${ic('select-item')}</span>Saved`, local: `<span style="color:var(--warning);display:inline-flex">${ic('local-only')}</span>Saved on this device` }[kind];
}
function words() { const d = $('#doc'); return d ? (d.innerText.trim().match(/\S+/g) || []).length : 0; }
function afterWrite() {
  setSave('saved'); S.meta = `${words().toLocaleString()} words`; updateStatus();
  const doc = $('#doc'); let burst = false;
  doc.addEventListener('input', () => { setSave('saving'); S.meta = `${words().toLocaleString()} words`; updateStatus(); clearTimeout(saveTimer); saveTimer = setTimeout(() => { if (S.offline) { if (!burst) { S.waiting++; burst = true; renderStrip(); updateStatus(); } setSave('local'); } else { setSave('saved'); burst = false; } }, 700); });
  $('#main').onclick = (e) => {
    const c = e.target.closest('[data-cmd]'); if (c) { document.execCommand(c.dataset.cmd); doc.focus(); return; }
    const a = e.target.closest('[data-act]'); if (a) { if (a.dataset.act === 'link-entry') linkEntry(); else if (a.dataset.act === 'toast') toast({ title: a.dataset.title }); else if (a.dataset.act === 'chapter-menu') openMenu(a, [{ label: 'Chapters', heading: true }, ...DATA.outline.map((o, i) => ({ label: o, check: i === S.chapter, fn: () => { S.chapter = i; toast({ title: `Opened ${o}` }); } }))], { label: 'Chapters', align: 'left' }); return; }
    const ch = e.target.closest('[data-ch]'); if (ch) { e.preventDefault(); S.chapter = +ch.dataset.ch; $$('[data-ch]').forEach((x) => x.removeAttribute('aria-current')); ch.setAttribute('aria-current', 'true'); }
  };
}
function linkEntry() {
  const sel = getSelection(); const range = sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
  openPalette('Entries', 'link', (it) => { const doc = $('#doc'); doc.focus(); if (range) { sel.removeAllRanges(); sel.addRange(range); } document.execCommand('insertText', false, it.name); toast({ title: `Linked ${it.name}` }); });
}

/* ---------------------------------------------------------------- settings and forms (D21: a save bar for the irreversible) */
const FORM0 = () => ({ name: lib(), desc: 'Our weekly game and the notes we keep for it', r1: 'Organizer', r2: 'Author' });
function pSettings() {
  const f = S.form || (S.form = FORM0());
  const sel = (id, v) => `<span class="selectwrap"><select id="${id}" class="select" aria-label="Role">${['Owner', 'Organizer', 'Author', 'Player'].map((r) => `<option ${r === v ? 'selected' : ''}>${r}</option>`).join('')}</select>${ic('expand')}</span>`;
  return `<div class="page form page-enter"><h1 class="t-title page-title">Library settings</h1><p class="page-sub">${esc(lib())} · 3 people · You are the Owner</p>
  <section class="form-sec"><div><h2 class="t-heading">General</h2><p class="muted" style="margin-top:4px">The name and description people see.</p></div><div class="fields"><div><label class="label" for="f-name">Library name</label><input id="f-name" class="input" type="text" value="${esc(f.name)}"></div><div><label class="label" for="f-desc">Description</label><input id="f-desc" class="input" type="text" value="${esc(f.desc)}"><div class="help" id="f-help">Everyone in the library can read this.</div></div></div></section>
  <section class="form-sec"><div><h2 class="t-heading">People</h2><p class="muted" style="margin-top:4px">Who can do what in this library.</p></div><div style="max-width:520px"><div class="person"><span><b>Dana Okafor</b> <span class="t-meta">You</span></span><span class="muted">Owner</span></div><div class="person"><b>Mara Quill</b>${sel('f-r1', f.r1)}</div><div class="person"><b>Tobias Reyes</b>${sel('f-r2', f.r2)}</div><div style="margin-top:var(--s-3)"><button type="button" class="btn" data-act="invite">${ic('add')}Invite someone</button></div></div></section>
  <section class="form-sec"><div><h2 class="t-heading">Delete this library</h2><p class="muted" style="margin-top:4px">This removes its notes for everyone. It cannot be undone.</p></div><div><button type="button" class="btn btn--danger" data-act="delete-lib">Delete ${esc(lib())}…</button></div></section></div>`;
}
function dirtyCount() { const f = S.form, z = FORM0(); return ['name', 'desc', 'r1', 'r2'].filter((k) => f[k] !== z[k]).length; }
function renderSaveBar() {
  const n = dirtyCount(); const b = $('#savebar');
  if (n && b.dataset.n !== String(n)) { b.dataset.n = String(n); b.innerHTML = `<div><div class="savebar-in" role="region" aria-label="Unsaved changes"><span style="display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-ui)"><span style="color:var(--warning);display:inline-flex">${ic('pending')}</span>${n} ${n === 1 ? 'change' : 'changes'} not saved</span><span class="grow"></span><button type="button" class="btn" data-act="discard">Discard</button><button type="button" class="btn btn--primary" data-act="save">Save changes</button></div></div>`; } if (!n) delete b.dataset.n;
  b.toggleAttribute('data-open', n > 0);
}
function afterSettings() {
  S.form = S.form || FORM0();
  const read = () => { S.form = { name: $('#f-name').value, desc: $('#f-desc').value, r1: $('#f-r1').value, r2: $('#f-r2').value }; renderSaveBar(); const h = $('#f-help'); if (h) h.textContent = S.form.desc !== FORM0().desc ? 'Changed. Not saved yet.' : 'Everyone in the library can read this.'; };
  $('#main').oninput = read; $('#main').onchange = read;
  S.meta = '3 people'; updateStatus();
  $('#main').onclick = (e) => {
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'invite') toast({ title: 'Invite links are made in Account', text: 'A link is shown once, with Copy.' });
    else if (a.dataset.act === 'delete-lib') openDeleteLibrary();
  };
  $('#savebar').onclick = (e) => {
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'discard') { S.form = FORM0(); go('settings'); toast({ title: 'Changes discarded' }); }
    else if (a.dataset.act === 'save') { DATA.libraries[S.lib] = S.form.name || lib(); const keep = { ...S.form }; toast({ title: S.offline ? 'Saved on this device' : 'Saved', text: S.offline ? 'It is sent when you are back online.' : undefined }); if (S.offline) { S.waiting++; renderStrip(); } FORMSAVED = keep; S.form = FORM0(); S.form = { ...keep, name: DATA.libraries[S.lib] }; renderSaveBar(); renderHeader(); }
  };
  renderSaveBar();
}
let FORMSAVED = null;
function openDeleteLibrary() {
  const name = lib();
  openDialog({ title: `Delete ${esc(name)}?`, label: 'alertdialog', body: `<p class="muted t-body" style="margin-bottom:var(--s-2h)">This removes the library for everyone in it. It cannot be undone.</p><ul style="margin:0 0 var(--s-3);padding:0;list-style:none;border:1px solid var(--border-subtle);border-radius:var(--r-card)"><li style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-subtle)"><span>People who lose access</span><span class="num">6</span></li><li style="display:flex;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--border-subtle)"><span>Entries</span><span class="num">214</span></li><li style="display:flex;justify-content:space-between;padding:8px 12px"><span>Notes</span><span class="num">41</span></li></ul><label class="label" for="dl-n">Type <b style="color:var(--text-primary)">${esc(name)}</b> to confirm</label><input id="dl-n" class="input" type="text" data-autofocus autocomplete="off"><div class="help" id="dl-h">Type the full name to continue.</div>`,
    actions: [{ label: 'Cancel' }, { label: 'Delete library', kind: 'danger', disabled: true, fn: () => { toast({ title: 'Nothing was deleted', text: 'The prototype never deletes anything.' }); } }],
    init: (d) => { const b = $('[data-a="1"]', d), i = $('#dl-n', d); i.addEventListener('input', () => { const ok = i.value.trim() === name; setDisabled(b, !ok); $('#dl-h', d).textContent = ok ? 'This cannot be undone.' : 'Type the full name to continue.'; }); } });
}

/* ---------------------------------------------------------------- map: a full-width workspace (D21) */
function pMap() {
  const pl = DATA.places; const cur = pl.find((p) => p.id === S.place);
  return `<div class="map-wrap page-enter"><aside class="map-side" aria-label="Places"><div class="t-micro" style="margin-bottom:8px">Places on this map</div>${pl.map((p) => `<a href="#/map" data-place="${p.id}" ${p.id === S.place ? 'aria-current="true"' : ''}>${ic('location')}${esc(p.name)}</a>`).join('')}</aside><div class="map-canvas" role="application" aria-label="Map of the outer ring"><svg viewBox="0 0 720 440" preserveAspectRatio="xMidYMid meet" role="group" aria-label="Places"><g class="g" id="mg" style="transform:scale(${S.zoom})"><path d="M140 320 L380 210 L590 350" fill="none" stroke="var(--text-secondary)" stroke-width="2"></path><path d="M380 210 L500 130" fill="none" stroke="var(--text-secondary)" stroke-width="2" stroke-dasharray="6 5"></path>${pl.map((p) => `<g class="pin" tabindex="0" role="button" aria-label="${esc(p.name)}" data-place="${p.id}"><circle cx="${p.x}" cy="${p.y}" r="${p.id === S.place ? 10 : 7}" fill="${p.id === S.place ? 'var(--text-primary)' : 'var(--surface-canvas)'}" stroke="var(--text-primary)" stroke-width="2"></circle><text x="${p.x + 14}" y="${p.y + 4}" font-size="13" fill="var(--text-primary)" font-weight="${p.id === S.place ? 600 : 400}" font-family="Geist, sans-serif">${esc(p.name)}</text></g>`).join('')}</g></svg><div class="tools"><button type="button" aria-label="Zoom in" data-zoom="1.25">${ic('zoom-in')}</button><button type="button" aria-label="Zoom out" data-zoom="0.8">${ic('zoom-out')}</button><button type="button" aria-label="Fit" data-zoom="0">${ic('zoom-fit')}</button></div><div class="legend">Solid line: a direct connection · dashed: derived</div></div><div class="map-peek" id="peek"><div style="font-weight:600">${esc(cur.name)}</div><div class="t-meta">4 places · tap a place on the map</div></div></div>`;
}
function afterMap() {
  const sel = (id) => { S.place = id; go('map', true); };
  S.meta = `Zoom ${Math.round(S.zoom * 100)}%`; updateStatus();
  $('#main').onclick = (e) => {
    const z = e.target.closest('[data-zoom]'); if (z) { S.zoom = z.dataset.zoom === '0' ? 1 : Math.max(0.5, Math.min(2.5, S.zoom * +z.dataset.zoom)); $('#mg').style.transform = `scale(${S.zoom})`; S.meta = `Zoom ${Math.round(S.zoom * 100)}%`; updateStatus(); return; }
    const p = e.target.closest('[data-place]'); if (p) { e.preventDefault(); sel(p.dataset.place); }
  };
  $('#main').onkeydown = (e) => { const p = e.target.closest('.pin'); if (p && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); sel(p.dataset.place); } };
}

/* ---------------------------------------------------------------- first run (D27) */
function pFirstRun() {
  return `<div class="firstrun page-enter">${slot('first-run-welcome', 'Lorenzo, Warm Smile, an open atlas', 'parallax')}<div><h1 class="t-display" style="padding-bottom:.1em"><span class="typewriter" style="--typewriter-chars:18;--typewriter-width:100%">Welcome to Lorenzo</span></h1><p class="lead">Lorenzo keeps track of the worlds your games and stories happen in: where things are, who knows what, and the notes that belong to each. How would you like to start?</p>
  <div class="doors stagger"><section class="card" aria-labelledby="d1"><h2 id="d1" class="t-heading" style="margin-bottom:6px">I run a game</h2><p class="muted" style="margin-bottom:var(--s-3)">Set up a library for your group, a campaign and a link for your players. One short form.</p><button type="button" class="btn btn--primary" data-act="setup">Set up a library</button></section>
  <section class="card" aria-labelledby="d2"><h2 id="d2" class="t-heading" style="margin-bottom:6px">I’m joining a game</h2><p class="muted" style="margin-bottom:var(--s-2h)">Someone sent you an invite link. Open it, or paste it here.</p><div style="display:flex;gap:8px"><label class="visually-hidden" for="fr-l">Invite link</label><input id="fr-l" class="input" type="text" placeholder="Paste the invite link"><button type="button" class="btn" data-act="join">Join</button></div></section></div>
  ${S.publicRepos ? '<p class="muted" style="margin-top:var(--s-3)">Just looking around? <a href="#/states">Browse public repositories</a></p>' : ''}</div></div>`;
}
function afterFirstRun() { $('#main').onclick = (e) => { const a = e.target.closest('[data-act]'); if (!a) return; if (a.dataset.act === 'setup') openSetup(); else if (a.dataset.act === 'join') go('join'); }; $('#main').onkeydown = (e) => { if (e.key === 'Enter' && e.target.id === 'fr-l') go('join'); }; }
function openSetup() {
  openDialog({ title: 'Set up a library', body: `<div style="display:flex;flex-direction:column;gap:var(--s-3)"><div><label class="label" for="su-l">Library name</label><input id="su-l" class="input" type="text" value="Thursday table" data-autofocus><div class="help">A library holds a group’s campaigns, characters and notes.</div></div><div><label class="label" for="su-c">Campaign name</label><input id="su-c" class="input" type="text" value="The harbour job"></div><div><label class="label" for="su-s">Game system</label><input id="su-s" class="input" type="text" value="Any system, or none"></div><div><span class="label">Who runs the campaign</span><div class="seg" role="radiogroup" aria-label="Who runs the campaign"><button type="button" role="radio" aria-checked="true">I do</button><button type="button" role="radio" aria-checked="false">Someone I can find</button><button type="button" role="radio" aria-checked="false">A link</button></div></div></div>`,
    actions: [{ label: 'Cancel' }, { label: 'Set up', kind: 'primary', close: false, fn: (d) => { runSetup(d, $('#su-l', d).value || 'Thursday table'); return false; } }] });
}
function runSetup(d, name) {
  /* the rare branded wait (identity 11.2, 17.9): the spark, with steps and a progress bar */
  const steps = ['Creating the library', 'Adding the campaign', 'Making your player link'];
  d.innerHTML = `<div class="sheet-grip"></div><h2 id="dlg-t">Setting up ${esc(name)}</h2><div style="display:flex;flex-direction:column;align-items:center;gap:var(--s-3);padding:var(--s-3) 0"><span class="spark-loader" style="color:var(--canonical);width:40px;height:40px">${MARK('')}</span><div class="progress-bar" style="width:100%" role="progressbar" aria-label="Setting up"><span id="su-bar" style="width:0%"></span></div><ol id="su-steps" style="margin:0;padding:0;list-style:none;width:100%">${steps.map((s, i) => `<li data-s="${i}" style="display:flex;gap:8px;align-items:center;min-height:28px;color:var(--text-tertiary)">${ic('pending')}${s}</li>`).join('')}</ol></div>`;
  let i = 0;
  const next = () => { if (i > 0) { const li = $(`[data-s="${i - 1}"]`, d); li.style.color = 'var(--text-primary)'; li.firstElementChild.outerHTML = ic('select-item'); } $('#su-bar', d).style.width = (i / steps.length * 100) + '%'; if (i === steps.length) { setTimeout(() => finishSetup(d, name), 350); return; } const li = $(`[data-s="${i}"]`, d); li.style.color = 'var(--text-primary)'; i++; setTimeout(next, 800); };
  next();
}
function finishSetup(d, name) {
  d.innerHTML = `<div class="sheet-grip"></div><h2 id="dlg-t">Your library is ready</h2><p class="muted" style="margin-bottom:var(--s-3)">${esc(name)} has a campaign and you are its GM. Send this link to your players. It is shown once.</p><div style="display:flex;gap:8px"><input class="input" type="text" readonly value="https://lorenzo.example/join/#k7Qm-example-token" aria-label="Player link"><button type="button" class="btn" id="su-copy">${ic('copy')}Copy</button></div><div class="actions"><button type="button" class="btn btn--primary" id="su-open" data-autofocus>Open ${esc(name)}</button></div>`;
  $('#su-copy', d).onclick = () => toast({ title: 'Link copied' });
  $('#su-open', d).onclick = () => { closeOv(); DATA.libraries[S.lib] = name; S.form = null; go('home'); };
  $('#su-open', d).focus();
}

/* ---------------------------------------------------------------- joining with an invite link (ADR 0171, D27) */
function pJoin(dead) {
  const done = S.join === 'done', inn = S.join === 'preview-in';
  if (dead) return `<div class="join page-enter">${slot('no-access', 'Catileo at a closed door', '')}<h1 class="t-sub">This link doesn’t work any more.</h1><p class="muted">Ask whoever sent it for a new one.</p><a class="btn" href="#/home">Go to Home</a></div>`;
  if (done) return `<div class="join page-enter"><span class="badge">TT</span><h1 class="t-title">You’re in.</h1><p class="muted">Thursday table lists you as a player.</p><a class="btn btn--primary" href="#/beings">See your characters</a><p class="t-meta">Already a player here? It says so instead, and nothing changes.</p></div>`;
  return `<div class="join page-enter"><span class="badge">TT</span><p class="t-meta">${inn ? 'Signed in as Dana Okafor' : 'You are invited to join'}</p><h1 class="t-title">${inn ? 'Join Thursday table?' : 'Thursday table'}</h1><p class="muted">${inn ? 'You will be a player. You will see what is shared with players.' : 'as a player'}</p><button type="button" class="btn btn--primary" data-act="join-step" style="margin-top:var(--s-2h)">${inn ? 'Join' : 'Log in to join'}</button>${inn ? '' : '<p class="t-meta">No account yet? You can create one when you log in.</p>'}<p class="t-meta"><a href="#/join/dead">Try a link that doesn’t work</a></p></div>`;
}
function afterJoin() { $('#main').onclick = (e) => { const a = e.target.closest('[data-act="join-step"]'); if (!a) return; S.join = S.join === 'preview-out' ? 'preview-in' : 'done'; go('join', true); }; }

/* ---------------------------------------------------------------- the states gallery (D24) */
function pStates() {
  const cell = (label, where, inner) => `<div><div class="state-label t-micro"><span>${label}</span><span>${where}</span></div>${inner}</div>`;
  const sc = (icon, title, text, acts, extra = '') => `<div class="state-cell">${icon ? ic(icon) : ''}<div class="t-sub">${title}</div><div class="muted" style="max-width:300px">${text}</div>${extra}<div class="acts">${acts}</div></div>`;
  const b = (l, a, k = '') => `<button type="button" class="btn ${k}" data-act="st" data-a="${a}">${l}</button>`;
  return `<div class="page page--wide page-enter"><h1 class="t-title page-title">States</h1><p class="page-sub" style="max-width:760px">Each state says what happened in plain words, what it means for the work, and offers one next step. These sit inside a region and leave the rest of the page working.</p><div class="states stagger">
  ${cell('Empty, first time', 'region', sc('kind-entity-dashed', 'No entries yet', 'Add a person, place, event, object, or whatever else exists here.', b('New entry', 'new', 'btn--primary')))}
  ${cell('Empty, after a search', 'region', sc('search', 'No entries match', 'Try a different word, or clear the filters.', b('Clear filters', 'toast')))}
  ${cell('Loading, slow', 'region', `<div class="state-cell" role="status" aria-label="Loading entries"><div style="width:100%;display:flex;flex-direction:column;gap:14px"><div class="skel" style="width:70%"></div><div class="skel" style="width:90%"></div><div class="skel" style="width:55%"></div><div class="skel" style="width:80%"></div><div class="muted" style="margin-top:8px">Still loading. This is taking longer than usual.</div></div></div>`)}
  ${cell('Error', 'region', sc('warning', 'Couldn’t load entries', 'The connection dropped before this finished. Nothing you wrote is lost.', b('Try again', 'toast', 'btn--primary'), '<div class="t-code t-meta">503 · request 4f2a91</div>'))}
  ${cell('Partly loaded', 'region', sc('warning', 'Some entries didn’t load', 'Showing 8. 2 could not be loaded.', b('Try again for the rest', 'toast', 'btn--primary')))}
  ${cell('Conflict', 'region', sc('conflict', 'This changed while you were editing', 'Mara Quill changed the description at 19:38. Your version and theirs both exist.', b('Review changes', 'review', 'btn--primary') + b('Keep mine', 'toast')))}
  ${cell('No access', 'page or region', `<div class="state-cell">${slot('no-access', 'Catileo at a closed door')}<div class="t-sub">This page isn’t available</div><div class="muted" style="max-width:300px">It may not exist, or you may not have access. Ask a GM or an Organizer of the library to share it with you.</div><div class="acts">${b('Go to Home', 'home')}</div></div>`)}
  ${cell('Offline, not on this device', 'page or region', sc('offline', 'Not on this device yet', 'Reconnect to open it. What you have already saved here is still available.', b('See what is saved here', 'toast')))}
  </div></div>`;
}
function afterStates() { $('#main').onclick = (e) => { const a = e.target.closest('[data-a]'); if (!a) return; const k = a.dataset.a; if (k === 'new') openNewEntry(); else if (k === 'home') go('home'); else if (k === 'review') openConflictReview(); else toast({ title: 'That is drawn here, not wired' }); }; }

/* ---------------------------------------------------------------- an app this prototype does not draw */
function pStub(appId) {
  const a = appOf(appId) || { name: 'This page', icon: 'info' };
  return `<div class="stub page-enter">${ic(a.icon, 'lg')}<h1 class="t-title">${esc(a.name)}</h1><p class="muted">This page is not drawn in the shell prototype. The shell around it is: open another app from the footer, from Home or from the palette.</p><div style="display:flex;gap:8px"><a class="btn btn--primary" href="#/home">Go to Home</a><button type="button" class="btn" data-act="palette">Find or go anywhere</button></div></div>`;
}

/* ---------------------------------------------------------------- account: profile, access tokens and connecting a device (PT1 to PT5).
   In the shell so that every app's account menu reaches them; the account hub uses the same pages. */
const SA_COLORS = [['Blue', 'var(--brand-archive-blue)'], ['Sky', 'var(--brand-astral-blue)'], ['Green', 'var(--utility-success)'], ['Burgundy', 'var(--brand-burgundy)'], ['Grey', 'var(--text-secondary)']];
const SA = {
  prof: { nick: 'dana', disp: 'Dana Okafor', pron: 'she/her', bio: 'I run the Thursday game and keep too many notes.', lang: 'English, Deutsch', color: 0, hex: '' },
  tokens: [{ id: 't1', name: 'Laptop command line', hint: 'x3Qf', made: 90, used: 0, ends: null }, { id: 't2', name: 'Phone', hint: 'k9Lm', made: 200, used: 21, ends: 4 }, { id: 't3', name: 'Build server script', hint: 'p7Zr', made: 300, used: 120, ends: null }, { id: 't4', name: 'Old laptop', hint: 'b2Vd', made: 270, used: null, ends: null }, { id: 't5', name: 'Conference demo', hint: 'q8Wn', made: 150, used: 60, ends: -21 }],
  cust: false, done: false
};
SA.last = { ...SA.prof };
const saAgo = (d) => (d === 0 ? 'today' : d < 7 ? `${d} ${d === 1 ? 'day' : 'days'} ago` : d < 60 ? `${Math.round(d / 7)} weeks ago` : `${Math.round(d / 30)} months ago`);
const saWho = (pub) => (pub ? `<span class="pt-who">${ic('eye')}Others see this</span>` : `<span class="pt-who">${ic('private')}Only you and admins see this</span>`);
const saColor = () => (SA.prof.hex ? SA.prof.hex : SA_COLORS[SA.prof.color][1]);
const saInit = (n) => n.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase() || '?';
const saField = (id, key, label, pub, help, tag) => `<div class="pt-f"><div class="pt-fh"><label class="label" for="${id}">${label}</label>${saWho(pub)}</div>${tag === 'textarea' ? `<textarea id="${id}" class="input" rows="3" style="padding:8px 12px" data-pf="${key}">${esc(SA.prof[key])}</textarea>` : `<input id="${id}" class="input" data-pf="${key}" value="${esc(SA.prof[key])}" ${help ? `aria-describedby="${id}-h"` : ''}>`}${help ? `<div class="help" id="${id}-h">${help}</div>` : ''}<span class="pt-sv" id="${id}-sv" role="status"></span></div>`;
const saPrev = () => `<div class="pt-prev" role="group" aria-label="How others see you"><div class="pt-pt">How others see you</div><div class="pt-row"><span class="pt-av" id="pv-av" style="--c:${saColor()}">${esc(saInit(SA.prof.disp))}</span><div><b id="pv-d">${esc(SA.prof.disp)}</b><div class="t-meta" id="pv-n">@${esc(SA.prof.nick)}</div></div><span class="pt-dot" id="pv-dot" style="background:${saColor()}" title="Your colour"></span></div><div class="pt-note">${ic('notifications')}<span><b id="pv-d2">${esc(SA.prof.disp)}</b> invited you to Thursday table</span></div><p class="t-meta" style="margin:0">Pronouns, bio and languages are not shown to others.</p></div>`;
function pSaProfile() {
  SA.done = false;
  return `<div class="page page--wide page-enter pt"><p class="sa-crumb">Account</p><h1 class="t-title page-title">Profile</h1><p class="page-sub">How you appear to other people. Each change is saved as you make it.</p><div class="pt-grid"><div class="pt-form">
  <section class="pt-sec"><h2 class="t-heading">Picture</h2>${saWho(true)}<div class="sa-row"><span class="sa-pic" aria-hidden="true">${esc(saInit(SA.prof.disp))}</span><button type="button" class="btn" data-sa="toast" data-title="A picture is chosen in a picker">Replace</button><button type="button" class="btn btn--quiet" data-sa="toast" data-title="Picture removed">Remove</button></div><p class="help" style="margin:0">Until you upload one, it is computed from your email.</p></section>
  <section class="pt-sec"><h2 class="t-heading">Names</h2>${saField('pf-n', 'nick', 'Nickname', true, 'Unique. Others find you by it.')}${saField('pf-d', 'disp', 'Display name', true, 'Shown in lists. Two people can share one.')}${saField('pf-p', 'pron', 'Pronouns', false, '')}</section>
  <section class="pt-sec"><h2 class="t-heading">About you</h2>${saField('pf-b', 'bio', 'Bio', false, '', 'textarea')}${saField('pf-l', 'lang', 'Languages', false, '')}
  <div class="pt-f"><div class="pt-fh"><span class="label" id="clb">Your colour</span>${saWho(true)}</div><div class="sa-row" role="group" aria-labelledby="clb">${SA_COLORS.map(([n, c], i) => `<button type="button" class="sa-swatch" aria-pressed="${!SA.cust && SA.prof.color === i}" data-sa="swatch" data-i="${i}"><i style="background:${c}"></i>${n}</button>`).join('')}<button type="button" class="sa-swatch" aria-pressed="${SA.cust}" data-sa="custom">${ic('appearance')}Custom…</button></div>${SA.cust ? `<div class="pt-cust"><label class="label" for="hex">Colour, as #RRGGBB</label><div class="sa-row"><input id="hex" class="input" style="width:9rem;font-family:var(--font-mono)" data-pf="hex" value="${esc(SA.prof.hex || '#3D7EA6')}" aria-describedby="hex-ok"><span class="pt-sw" id="hex-sw" style="background:${esc(SA.prof.hex || '#3D7EA6')}"></span></div><p class="pt-ok" id="hex-ok" role="status"></p></div>` : ''}<div class="help">It marks you next to your name. Your name is what identifies you.</div></div></section>
  <section class="pt-sec"><h2 class="t-heading">Delete my account</h2><p class="muted" style="margin:0">This removes your profile and what you own. It does not delete your login. It needs you signed in here, never a token.</p><div><button type="button" class="btn btn--danger" data-sa="delete-acct">Delete my account…</button></div></section>
  </div><aside class="pt-side" aria-label="Preview">${saPrev()}</aside></div></div>`;
}
/* a colour is checked against the light and the dark surface (WCAG 1.4.11: 3 to 1) */
function saLum(hex) { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4))); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }
function saCheck(hex) {
  if (!/^#[0-9A-Fa-f]{6}$/.test(hex)) return { ok: false, text: 'A colour is # and six letters or digits, such as #3D7EA6.' };
  const cs = getComputedStyle(document.documentElement); const paper = (cs.getPropertyValue('--brand-paper') || '#faf9f6').trim(); const ink = (cs.getPropertyValue('--brand-ink') || '#0b1220').trim();
  const L = saLum(hex); const r = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); const light = r(L, saLum(/^#[0-9a-f]{6}$/i.test(paper) ? paper : '#faf9f6')), dark = r(L, saLum(/^#[0-9a-f]{6}$/i.test(ink) ? ink : '#0b1220'));
  if (light >= 3 && dark >= 3) return { ok: true, text: 'Readable on a light surface and on a dark one.' };
  return { ok: false, text: light < 3 && dark < 3 ? 'Too faint on both light and dark surfaces. Choose a colour that is neither very light nor very dark.' : light < 3 ? 'Too faint on a light surface. Choose a deeper colour.' : 'Too faint on a dark surface. Choose a lighter colour.' };
}
/* ---- access tokens (PT4) */
function saTokState(t) {
  const note = []; let state, icon = 'select-item', cls = 'ok';
  if (t.ends !== null && t.ends < 0) { state = t.used === null ? 'Never used' : `Last used ${saAgo(t.used)}`; note.push(`Expired ${saAgo(-t.ends)}`); icon = 'warning'; cls = 'expired'; }
  else if (t.used === null) { state = 'Never used'; note.push(`Made ${saAgo(t.made)}`); icon = 'kind-clock-unknown'; cls = 'never'; }
  else if (t.used >= 90) { state = `Not used for ${t.used} days`; note.push('It still works. Revoke it if you no longer need it.'); icon = 'kind-clock-unknown'; cls = 'stale'; }
  else { state = `Last used ${saAgo(t.used)}`; }
  if (t.ends !== null && t.ends >= 0 && t.ends <= 14) { note.push(`Expires in ${t.ends} ${t.ends === 1 ? 'day' : 'days'}`); if (cls === 'ok') { icon = 'kind-clock'; cls = 'soon'; } }
  return { state, note: note.join('. '), icon, cls };
}
function pSaTokens() {
  SA.done = false;
  const rows = SA.tokens.map((t) => { const s = saTokState(t); return `<li class="pt-tk ${s.cls}"><div class="pt-tn"><b>${esc(t.name)}</b><span class="t-meta">Ends in <code>${esc(t.hint)}</code></span></div><div class="pt-tu"><span class="pt-state">${ic(s.icon)}${esc(s.state)}</span>${s.note ? `<span class="t-meta">${esc(s.note)}</span>` : ''}</div><button type="button" class="btn btn--quiet" data-sa="revoke" data-id="${t.id}" aria-label="Revoke ${esc(t.name)}">Revoke…</button></li>`; }).join('') || '<li class="pt-tk"><span class="muted">No access tokens. A device asks for one when you connect it.</span></li>';
  return `<div class="page page-enter pt pt-narrow"><p class="sa-crumb">Account</p><h1 class="t-title page-title">Access tokens</h1><p class="page-sub">Programs that act as you: the command line, a script, a bot.</p><div class="callout" role="note">${ic('info')}<span class="tx"><b>A token is a whole key.</b> It can do what you can, except manage tokens or delete your account. You see here when it was last used, and you can revoke it at any time.</span></div>
  <section class="pt-sec"><h2 class="t-heading">Your tokens <span class="t-meta">${SA.tokens.length} of 50</span></h2><ul class="pt-tks" aria-label="Your tokens">${rows}</ul></section>
  <section class="pt-sec"><h2 class="t-heading">Connect a device</h2><p class="muted" style="margin:0">Run the login on the device. It shows a code. Type it here, or open the link it prints.</p><div class="sa-row"><label class="visually-hidden" for="dv-c">Code from the device</label><input id="dv-c" class="input" style="width:200px;font-family:var(--font-mono)" placeholder="ABCD-EFGH" maxlength="9" autocomplete="off"><button type="button" class="btn" data-sa="find">Check the code</button></div><div id="dv-err" class="soerr" role="alert"></div></section></div>`;
}
/* ---- connect a device (PT5): the page the command line's link opens */
const SA_CODE = /^[A-Za-z]{4}-?[A-Za-z]{4}$/;
const saNorm = (v) => { const s = v.replace('-', '').toUpperCase(); return s.slice(0, 4) + '-' + s.slice(4); };
function pSaDevice() {
  const code = S.route.split('/')[1] || ''; const out = S.route.split('/')[2] === 'signin'; let body;
  const typeBox = (err) => `<div class="card pt-card"><p class="muted" style="margin:0">Type the code the device shows.</p><div class="sa-row"><label class="visually-hidden" for="dv-c">Code from the device</label><input id="dv-c" class="input" style="width:200px;font-family:var(--font-mono)" placeholder="ABCD-EFGH" maxlength="9" autocomplete="off" value="${esc(err ? code : '')}" ${err ? 'aria-invalid="true" aria-describedby="dv-err"' : ''}><button type="button" class="btn btn--primary" data-sa="continue">Continue</button></div><div id="dv-err" class="soerr" role="alert">${err ? 'That code is not valid or has ended. Codes last ten minutes. Start again on the device.' : ''}</div></div>`;
  if (SA.done) body = `<div class="card pt-card">${slot('device-connected', 'Catileo, curled up on a laptop')}<p><b>Connected.</b></p><p class="muted" style="margin:0">The device finishes by itself in a few seconds. Its token is shown to the device only. You can see and revoke it in Access tokens.</p><a class="btn" href="#/tokens" data-sa="seen">Go to Access tokens</a></div>`;
  else if (!code) body = typeBox(false);
  else if (!SA_CODE.test(code)) body = typeBox(true);
  else if (out) body = `<div class="card pt-card"><p><b>Sign in to approve this device.</b></p><p class="muted" style="margin:0">You will come back to this page with the code kept: <code>${esc(saNorm(code))}</code>.</p><div><button type="button" class="btn btn--primary" data-sa="signin">Sign in</button></div></div>`;
  else body = `<div class="card pt-card"><div class="sa-row">${ic('device', 'lg')}<div><b>lorenzo CLI on Dana’s laptop</b><div class="t-meta">is asking to act as you · code <code>${esc(saNorm(code))}</code> · it ends in 8 minutes</div></div></div><div class="callout callout--warn" role="note">${ic('warning')}<span class="tx"><b>Only approve a code you started yourself</b> on that device, just now. Someone else may have sent you this link.</span></div><div><label class="label" for="dv-n">Name for this token</label><input id="dv-n" class="input" value="lorenzo CLI on Dana’s laptop" aria-describedby="dv-nh"><div class="help" id="dv-nh">Up to 80 characters.</div><div id="dv-nerr" class="soerr" role="alert"></div></div><div><span class="label" id="dv-el">It stops working</span><div class="seg" role="radiogroup" aria-labelledby="dv-el" id="dv-e">${['Never', 'In 30 days', 'In 90 days', 'In a year'].map((t, i) => `<button type="button" role="radio" aria-checked="${i === 0}" data-v="${t}">${t}</button>`).join('')}</div></div><p class="t-meta" style="margin:0">It can do what you can, except manage tokens or delete your account. You can revoke it at any time from Access tokens.</p><div class="sa-row"><button type="button" class="btn btn--primary" data-sa="approve">Connect</button><button type="button" class="btn" data-sa="deny">Deny</button></div></div>`;
  return `<div class="page page-enter pt pt-narrow"><p class="sa-crumb">Account</p><h1 class="t-title page-title">Connect a device</h1>${body}</div>`;
}
function saLive() {
  const P = SA.prof; const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
  set('#pv-d', P.disp); set('#pv-d2', P.disp); set('#pv-n', '@' + P.nick); set('#pv-av', saInit(P.disp)); const av = $('#pv-av'); if (av) av.style.setProperty('--c', saColor()); const dot = $('#pv-dot'); if (dot) dot.style.background = saColor();
}
function afterSa() {
  const m = $('#main'); $('#savebar').toggleAttribute('data-open', false);
  const hex = $('#hex'); if (hex) { const c = saCheck(hex.value); $('#hex-ok').innerHTML = `${ic(c.ok ? 'select-item' : 'warning')}${esc(c.text)}`; }
  m.oninput = (e) => { const t = e.target; if (!t.dataset.pf) return; const k = t.dataset.pf; if (k === 'hex') { const v = t.value.trim(); const c = saCheck(v); $('#hex-ok').innerHTML = `${ic(c.ok ? 'select-item' : 'warning')}${esc(c.text)}`; if (/^#[0-9A-Fa-f]{6}$/.test(v)) { $('#hex-sw').style.background = v; SA.prof.hex = v; saLive(); } return; } SA.prof[k] = t.value; saLive(); };
  m.onchange = (e) => {
    const t = e.target; if (!t.dataset.pf) return; const k = t.dataset.pf; const sv = $(`#${t.id}-sv`); const prev = SA.prefs && SA.prefs[k] !== undefined ? SA.prefs[k] : null; const val = t.value.trim();
    const err = k === 'nick' ? (!/^[a-z0-9_.-]{2,30}$/i.test(val) ? 'A nickname is 2 to 30 letters, digits, dots, dashes or underscores.' : val.toLowerCase() === 'mara' ? 'Someone already has that nickname.' : null) : k === 'hex' ? (saCheck(val).ok ? null : saCheck(val).text) : null;
    if (err) { if (sv) { sv.textContent = err; sv.className = 'pt-sv soerr'; } else fieldErrSa(t, err); t.setAttribute('aria-invalid', 'true'); return; }
    t.removeAttribute('aria-invalid'); if (sv) { sv.className = 'pt-sv'; sv.textContent = 'Saved'; }
    const old = SA.last && SA.last[k] !== undefined ? SA.last[k] : null; SA.last = SA.last || {}; const before = SA.last[k]; SA.last[k] = val; SA.prof[k] = val; saLive();
    if (before !== undefined && before !== val) withUndo(`${k === 'nick' ? 'Nickname' : k === 'disp' ? 'Display name' : k === 'pron' ? 'Pronouns' : k === 'bio' ? 'Bio' : k === 'lang' ? 'Languages' : 'Colour'} changed`, () => { SA.last[k] = before; SA.prof[k] = before; t.value = before; if (sv) sv.textContent = 'Saved'; saLive(); });
    announce_sa(`${t.id === 'pf-n' ? 'Nickname' : 'Field'} saved`);
  };
  m.onclick = (e) => {
    const a = e.target.closest('[data-sa]'); if (!a) { const sg = e.target.closest('#dv-e button'); if (sg) $$('#dv-e button').forEach((x) => x.setAttribute('aria-checked', x === sg)); return; }
    const k = a.dataset.sa;
    if (k === 'toast') toast({ title: a.dataset.title });
    else if (k === 'swatch') { SA.cust = false; SA.prof.hex = ''; SA.prof.color = +a.dataset.i; render(true); }
    else if (k === 'custom') { SA.cust = !SA.cust; if (!SA.cust) SA.prof.hex = ''; render(true); }
    else if (k === 'delete-acct') { const name = DATA.user.email; openDialog({ title: 'Delete my account?', label: 'alertdialog', body: `<p class="muted t-body" style="margin-bottom:var(--s-2h)">This removes your profile and the libraries and repositories only you own. It cannot be undone. Your login is not deleted.</p><label class="label" for="cn-i">Type <b style="color:var(--text-primary)">${esc(name)}</b> to confirm</label><input id="cn-i" class="input" data-autofocus autocomplete="off"><div class="help" id="cn-h">Type the full name to continue.</div>`, actions: [{ label: 'Cancel' }, { label: 'Delete my account', kind: 'danger', disabled: true, fn: () => { toast({ title: 'Nothing was deleted', text: 'The prototype never deletes anything.' }); } }], init: (d) => { const b = $('[data-a="1"]', d), i = $('#cn-i', d); i.addEventListener('input', () => { const ok = i.value.trim() === name; setDisabled(b, !ok); $('#cn-h', d).textContent = ok ? 'This cannot be undone.' : 'Type the full name to continue.'; }); } }); }
    else if (k === 'revoke') { const t = SA.tokens.find((x) => x.id === a.dataset.id); openDialog({ title: `Revoke ${esc(t.name)}?`, label: 'alertdialog', body: `<p class="muted t-body" style="margin:0">The device stops working at once. It cannot be undone: connect it again to get a new token.${t.used === 0 ? ' It was used today.' : ''}</p>`, actions: [{ label: 'Cancel', auto: true }, { label: 'Revoke', kind: 'danger', fn: () => { SA.tokens = SA.tokens.filter((x) => x !== t); render(true); toast({ title: `${t.name} revoked`, text: 'It stopped working at once.' }); } }] }); }
    else if (k === 'find' || k === 'continue') { const v = $('#dv-c').value.trim(); if (!SA_CODE.test(v)) { $('#dv-err').textContent = 'That code is not valid or has ended. Codes last ten minutes. Start again on the device.'; $('#dv-c').setAttribute('aria-invalid', 'true'); return; } SA.done = false; location.hash = '#/device/' + saNorm(v); }
    else if (k === 'approve') { const name = $('#dv-n').value.trim(); if (!name) { $('#dv-nerr').textContent = 'A token needs a name.'; return; } if (name.length > 80) { $('#dv-nerr').textContent = `A name is at most 80 characters; this is ${name.length}.`; $('#dv-n').setAttribute('aria-invalid', 'true'); return; } const e2 = ($('#dv-e [aria-checked="true"]') || {}).dataset || {}; const ends = { Never: null, 'In 30 days': 30, 'In 90 days': 90, 'In a year': 365 }[e2.v || 'Never']; SA.tokens.unshift({ id: 't' + Date.now(), name, hint: 'n4Rw', made: 0, used: null, ends }); SA.done = true; render(true); announce_sa('Connected'); }
    else if (k === 'deny') { location.hash = '#/tokens'; toast({ title: 'Denied', text: 'The device was told no.' }); }
    else if (k === 'signin') { location.hash = '#/device/' + (S.route.split('/')[1] || ''); toast({ title: 'Signed in', text: 'You are back on the page with the code kept.' }); }
    else if (k === 'seen') { SA.done = false; }
  };
}
function fieldErrSa(input, msg) { let p = input.parentElement.querySelector('.soerr'); if (!p) { p = document.createElement('p'); p.className = 'soerr'; p.setAttribute('role', 'alert'); input.parentElement.appendChild(p); } p.textContent = msg; }
function announce_sa(t) { let l = $('#sa-live'); if (!l) { l = document.createElement('div'); l.id = 'sa-live'; l.className = 'visually-hidden'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = ''; setTimeout(() => { l.textContent = t; }, 30); }

/* Inventory: routes, actions, dialogs and the controls bar. */
function ivRefresh(keepFocus) {
  const m = $('#main'); const top = m.scrollTop; const f = document.activeElement; let sel = null, pos = null;
  if (keepFocus && f && m.contains(f)) { sel = f.id ? `#${f.id}` : f.dataset.iv ? `[data-iv="${f.dataset.iv}"]${f.dataset.v ? `[data-v="${CSS.escape(f.dataset.v)}"]` : ''}` : f.dataset.pick ? `[data-pick="${f.dataset.pick}"]` : null; if (f.selectionStart != null) pos = [f.selectionStart, f.selectionEnd]; }
  const r = cur(); S.meta = r.meta ? r.meta() : ''; m.innerHTML = r.render(); ivAfter(); m.scrollTop = top;
  if (sel) { const n = $(sel, m); if (n) { n.focus({ preventScroll: true }); if (pos && n.setSelectionRange) n.setSelectionRange(pos[0], pos[1]); } }
  updateStatus();
}
const ivSoon = (fn) => setTimeout(fn, 0);
function remember(b) { IV.board = b; IV.col = 'eq'; IV.sel = null; IV.q = ''; IV.picked = new Set(); IV.multi = false; ivStore.set('iv-board', b); }
function boardRoute() { if (!IV.board || !canOpen(IV.board)) { const last = ivStore.get('iv-board'); IV.board = last && BOARDS[last] && canOpen(last) ? last : MEP; } return ivBoardPage(); }
/* do a change, and offer Undo; a refusal is shown as it is given and nothing changes */
function ivAct(title, fn, text) {
  const before = snapI(); const err = fn();
  if (err) { restoreI(before); toast({ kind: 'error', title: 'That did not work', text: err, action: { label: 'Close', fn: () => {} } }); ivRefresh(true); return false; }
  ivRefresh(true); announce(title);
  withUndo(title, () => { restoreI(before); ivRefresh(); }, text); return true;
}
function pickCol(b, sel) { return BOARDS[b].cols.map((c) => `<label class="ivrd"><input type="radio" name="col" value="${c.id}" ${c.id === sel ? 'checked' : ''}> <span>${esc(c.n)}</span><span class="t-meta num">${sumw(ITEMS.filter((x) => x.at === b && x.col === c.id))}${c.cap != null ? ` of ${c.cap}` : ''} lb</span></label>`).join(''); }
function moveDialog(ids) {
  const L = ids.map(itemOf).filter(Boolean); if (!L.length) return; const b = L[0].at;
  openDialog({ title: L.length === 1 ? `Move ${esc(L[0].n)}` : `Move ${L.length} cards`, body: `<p class="muted" style="margin:0 0 var(--s-2h)">Moving keeps who owns it. A stack keeps its count and joins an identical one already there.</p><fieldset class="ivfs2"><legend class="sr-only">Move to</legend>${pickCol(b, L[0].col)}</fieldset>`,
    actions: [{ label: 'Cancel' }, { label: 'Move', kind: 'primary', fn: (d) => { const c = $('input[name=col]:checked', d).value; const name = BOARDS[b].cols.find((x) => x.id === c).n; ivSoon(() => ivAct(L.length === 1 ? `${L[0].n} moved to ${name}` : `${L.length} cards moved to ${name}`, () => { for (const i of L) { const e = moveTo(itemOf(i.id), b, c); if (e) return e; } return null; })); } }] });
}
function giveDialog(ids) {
  const L = ids.map(itemOf).filter(Boolean); if (!L.length) return; const one = L.length === 1 ? L[0] : null;
  const to = Object.keys(BOARDS).filter((b) => BOARDS[b].kind !== 'Nobody' && !L.every((i) => i.owner === b));
  openDialog({ title: one ? `Give ${esc(one.n)}` : `Give ${L.length} cards`, body: `<p class="muted" style="margin:0 0 var(--s-2h)">Giving changes who owns it. Moving does not.</p><label class="label" for="gv-to">Give to</label><select id="gv-to" class="select">${to.map((b) => `<option value="${b}">${esc(BOARDS[b].n)}</option>`).join('')}</select>${one && one.q > 1 ? `<label class="label" for="gv-n" style="margin-top:var(--s-3)">How many (of ${one.q})</label><input id="gv-n" class="input" inputmode="numeric" value="${one.q}">` : ''}<label class="ivrd" style="margin-top:var(--s-3)"><input type="checkbox" id="gv-h"> <span>Hand it over: take it out of its container and into their hands too</span></label><p class="t-meta">Otherwise it stays where it is, and is theirs now.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Give', kind: 'primary', fn: (d) => { const r = $('#gv-to', d).value; const h = $('#gv-h', d).checked; const k = one && one.q > 1 ? parseInt($('#gv-n', d).value, 10) : null; if (k !== null && (!(k >= 1) || k > one.q)) { toast({ kind: 'error', title: 'That is not a number we can give', text: `Choose between 1 and ${one.q}.` }); return false; } ivSoon(() => ivAct(one ? `${one.n} given to ${BOARDS[r].n}` : `${L.length} cards given to ${BOARDS[r].n}`, () => { L.forEach((x) => giveTo(itemOf(x.id), r, h, one && k ? k : itemOf(x.id).q)); return null; })); } }] });
}
function addDialog() {
  const b = IV.board; const off = !isGM() && !IV.self; const list = CAT.filter((c) => isGM() || c.public);
  openDialog({ title: 'Add an item', body: `${off ? `<p class="ivnotice">${ic('info')} Your GM has turned this off for you. Ask them to add it.</p>` : ''}<fieldset class="ivfs2"><legend class="label">Where does it come from</legend><label class="ivrd"><input type="radio" name="src" value="list" checked> From the list</label><label class="ivrd"><input type="radio" name="src" value="own"> Not in the list</label></fieldset><div id="ad-list"><label class="label" for="ad-c">Item</label><select id="ad-c" class="select">${list.map((c) => `<option value="${c.id}">${esc(c.n)}</option>`).join('')}</select><label class="label" for="ad-n" style="margin-top:var(--s-3)">A name of your own, if you like</label><input id="ad-n" class="input" autocomplete="off"></div><div id="ad-own" hidden><label class="label" for="ow-n">Name</label><input id="ow-n" class="input" autocomplete="off"><label class="label" for="ow-d" style="margin-top:var(--s-3)">Description</label><textarea id="ow-d" class="input" style="min-height:4rem"></textarea><div class="row2" style="margin-top:var(--s-3)"><div><label class="label" for="ow-w">Weight, lb</label><input id="ow-w" class="input" inputmode="decimal" value="0"></div><div><label class="label" for="ow-v">Value</label><input id="ow-v" class="input" inputmode="decimal" value="0"></div></div><p class="t-meta">It is added as unsorted, with your description kept as a note, until your GM matches it to a catalog item.</p></div>`,
    actions: [{ label: 'Cancel' }, { label: 'Add to Not carried', kind: 'primary', disabled: off, fn: (d) => { const own = $('input[name=src]:checked', d).value === 'own'; if (own) { const n = $('#ow-n', d).value.trim(); if (!n) { toast({ kind: 'error', title: 'It needs a name' }); return false; } const w = parseFloat($('#ow-w', d).value) || 0; const desc = $('#ow-d', d).value.trim(); ivSoon(() => ivAct(`${n} added to Not carried`, () => { ITEMS.push({ id: uid(), n, cat: null, unsorted: true, uname: n, q: 1, w, owner: b, at: b, col: 'nc', notes: desc ? [{ who: `${BOARDS[b].n.split(' ')[0]} only`, t: desc }] : [] }); return null; }, 'Unsorted until your GM matches it')); } else { const c = catOf($('#ad-c', d).value); const n = $('#ad-n', d).value.trim() || c.n; ivSoon(() => ivAct(`${n} added to Not carried`, () => { ITEMS.push({ id: uid(), n, cat: c.id, q: 1, w: c.w, owner: b, at: b, col: 'nc', notes: [] }); return null; })); } } }],
    init: (d) => { const bt = $('[data-a="1"]', d); if (off) setDisabled(bt, true); $$('input[name=src]', d).forEach((r) => r.addEventListener('change', () => { const o = $('input[name=src]:checked', d).value === 'own'; $('#ad-list', d).hidden = o; $('#ad-own', d).hidden = !o; })); } });
}
function makeDialog(pre) {
  openDialog({ title: 'Make from catalog', body: `<label class="label" for="mk-c">Item</label><select id="mk-c" class="select">${CAT.map((c) => `<option value="${c.id}" ${c.id === pre ? 'selected' : ''}>${esc(c.n)}</option>`).join('')}</select><label class="label" for="mk-o" style="margin-top:var(--s-3)">Owner</label><select id="mk-o" class="select">${Object.keys(BOARDS).map((b) => `<option value="${b}" ${b === (BOARDS[IV.board] ? IV.board : 'unowned') ? 'selected' : ''}>${esc(BOARDS[b].n)}</option>`).join('')}</select><label class="label" for="mk-s" style="margin-top:var(--s-3)">Link name <span class="t-meta">optional</span></label><input id="mk-s" class="input" autocomplete="off">`,
    actions: [{ label: 'Cancel' }, { label: 'Make it', kind: 'primary', fn: (d) => { const c = catOf($('#mk-c', d).value); const o = $('#mk-o', d).value; ivSoon(() => ivAct(`${c.n} made for ${BOARDS[o].n}`, () => { ITEMS.push({ id: uid(), n: c.n, cat: c.id, q: 1, w: c.w, owner: o, at: o, col: 'nc', notes: [] }); return null; }, 'In Not carried')); } }] });
}
function noteDialog(i) {
  openDialog({ title: `Add a note to ${esc(i.n)}`, body: `<label class="label" for="nt">The note</label><textarea id="nt" class="input" style="min-height:5rem"></textarea><label class="ivrd"><input type="checkbox" id="nt-e"> <span>Everyone can read this</span></label><p class="t-meta">Otherwise only ${esc(ownerN(i.owner))} and the campaign’s GMs can.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Add the note', kind: 'primary', fn: (d) => { const t = $('#nt', d).value.trim(); if (!t) { toast({ kind: 'error', title: 'A note needs some words' }); return false; } const all = $('#nt-e', d).checked; ivSoon(() => ivAct('Note added', () => { itemOf(i.id).notes.push({ who: all ? 'Everyone' : `${ownerN(i.owner).split(' ')[0]} only`, t }); return null; })); } }], init: (d) => $('#nt', d).focus() });
}
function splitDialog(i) { openDialog({ title: `Split ${esc(i.n)}`, body: `<label class="label" for="sp">How many go into the new stack (of ${i.q})</label><input id="sp" class="input" inputmode="numeric" value="1">`, actions: [{ label: 'Cancel' }, { label: 'Split', kind: 'primary', fn: (d) => { const k = parseInt($('#sp', d).value, 10); const e = (k >= 1 && k < i.q) ? null : `Choose a number between 1 and ${i.q - 1}.`; if (e) { toast({ kind: 'error', title: 'That did not work', text: e }); return false; } ivSoon(() => ivAct(`${i.n} split ${i.q - k} and ${k}`, () => splitStack(itemOf(i.id), k))); } }], init: (d) => $('#sp', d).select() }); }
function downDialog(i) {
  if (i.q > 1 && i.cat && i.col !== 'nc') return openDialog({ title: `Set down ${esc(i.n)}?`, label: 'alertdialog', body: `<p class="muted" style="margin:0">This stack of ${i.q} becomes ${i.q} separate items in Not carried.</p>`, actions: [{ label: 'Cancel' }, { label: 'Set down', kind: 'primary', fn: () => { ivSoon(() => ivAct(`${i.n} set down`, () => setDown(itemOf(i.id)))); } }] });
  ivAct(`${i.n} set down`, () => setDown(itemOf(i.id)));
}
function unpackDialog(i) {
  const c = catOf(i.cat); const off = !isGM() && !IV.self; const list = c.pack.map(([id, n]) => `${catOf(id).n} × ${n}`).join(', ');
  openDialog({ title: `Unpack ${esc(i.n)}?`, body: `${off ? `<p class="ivnotice">${ic('info')} Your GM has turned this off for you.</p>` : ''}<p class="muted" style="margin:0 0 var(--s-2h)">A dry run says what it will make, in ${esc(ownerN(i.owner))}’s hands:</p><ul class="ivnl"><li>${esc(list)}</li></ul><p class="t-meta">The pack goes.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Unpack', kind: 'primary', disabled: off, fn: () => { ivSoon(() => ivAct(`${i.n} unpacked`, () => { const x = itemOf(i.id); ITEMS = ITEMS.filter((y) => y.id !== x.id); c.pack.forEach(([id, n]) => { const k = catOf(id); ITEMS.push({ id: uid(), n: k.n, cat: id, q: n, w: k.w, owner: x.owner, at: x.owner, col: 'eq', notes: [] }); }); return null; })); } }], init: (d) => { if (off) setDisabled($('[data-a="1"]', d), true); } });
}
function reassignDialog(i) { openDialog({ title: `Reassign ${esc(i.n)}`, body: `<label class="label" for="ra">New owner</label><select id="ra" class="select">${Object.keys(BOARDS).filter((b) => b !== i.owner).map((b) => `<option value="${b}">${esc(BOARDS[b].n)}</option>`).join('')}</select><p class="t-meta">It goes to their Not carried. Its notes go with it.</p>`, actions: [{ label: 'Cancel' }, { label: 'Reassign', kind: 'primary', fn: (d) => { const o = $('#ra', d).value; ivSoon(() => ivAct(`${i.n} reassigned to ${BOARDS[o].n}`, () => { const x = itemOf(i.id); x.owner = o; x.at = o; x.col = 'nc'; return null; })); } }] }); }
function deleteDialog(i) { openDialog({ title: `Delete ${esc(i.n)}?`, label: 'alertdialog', body: `<p class="muted" style="margin:0">This removes ${i.q > 1 ? `all ${i.q}` : 'it'} from ${esc(ownerN(i.owner))}’s board, with its notes.</p>`, actions: [{ label: 'Cancel' }, { label: 'Delete', kind: 'danger', fn: () => { ivSoon(() => { IV.sel = null; ivAct(`${i.n} deleted`, () => { ITEMS = ITEMS.filter((x) => x.id !== i.id); return null; }); if (S.route.startsWith('item')) location.hash = '#/board'; }); } }] }); }
function findDialog() {
  const list = (q) => Object.keys(BOARDS).filter((b) => BOARDS[b].kind !== 'Nobody' && BOARDS[b].n.toLowerCase().includes(q.toLowerCase())).map((b) => `<button type="button" class="ivmi" data-find="${b}">${ic(BOARDS[b].kind === 'Group' ? 'kind-group' : 'kind-being')}<span>${esc(BOARDS[b].n)}</span><span class="t-meta">${BOARDS[b].kind}</span></button>`).join('') || '<p class="t-meta">No being matches.</p>';
  openDialog({ title: 'Open a board', body: `<label class="label" for="fq">Find any being</label><input id="fq" class="input" autocomplete="off"><div id="fl" class="ivfl">${list('')}</div>`, actions: [{ label: 'Cancel' }], init: (d) => { const q = $('#fq', d); q.focus(); q.addEventListener('input', () => { $('#fl', d).innerHTML = list(q.value); }); d.addEventListener('click', (e) => { const f = e.target.closest('[data-find]'); if (f) { closeOv(); remember(f.dataset.find); location.hash = '#/board'; ivRefresh(); } }); } });
}
function newCatDialog() { openDialog({ title: 'New catalog item', body: `<label class="label" for="nc-n">Name</label><input id="nc-n" class="input" autocomplete="off"><label class="label" for="nc-w" style="margin-top:var(--s-3)">Weight, lb</label><input id="nc-w" class="input" inputmode="decimal" value="1">`, actions: [{ label: 'Cancel' }, { label: 'Add to the catalog', kind: 'primary', fn: (d) => { const n = $('#nc-n', d).value.trim(); if (!n) { toast({ kind: 'error', title: 'It needs a name' }); return false; } const id = n.toLowerCase().replace(/[^a-z0-9]+/g, '-') + uid(); CAT.push({ id, n, kind: 'New', w: parseFloat($('#nc-w', d).value) || 0, v: 0, public: false, tags: [], protos: [], slug: id, desc: '' }); IV.cat = id; ivSoon(() => { ivRefresh(); announce(`${n} added to the catalog`); }); } }], init: (d) => $('#nc-n', d).focus() }); }
function saveCat() {
  const d = IV.catSave; const c = catOf(d.id);
  if (CAT.some((x) => x.id !== c.id && x.slug === d.slug)) { toast({ kind: 'error', title: 'Another item already uses that link name', text: `Change “${d.slug}” and save again. Your changes are kept.` }); return; }
  Object.assign(c, { slug: d.slug, protos: d.protos, public: d.public }); IV.catSave = null; ivRefresh(); toast({ title: `${c.n} saved` });
}
function dirtyCat(c) {
  const s = IV.catSave || { id: c.id, slug: c.slug, protos: [...c.protos], public: c.public };
  s.n = (s.slug !== c.slug) + (s.protos.join(', ') !== c.protos.join(', ')) + (s.public !== c.public); IV.catSave = s.n ? s : null; return IV.catSave;
}
function openItem(id) { IV.sel = id; if (isPhone()) { location.hash = '#/item/' + id; return; } if (isSmall()) { const it = itemOf(id); const d = openDialog({ title: esc(it.n), wide: true, body: itemView(it, 'panel'), actions: [{ label: 'Close' }] }); d.addEventListener('click', (e) => { const a = e.target.closest('[data-iv]'); if (a && a.dataset.iv !== 'closep') { closeOv(); ivSoon(() => ivClick({ target: a, __d: true })); } }); return; } ivRefresh(); const p = $('.ivp'); if (p) p.setAttribute('tabindex', '-1'); }
function switchMenu(btn) {
  const it = (b) => ({ label: BOARDS[b].n, icon: BOARDS[b].kind === 'Group' ? 'kind-group' : 'kind-being', check: IV.board === b, fn: () => { remember(b); ivRefresh(); announce(`${BOARDS[b].n}`); } });
  const items = [{ label: 'My characters', heading: true }, ...(isGM() ? Object.keys(BOARDS).filter((b) => BOARDS[b].kind === 'Character').slice(0, 2) : MINE).map(it), { label: 'My groups', heading: true }, ...GROUPS.map(it)];
  if (isGM()) items.push({ label: 'GM', heading: true }, { label: 'Find any being…', icon: 'search', fn: findDialog }, { label: 'Unowned things', icon: 'kind-item-unknown', check: IV.board === 'unowned', fn: () => { remember('unowned'); ivRefresh(); } });
  openMenu(btn, items, { label: 'Boards', align: 'left' });
}
function cardMenu(btn, id) {
  const i = itemOf(id); const ro = i.at !== IV.board && i.owner === IV.board;
  const items = [{ label: 'Open', icon: 'kind-item', fn: () => openItem(id) }];
  if (canMove(i) && !ro) items.push({ label: 'Move to…', fn: () => moveDialog([id]) }, { label: 'Give…', icon: 'give', fn: () => giveDialog([id]) }, { label: 'Set down', fn: () => downDialog(i) }, { label: 'Add a note', fn: () => noteDialog(i) }, ...(i.q > 1 ? [{ label: 'Split', fn: () => splitDialog(i) }] : []), ...(i.cat && catOf(i.cat).pack ? [{ label: 'Unpack', fn: () => unpackDialog(i) }] : []));
  if (isGM()) items.push({ sep: true }, { label: 'Reassign…', fn: () => reassignDialog(i) }, { label: 'Unassign', fn: () => ivAct(`${i.n} is unassigned`, () => { const x = itemOf(id); x.owner = 'unowned'; x.at = 'unowned'; x.col = 'nc'; return null; }) }, { label: 'Delete…', danger: true, icon: 'delete', fn: () => deleteDialog(i) });
  openMenu(btn, items, { label: `Actions for ${i.n}` });
}
function doMatch() { const g = unsGroups()[IV.uns]; const tick = IV.unsTick || new Set(g.map((i) => i.id)); const c = catOf(IV.unsPick); ivAct(`${tick.size === g.length ? 'All' : tick.size} of ${IV.uns} given to ${c.n}`, () => { g.filter((i) => tick.has(i.id)).forEach((i) => { i.cat = c.id; i.unsorted = false; }); IV.unsTick = null; return null; }, 'Their names and notes stay'); }
function ivClick(e) {
  const t = e.target.closest('[data-iv]'); if (!t) { const pk = e.target.closest('[data-pick]'); if (pk) { pk.checked ? IV.picked.add(pk.dataset.pick) : IV.picked.delete(pk.dataset.pick); ivRefresh(true); } const tk = e.target.closest('[data-tick]'); if (tk) { const g = unsGroups()[IV.uns]; IV.unsTick = IV.unsTick || new Set(g.map((i) => i.id)); tk.checked ? IV.unsTick.add(tk.dataset.tick) : IV.unsTick.delete(tk.dataset.tick); } return; }
  if (t.getAttribute('aria-disabled') === 'true') return; const k = t.dataset.iv, v = t.dataset.v; const it = v && itemOf(v);
  const fns = {
    open: () => openItem(v), menu: () => cardMenu(t, v), switch: () => switchMenu(t), add: addDialog, make: () => makeDialog(v), closep: () => { IV.sel = null; ivRefresh(); },
    multi: () => { IV.multi = !IV.multi; IV.picked = new Set(); ivRefresh(true); }, bclear: () => { IV.multi = false; IV.picked = new Set(); ivRefresh(); },
    bmove: () => moveDialog([...IV.picked]), bgive: () => giveDialog([...IV.picked]), bmerge: () => ivAct('Stacks merged', () => { mergeStacks([...IV.picked].map(itemOf)); IV.picked = new Set(); return null; }),
    col: () => { IV.col = v; ivRefresh(true); }, move: () => moveDialog([v]), give: () => giveDialog([v]), down: () => downDialog(it), note: () => noteDialog(it), split: () => splitDialog(it), unpack: () => unpackDialog(it),
    reassign: () => reassignDialog(it), unassign: () => ivAct(`${it.n} is unassigned`, () => { it.owner = 'unowned'; it.at = 'unowned'; it.col = 'nc'; return null; }), delete: () => deleteDialog(it),
    copy: () => { try { navigator.clipboard.writeText(location.href); } catch (er) { /* fallback: nothing */ } toast({ title: 'Link copied' }); },
    cat: () => { if (IV.catSave) { toast({ kind: 'error', title: 'Save or discard the changes first', text: `${IV.catSave.n} change${IV.catSave.n === 1 ? '' : 's'} on ${catOf(IV.catSave.id).n} are not saved.` }); return; } IV.cat = v; if (isSmall()) { location.hash = '#/catitem/' + v; return; } ivRefresh(true); }, newcat: newCatDialog,
    ctag: () => { const c = catOf(IV.cat); c.tags = c.tags.includes(v) ? c.tags.filter((x) => x !== v) : [...c.tags, v]; ivRefresh(true); announce('Saved'); },
    used: () => { const c = catOf(IV.cat); const u = CAT.filter((x) => x.protos.includes(c.n)); openDialog({ title: `Used as a prototype by ${u.length}`, body: u.length ? `<ul class="ivnl">${u.map((x) => `<li>${esc(x.n)}</li>`).join('')}</ul>` : '<p class="muted">Nothing is made from it.</p>', actions: [{ label: 'Close' }] }); },
    cdelete: () => { const c = catOf(IV.cat); const n = ITEMS.filter((i) => i.cat === c.id).length; if (n) { toast({ kind: 'error', title: `${c.n} is in use`, text: `${pl(n, 'item was', 'items were')} made from it. Delete or unassign them first.`, action: { label: 'Close', fn: () => {} } }); return; } openDialog({ title: `Delete ${esc(c.n)}?`, label: 'alertdialog', body: '<p class="muted" style="margin:0">It leaves the catalog. Nothing is made from it.</p>', actions: [{ label: 'Cancel' }, { label: 'Delete', kind: 'danger', fn: () => { const i = CAT.indexOf(c); CAT.splice(i, 1); IV.cat = CAT[0].id; ivSoon(() => { ivRefresh(); withUndo(`${c.n} deleted`, () => { CAT.splice(i, 0, c); ivRefresh(); }); }); } }] }); },
    save: saveCat, discard: () => { IV.catSave = null; ivRefresh(); announce('Changes discarded'); },
    uns: () => { IV.uns = v; IV.unsTick = null; IV.unsPick = (unsSuggest(v)[0] || {}).id || null; if (isSmall()) { location.hash = '#/unsitem/' + encodeURIComponent(v); return; } ivRefresh(true); }, pick: () => { IV.unsPick = v; ivRefresh(true); },
    match: doMatch,
    makecat: () => openDialog({ title: 'Make a new catalog item', body: `<label class="label" for="mc-n">Name</label><input id="mc-n" class="input" value="${esc(IV.uns)}" autocomplete="off">`, actions: [{ label: 'Cancel' }, { label: 'Make it and give the ticked', kind: 'primary', fn: (d) => { const n = $('#mc-n', d).value.trim(); if (!n) return false; const id = n.toLowerCase().replace(/[^a-z0-9]+/g, '-') + uid(); CAT.push({ id, n, kind: 'New', w: 1, v: 0, public: false, tags: [], protos: [], slug: id, desc: '' }); IV.unsPick = id; ivSoon(doMatch); } }] }),
    keep: () => toast({ title: `${IV.uns} kept for now`, text: 'It stays in this list.' }),
  };
  if (fns[k]) fns[k]();
}
function ivInput(e) {
  const t = e.target;
  if (t.id === 'ivq') { IV.q = t.value; ivRefresh(true); announce(pl(colsOf(IV.board).reduce((n, c) => n + c.items.length, 0), 'card', 'cards')); }
  else if (t.id === 'cq') { IV.cq = t.value; ivRefresh(true); }
  else if (t.id === 'iv-desc' || t.id === 'iv-cdesc') { const it = t.id === 'iv-desc' ? catOf(itemOf(parts()[1]).cat) : catOf(IV.cat); it.desc = t.innerText; clearTimeout(IV.st); const el = $('#iv-saved'); if (el) el.textContent = 'Saving…'; IV.st = setTimeout(() => { const e2 = $('#iv-saved'); if (e2) e2.textContent = 'Saved'; announce('Saved'); }, 600); }
  else if (t.dataset.fld) { const c = catOf(IV.cat); IV.catSave = IV.catSave && IV.catSave.id === c.id ? IV.catSave : { id: c.id, slug: c.slug, protos: [...c.protos], public: c.public }; const f = t.dataset.fld; if (f === 'public') IV.catSave.public = t.checked; else if (f === 'protos') IV.catSave.protos = t.value.split(',').map((x) => x.trim()).filter(Boolean); else IV.catSave.slug = t.value; dirtyCat(c); ivRefresh(true); }
}
function ivChange(e) {
  const t = e.target;
  if (t.dataset.st) { const it = itemOf(parts()[1]); const n = parseFloat(t.value); if (isNaN(n) || n < 0) { toast({ kind: 'error', title: 'That is not a number', text: 'A weight is zero or more.' }); t.value = it.w; return; } it.w = n; announce('Saved'); ivSoon(() => ivRefresh(true)); }
  else if (t.dataset.cst) { const c = catOf(IV.cat); const n = parseFloat(t.value); if (isNaN(n) || n < 0) { toast({ kind: 'error', title: 'That is not a number' }); t.value = c[t.dataset.cst]; return; } c[t.dataset.cst] = n; announce('Saved'); }
  else if (t.dataset.ivSel === 'pickc' || t.matches('[data-iv-sel]')) { IV.unsPick = t.value || null; ivRefresh(true); }
}
function ivAfter() {
  const m = $('#main'); m.onclick = ivClick; m.oninput = ivInput; m.onchange = ivChange;
  const bd = $('#ivboard'); if (bd) {
    bd.ondragstart = (e) => { const c = e.target.closest('[data-it]'); if (c && e.dataTransfer) { e.dataTransfer.setData('text/plain', c.dataset.it); e.dataTransfer.effectAllowed = 'move'; } };
    bd.ondragover = (e) => { const c = e.target.closest('.ivc'); if (c && !c.classList.contains('ro')) e.preventDefault(); };
    bd.ondrop = (e) => { const c = e.target.closest('.ivc'); if (!c || c.classList.contains('ro')) return; e.preventDefault(); const i = itemOf(e.dataTransfer.getData('text/plain')); if (!i || i.at !== IV.board || i.col === c.dataset.col) return; const name = colN(IV.board, c.dataset.col); ivAct(`${i.n} moved to ${name}`, () => moveTo(itemOf(i.id), IV.board, c.dataset.col)); };
  }
}
const ivr = (tab, render, meta) => ({ app: 'inventory', tab, render, full: false, after: ivAfter, meta: meta || (() => '') });
window.ROUTES_EXT = {
  board: ivr('board', boardRoute, () => (IV.board && BOARDS[IV.board] ? `Carried ${carriedW(IV.board)} of 120 lb` : '')),
  item: { app: 'inventory', tab: 'board', render: pItem, full: false, after: ivAfter, meta: () => '' },
  catalog: ivr('catalog', pCatalog), catitem: { app: 'inventory', tab: 'catalog', render: pCatItem, full: false, after: ivAfter, meta: () => '' }, unsitem: { app: 'inventory', tab: 'unsorted', render: () => (isGM() ? pUnsItem() : ''), full: false, after: ivAfter, meta: () => '' }, unsorted: { app: 'inventory', tab: 'unsorted', render: () => (isGM() ? pUnsorted() : `<div class="page page--wide page-enter iv"><div class="ivempty"><p><b>This page does not exist.</b></p><p class="t-meta">The link may be wrong, or it is not a page you can open.</p><a class="btn" href="#/board">Back to the board</a></div></div>`), full: false, after: ivAfter, meta: () => '' },
};
window.START_ROUTE = 'board'; window.INWORLD = () => null;
DATA.apps.find((a) => a.id === 'inventory').route = 'board'; DATA.appTabs.inventory = [['Board', 'board'], ['Catalog', 'catalog'], ['Unsorted', 'unsorted']]; TAB_ICONS.board = 'inventory'; TAB_ICONS.catalog = 'kind-items'; TAB_ICONS.unsorted = 'kind-item-unknown';
window.TAB_HIDE = (t) => t === 'unsorted' && S.role !== 'gm';
const PBi = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Self-service (a player)</b>${[['on', 'On'], ['off', 'Off']].map(([v, t]) => PBi('ivself', v, t, (v === 'on') === IV.self)).join('')}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p="ivself"]').forEach((b) => b.setAttribute('aria-pressed', (b.dataset.v === 'on') === IV.self)); };
window.PROTO_CLICK = (k, v) => { if (k !== 'ivself') return false; IV.self = v === 'on'; return true; };

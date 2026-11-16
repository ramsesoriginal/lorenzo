/* Beings: routes, actions and the controls bar. */
const curBeing = () => beingOf(parts()[1]);
function bnRefresh(keepFocus) {
  const m = $('#main'); const top = m.scrollTop; const f = document.activeElement; let sel = null;
  if (keepFocus && f && m.contains(f)) { const a = f.dataset.bn ? `[data-bn="${f.dataset.bn}"]${f.dataset.b ? `[data-b="${f.dataset.b}"]` : ''}${f.dataset.v ? `[data-v="${f.dataset.v}"]` : ''}${f.dataset.d ? `[data-d="${f.dataset.d}"]` : ''}` : f.id ? `#${f.id}` : null; sel = a; }
  const r = cur(); S.meta = r.meta ? r.meta() : ''; m.innerHTML = r.render(); bnAfter(); m.scrollTop = top;
  if (sel) { const n = $(sel, m); if (n) n.focus({ preventScroll: true }); }
  updateStatus(); bnWatch();
}
const bnSoon = (fn) => setTimeout(fn, 0);
function bnWatch() {
  const m = $('#main'), s = $('.bn-sent', m), band = $('#bn-band', m); if (!s || !band) return;
  if (BN.io) BN.io.disconnect();
  BN.io = new IntersectionObserver(([en]) => band.classList.toggle('compact', !en.isIntersecting && en.boundingClientRect.top < 0), { root: m, threshold: 0 }); BN.io.observe(s);
}
function setMode(b, v) { BN.mode = v; BN.editAbout = false; BN.editStat = null; BN.adjustOpen = null; BN.editNote = null; if (mine(b) && !isGM()) bnStore.set(modeKey(b), v); announce(v === 'play' ? 'Play. Numbers can be changed.' : 'Read'); }
let bnToast = null;
function stepToast(b, h) {
  if (bnToast && bnToast.isConnected) dismiss(bnToast, true);
  bnToast = toast({ kind: 'undo', icon: 'undo', title: h.n, text: `${b.name}, by you`, action: { label: 'Undo', fn: () => { const l = bnHist(b); if (l[l.length - 1] === h) { undoLast(b); bnRefresh(); } else toast({ title: 'A later step came after this one', text: 'Undo that step first, or use History.', kind: 'error' }); } } });
}
function doStep(b, id, delta) {
  const before = bnHist(b).length; if (!playStep(b, id, b.stats[id].v + delta)) { bnRefresh(true); return; }
  const h = BN.hist[BN.hist.length - 1]; stepToast(b, h); bnRefresh(true);
}
function applyAdjust(b, id) {
  const i = $(`[data-adj="${id}"]`); const t = (i.value || '').trim().replace('−', '-');
  if (!/^[+-]?\d+$/.test(t)) { toast({ kind: 'error', title: 'That is not a number', text: 'Type 5 to set it, or +3 or -2 to change it.', action: { label: 'Try again', fn: () => i.focus() } }); return; }
  const to = /^[+-]/.test(t) ? b.stats[id].v + parseInt(t, 10) : parseInt(t, 10);
  BN.adjustOpen = null; if (playStep(b, id, to)) stepToast(b, BN.hist[BN.hist.length - 1]); bnRefresh(true);
}
function histMenu(btn, b) {
  const l = bnHist(b); if (!l.length) return;
  openMenu(btn, [{ label: `Steps in Play, newest first (${l.length} of 30)`, heading: true }, ...l.map((h, i) => ({ label: `Undo back to before: ${h.n}, by ${whoLabel(h)}, ${h.at}`, icon: 'undo', fn: () => { const n = undoTo(b, i); announce(`Undid ${n} step${n > 1 ? 's' : ''}`); bnRefresh(); } })).reverse()], { label: 'History' });
}
function addNoteDialog(b, edit) {
  const n = edit || { aud: 'Everyone', t: '', who: [] };
  const auds = ['Everyone', 'GM only', 'Some characters', 'Player note'];
  const others = BEINGS.filter((x) => x.kind === 'Character' && x.id !== b.id).map((x) => x.name);
  openDialog({ title: edit ? 'Change the note' : 'Add a note', body: `<fieldset class="bn-fs"><legend class="label">Who can read it</legend>${auds.map((a) => `<label class="bn-rd"><input type="radio" name="aud" value="${a}" ${a === n.aud ? 'checked' : ''}> ${bnAud(a)}</label>`).join('')}</fieldset><div id="bn-who" ${n.aud === 'Some characters' ? '' : 'hidden'}><div class="label">Which characters</div>${others.map((o) => `<label class="bn-rd"><input type="checkbox" name="who" value="${esc(o)}" ${(n.who || []).includes(o) ? 'checked' : ''}> ${esc(o)}</label>`).join('')}</div><label class="label" for="bn-nt">The note</label><textarea id="bn-nt" class="input bn-ta">${esc(n.t)}</textarea>`,
    actions: [{ label: 'Cancel' }, { label: edit ? 'Save the note' : 'Add the note', kind: 'primary', fn: (d) => { const t = $('#bn-nt', d).value.trim(); if (!t) { toast({ kind: 'error', title: 'A note needs some words' }); return false; } const a = $('input[name=aud]:checked', d).value; const who = a === 'Some characters' ? $$('input[name=who]:checked', d).map((x) => x.value) : []; if (edit) { Object.assign(edit, { aud: a, t, who }); announce('Note saved'); } else { const note = { id: uidn(), aud: a, t, who }; b.notes.push(note); withUndo('Note added', () => { b.notes = b.notes.filter((x) => x !== note); bnRefresh(); }, a); } bnSoon(bnRefresh); } }],
    init: (d) => { $$('input[name=aud]', d).forEach((r) => r.addEventListener('change', () => { $('#bn-who', d).hidden = $('input[name=aud]:checked', d).value !== 'Some characters'; })); $('#bn-nt', d).focus(); } });
}
function handOverDialog(b) {
  openDialog({ title: `Hand over ${esc(b.name)}`, body: `<p class="muted" style="margin:0 0 var(--s-3)">Choose a campaign, then who plays ${esc(b.name)}. The player can play it and change it. You can hand it over again.</p><label class="label" for="ho-c">Campaign</label><select id="ho-c" class="select">${CAMPAIGNS.map((c) => `<option value="${c.id}" ${c.id === b.campaign ? 'selected' : ''}>${esc(c.n)}</option>`).join('')}</select><label class="label" for="ho-p" style="margin-top:var(--s-3)">Player</label><select id="ho-p" class="select"></select>`,
    actions: [{ label: 'Cancel' }, { label: 'Hand over', kind: 'primary', fn: (d) => { const p = $('#ho-p', d).value; const was = b.played, wasC = b.campaign; b.played = p; b.campaign = $('#ho-c', d).value; withUndo(`${b.name} is now played by ${personName(p)}`, () => { b.played = was; b.campaign = wasC; bnRefresh(); }); bnSoon(bnRefresh); } }],
    init: (d) => { const fill = () => { const c = CAMPAIGNS.find((x) => x.id === $('#ho-c', d).value); $('#ho-p', d).innerHTML = c.players.map((p) => `<option value="${p}" ${p === b.played ? 'selected' : ''}>${esc(personName(p))}</option>`).join(''); }; fill(); $('#ho-c', d).addEventListener('change', fill); } });
}
function deleteDialog(b) {
  const owns = b.inv.length;
  openDialog({ title: `Delete ${esc(b.name)}?`, label: 'alertdialog', body: `<p class="muted" style="margin:0 0 var(--s-2h)">This removes ${esc(b.name)} for everyone in the library. It cannot be undone.</p><ul class="bn-cons"><li>Its stats, notes, link name and place in rosters go with it.</li><li>${owns} item${owns === 1 ? '' : 's'}: those it both owns and carries are deleted. Items it only carries stay with their owners. Items it only owns stay, and are no longer carried.</li></ul><label class="label" for="dl-n">Type <b style="color:var(--text-primary)">${esc(b.name)}</b> to confirm</label><input id="dl-n" class="input" autocomplete="off"><p class="t-meta" id="dl-h" style="margin:var(--s-1) 0 0">Type the full name to continue.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Delete being', kind: 'danger', disabled: true, fn: () => { const i = BEINGS.indexOf(b); BEINGS.splice(i, 1); const kept = BN.hist.filter((h) => h.b === b.id); BN.hist = BN.hist.filter((h) => h.b !== b.id); location.hash = '#/beings'; bnSoon(() => toast({ title: `${b.name} was deleted`, text: 'The prototype puts it back when you undo.', kind: 'undo', action: { label: 'Undo', fn: () => { BEINGS.splice(i, 0, b); BN.hist.push(...kept); bnRefresh(); } } })); } }],
    init: (d) => { const btn = $('[data-a="1"]', d), i = $('#dl-n', d); i.addEventListener('input', () => { const ok = i.value.trim() === b.name; setDisabled(btn, !ok); $('#dl-h', d).textContent = ok ? 'This cannot be undone.' : 'Type the full name to continue.'; }); } });
}
function newDialog() {
  openDialog({ title: 'New being', body: `<p class="muted" style="margin:0 0 var(--s-3)">A new being has no player until you hand it over. Its stats come from the library’s Settings.</p><label class="label" for="nb-n">Name</label><input id="nb-n" class="input" autocomplete="off"><label class="label" for="nb-k" style="margin-top:var(--s-3)">Kind</label><select id="nb-k" class="select"><option>NPC</option><option>Character</option></select>`,
    actions: [{ label: 'Cancel' }, { label: 'Make the being', kind: 'primary', fn: (d) => { const n = $('#nb-n', d).value.trim(); if (!n) { toast({ kind: 'error', title: 'A being needs a name' }); return false; } const id = n.toLowerCase().replace(/[^a-z0-9]+/g, '-') + '-' + uidn(); BEINGS.push(mk(id, n, $('#nb-k', d).value, null, null, 'GM only', 'Nowhere yet', '', { stats: { hp: { v: 10, max: 10 }, res: { v: 3, max: 3 }, body: { v: 2 }, mind: { v: 2 }, reach: { v: 2 }, role: { v: '' }, langs: { v: [] }, cond: { v: [] } } })); BN.mode = 'read'; bnSoon(() => { location.hash = '#/being/' + id; }); } }], init: (d) => $('#nb-n', d).focus() });
}
function renameDialog(b) {
  openDialog({ title: 'Rename the being', body: `<label class="label" for="rn">Name</label><input id="rn" class="input" value="${esc(b.name)}" autocomplete="off">`, actions: [{ label: 'Cancel' }, { label: 'Rename', kind: 'primary', fn: (d) => { const n = $('#rn', d).value.trim(); if (!n) { toast({ kind: 'error', title: 'A being needs a name' }); return false; } const o = b.name; b.name = n; withUndo(`Renamed to ${n}`, () => { b.name = o; bnRefresh(); }); bnSoon(bnRefresh); } }], init: (d) => $('#rn', d).select() });
}
function bnClick(e) {
  const t = e.target.closest('[data-bn]'); if (!t) return; const k = t.dataset.bn, v = t.dataset.v; const b = t.dataset.b ? beingOf(t.dataset.b) : (S.route.startsWith('being') ? curBeing() : null);
  if (t.getAttribute('aria-disabled') === 'true') return;
  if (k === 'view') { BN.view = v; bnStore.set('bn-view', v); bnRefresh(true); announce(`${v === 'side' ? 'Side by side' : v === 'rows' ? 'Rows' : 'Cards'}`); }
  else if (k === 'kind') { BN.kind = v; bnRefresh(true); }
  else if (k === 'clear') { BN.q = ''; BN.kind = 'All'; bnRefresh(); }
  else if (k === 'new') newDialog();
  else if (k === 'lplay') { BN.lplay = v === 'play'; bnRefresh(true); announce(BN.lplay ? 'Play. Numbers can be changed.' : 'Read'); }
  else if (k === 'lundo') { const h = undoLast(null); if (h) { toast({ title: `Undid: ${h.n}`, text: beingOf(h.b).name }); bnRefresh(true); } }
  else if (!b) return;
  else if (k === 'mode') { setMode(b, v); bnRefresh(true); }
  else if (k === 'layout') { BN.layout = v; bnRefresh(true); }
  else if (k === 'step') doStep(b, v, +t.dataset.d);
  else if (k === 'adjust') { BN.adjustOpen = BN.adjustOpen === v ? null : v; bnRefresh(); if (BN.adjustOpen) bnSoon(() => { const i = $(`[data-adj="${v}"]`); if (i) i.focus(); }); else bnSoon(() => { const a = $(`[data-bn="adjust"][data-v="${v}"]`); if (a) a.focus(); }); }
  else if (k === 'apply') applyAdjust(b, v);
  else if (k === 'cond') { const h = toggleCond(b, v); stepToast(b, h); bnRefresh(true); }
  else if (k === 'undo') { const h = undoLast(b); if (h) { toast({ title: `Undid: ${h.n}`, text: b.name }); bnRefresh(true); } }
  else if (k === 'history') histMenu(t, b);
  else if (k === 'why') { BN.why = BN.why === v ? null : v; bnRefresh(true); }
  else if (k === 'editstat') { BN.editStat = BN.editStat === v ? null : v; bnRefresh(); if (BN.editStat) bnSoon(() => { const i = $(`#v-${v}`); if (i) i.select(); }); }
  else if (k === 'editabout') { BN.editAbout = !BN.editAbout; BN.saved = ''; bnRefresh(); if (BN.editAbout) bnSoon(() => { const i = $('#bn-about'); if (i) i.focus(); }); }
  else if (k === 'addnote') addNoteDialog(b);
  else if (k === 'notemenu') { const n = b.notes.find((x) => x.id === v); openMenu(t, [{ label: 'Edit the words', icon: 'edit', fn: () => { BN.editNote = v; bnRefresh(); bnSoon(() => { const i = $(`[data-note="${v}"]`); if (i) i.focus(); }); } }, { label: 'Change who reads it…', icon: 'visibility', fn: () => addNoteDialog(b, n) }, { sep: true }, { label: 'Delete the note', icon: 'delete', danger: true, fn: () => { const i = b.notes.indexOf(n); b.notes.splice(i, 1); bnRefresh(); withUndo('Note deleted', () => { b.notes.splice(i, 0, n); bnRefresh(); }, n.aud); } }], { label: `Actions for the ${n.aud} note` }); }
  else if (k === 'notedone') { BN.editNote = null; announce('Note saved'); bnRefresh(); }
  else if (k === 'handover') handOverDialog(b);
  else if (k === 'more') openMenu(t, [{ label: 'Rename…', icon: 'edit', fn: () => renameDialog(b) }, { sep: true }, { label: 'Delete being…', icon: 'delete', danger: true, fn: () => deleteDialog(b) }], { label: `More for ${b.name}` });
}
function bnInput(e) {
  const t = e.target; const b = S.route.startsWith('being') ? curBeing() : null;
  if (t.id === 'bn-q') { BN.q = t.value; $('#bn-body').innerHTML = listBody(); announce(`${listBeings().length} beings`); return; }
  if (!b) return;
  if (t.id === 'bn-about') { b.about = t.innerText; clearTimeout(BN.st); const el = $('#bn-saved'); if (el) el.textContent = 'Saving…'; BN.st = setTimeout(() => { BN.saved = `Saved at ${bnClock()}`; const e2 = $('#bn-saved'); if (e2) e2.textContent = BN.saved; announce('Saved'); }, 600); }
  else if (t.dataset.note) { const n = b.notes.find((x) => x.id === t.dataset.note); if (n) n.t = t.value; }
}
function bnChange(e) {
  const t = e.target; const b = S.route.startsWith('being') ? curBeing() : null; if (!b || !t.dataset.stat) return;
  const s = b.stats[t.dataset.stat]; const n = parseInt(t.value, 10);
  if (isNaN(n) || n < 0) { toast({ kind: 'error', title: 'That is not a number', text: 'Stats are whole numbers, zero or more.' }); t.value = s[t.dataset.f]; return; }
  if (t.dataset.f === 'max') { s.max = n; if (s.v > n) s.v = n; } else s.v = s.max != null ? Math.min(n, s.max) : n;
  announce('Saved'); bnSoon(() => bnRefresh(true));
}
function bnAfter() {
  const m = $('#main'); m.onclick = bnClick; m.oninput = bnInput; m.onchange = bnChange;
  m.onkeydown = (e) => { if (e.key === 'Enter' && e.target.matches('[data-adj]')) { e.preventDefault(); applyAdjust(curBeing(), e.target.dataset.adj); } else if (e.key === 'Enter' && e.target.matches('[data-stat]')) e.target.blur(); else if (e.key === 'Escape' && e.target.matches('[data-adj]')) { BN.adjustOpen = null; bnRefresh(); } };
}
document.addEventListener('keydown', (e) => { if (!S.route.startsWith('being') || BN.mode !== 'play') return; if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z' && !e.target.closest('input, textarea, [contenteditable]')) { const b = curBeing(); if (b && undoLast(b)) { e.preventDefault(); bnRefresh(true); } } });
const bnr = (tab, render, meta) => ({ app: 'beings', tab, render, full: false, after: bnAfter, meta: meta || (() => '') });
window.ROUTES_EXT = {
  beings: bnr('beings', pList, () => `${pl(listBeings().length, 'being', 'beings')}`),
  mine: bnr('mine', pList, () => `${pl(listBeings().length, 'being', 'beings')}`),
  being: { app: 'beings', tab: 'beings', render: () => { const b = curBeing(); if (b && BN.seen !== b.id) { BN.seen = b.id; BN.mode = openMode(b); BN.editAbout = false; BN.editStat = null; BN.adjustOpen = null; BN.editNote = null; BN.why = null; BN.saved = ''; } return pBeing(); }, full: false, after: () => { bnAfter(); bnWatch(); }, meta: () => { const b = curBeing(); return b ? `${b.kind}${b.played ? ` · ${personName(b.played)}` : ''}` : ''; } },
};
window.START_ROUTE = 'beings'; window.INWORLD = () => null;
DATA.apps.find((a) => a.id === 'beings').route = 'beings'; DATA.appTabs.beings = [['All beings', 'beings'], ['Mine', 'mine']]; TAB_ICONS.mine = 'kind-being';
const bnv = bnStore.get('bn-view'); if (bnv) BN.view = bnv;
const PBn = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Beings</b>${[['one', 'Open Mara Quill'], ['empty', 'An empty library']].map(([v, t]) => PBn('bnx', v, t, false)).join('')}</span>`;
window.PROTO_SYNC = () => {};
window.PROTO_CLICK = (k, v) => { if (k !== 'bnx') return false; if (v === 'one') go('being/mara-quill'); else { BN.empty = !BN.empty; go('beings'); render(true); } return true; };

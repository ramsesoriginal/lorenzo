/* Social: routes, actions, dialogs, the graph's pointer and keys, the matrix's keys and its save. */
function scRefresh(keepFocus) {
  const m = $('#main'); const top = m.scrollTop; const f = document.activeElement; let sel = null, pos = null;
  if (keepFocus && f && m.contains(f)) { sel = f.id ? `#${f.id}` : f.dataset.cell ? `[data-cell="${f.dataset.cell}"]` : f.dataset.ent ? `[data-ent="${f.dataset.ent}"]` : f.dataset.so ? `[data-so="${f.dataset.so}"]${f.dataset.v ? `[data-v="${CSS.escape(f.dataset.v)}"]` : ''}` : null; if (f.selectionStart != null) pos = [f.selectionStart, f.selectionEnd]; }
  const r = cur(); S.meta = r.meta ? r.meta() : ''; m.innerHTML = r.render(); scAfter(); m.scrollTop = top;
  if (sel) { const n = $(sel, m); if (n) { n.focus({ preventScroll: true }); if (pos && n.setSelectionRange) n.setSelectionRange(pos[0], pos[1]); } }
  updateStatus();
}
const scSoon = (fn) => setTimeout(fn, 0);
/* change something, and offer Undo; a refusal is shown as given and nothing changes */
function scAct(title, fn, text) {
  const before = snapS(); const err = fn();
  if (err) { restoreS(before); toast({ kind: 'error', title: 'That did not work', text: err, action: { label: 'Close', fn: () => {} } }); scRefresh(true); return false; }
  scRefresh(true); announce(title); withUndo(title, () => { restoreS(before); scRefresh(); }, text); return true;
}
function fieldError(input, msg) { let p = input.parentElement.querySelector('.soerr'); if (!p) { p = document.createElement('p'); p.className = 'soerr'; p.setAttribute('role', 'alert'); input.parentElement.appendChild(p); } p.textContent = msg; input.setAttribute('aria-invalid', 'true'); }
function clearFieldError(input) { const p = input.parentElement.querySelector('.soerr'); if (p) p.parentNode.removeChild(p); input.removeAttribute('aria-invalid'); }
const relName = (a, b, t) => `${entName(a)} - ${typeOf(t).n} - ${entName(b)}`;
function makeRel(a, b, type, vals, extra) { const r = { id: uid(), a, b, type, vals: vals || {}, since: null, until: null, aud: 'restricted', readers: [], through: [], notes: '', ...extra }; RELS.push(r); return r; }
/* ---- dialogs */
function newRelDialog(a, b) {
  const ids = Object.keys(ENTS).filter(entVisible); const opt = (sel) => ids.map((i) => `<option value="${i}" ${i === sel ? 'selected' : ''}>${esc(entName(i))}</option>`).join('');
  openDialog({ title: 'New relationship', body: `<p class="muted" style="margin:0 0 var(--s-2h)">A relationship is between two entries and has a type from this library. It starts restricted; choose who may read it afterwards.</p><label class="label" for="nr-a">From</label><select id="nr-a" class="select">${opt(a)}</select><label class="label" for="nr-t" style="margin-top:var(--s-3)">Type</label><select id="nr-t" class="select">${TYPES.filter((t) => t.reads).map((t) => `<option value="${t.id}">${esc(typePath(t.id))}</option>`).join('')}</select><p class="t-meta" id="nr-d"></p><label class="label" for="nr-b" style="margin-top:var(--s-3)">To</label><select id="nr-b" class="select">${opt(b)}</select><label class="label" for="nr-v" style="margin-top:var(--s-3)">Reputation <span class="t-meta">optional</span></label><input id="nr-v" class="input" inputmode="numeric" aria-describedby="nr-h"><p class="t-meta" id="nr-h">${scaleWords('rep')}.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Make the relationship', kind: 'primary', fn: (d) => { const A = $('#nr-a', d).value, B = $('#nr-b', d).value, T = $('#nr-t', d).value, V = $('#nr-v', d).value.trim(); if (A === B) { toast({ kind: 'error', title: 'A relationship needs two different ends', text: 'Choose another entry for one of them.' }); return false; } if (V !== '') { const e = validateStanding('rep', V); if (e) { fieldError($('#nr-v', d), e); return false; } } scSoon(() => scAct(`${relName(A, B, T)} made`, () => { makeRel(A, B, T, V === '' ? {} : { rep: Number(V) }); return null; }, 'Restricted')); } }],
    init: (d) => { const note = () => { const t = typeOf($('#nr-t', d).value); $('#nr-d', d).textContent = `Reads “A ${t.reads} B”. ${t.directed ? 'One-way, from A to B.' : 'Two-way: it fills both cells of the pair.'}`; }; note(); $('#nr-t', d).addEventListener('change', note); } });
}
function membersDialog() {
  const web = webOf(SC.web);
  const draw = (d) => { const list = web.members.filter(entVisible); const sel = SC.sel && SC.sel.k === 'ent' ? SC.sel.id : null; $('#mb', d).innerHTML = `<p class="t-meta">${pl(list.length, 'member', 'members')} of at most 500. A web shows exactly the entries added here; nothing is added by a rule.</p><ul class="sorows">${list.map((i) => `<li><span>${icEnt(i)} ${esc(entName(i))}</span><button type="button" class="btn sm ghost" data-mrem="${i}" aria-label="Remove ${esc(entName(i))} from the web">Remove</button></li>`).join('') || '<li class="muted">No one yet.</li>'}</ul>`; $('#mr', d).innerHTML = Object.keys(ENTS).filter((i) => entVisible(i) && !web.members.includes(i) && entName(i).toLowerCase().includes($('#mq', d).value.toLowerCase())).slice(0, 6).map((i) => `<button type="button" class="ivmi" data-madd="${i}">${icEnt(i)}<span>${esc(entName(i))}</span><span class="t-meta">${ENTS[i].k}</span></button>`).join('') || '<p class="t-meta">No other entry matches.</p>'; };
  openDialog({ title: 'Members of this web', wide: true, body: `<label class="label" for="mq">Add by name</label><input id="mq" class="input" autocomplete="off" placeholder="Search entries"><div id="mr" class="somr"></div>
  <div class="row2 somact"><label class="solbl" for="mg">Add a group’s members</label><select id="mg" class="select sm">${Object.keys(GROUP_MEMBERS).map((g) => `<option value="${g}">${esc(entName(g))}</option>`).join('')}</select><button type="button" class="btn sm" id="mga">Add them</button></div>
  <div class="row2 somact"><label class="solbl" for="mn">Add everyone within</label><select id="mn" class="select sm"><option>1</option><option selected>2</option><option>3</option></select><span class="t-meta">steps of</span><span id="mfrom" class="t-meta"></span><button type="button" class="btn sm" id="mna">Add them</button></div><div id="mb"></div>`,
    actions: [{ label: 'Done', kind: 'primary' }],
    init: (d) => { const sel = SC.sel && SC.sel.k === 'ent' ? SC.sel.id : null; $('#mfrom', d).textContent = sel ? entName(sel) : 'the selected entry (select one first)'; if (!sel) setDisabled($('#mna', d), true); const before = snapS(); draw(d); $('#mq', d).addEventListener('input', () => draw(d));
      d.addEventListener('click', (e) => { const a = e.target.closest('[data-madd]'), r = e.target.closest('[data-mrem]'); if (a) { web.members.push(a.dataset.madd); draw(d); announce(`${entName(a.dataset.madd)} added`); } if (r) { web.members = web.members.filter((x) => x !== r.dataset.mrem); draw(d); announce(`${entName(r.dataset.mrem)} removed`); } if (e.target.closest('#mga')) { const g = $('#mg', d).value; let n = 0; GROUP_MEMBERS[g].filter(entVisible).forEach((m) => { if (!web.members.includes(m)) { web.members.push(m); n++; } }); draw(d); announce(`${pl(n, 'entry', 'entries')} added`); } if (e.target.closest('#mna') && sel) { let n = 0; neighbours(web, sel, Number($('#mn', d).value)).forEach((m) => { if (entVisible(m) && !web.members.includes(m)) { web.members.push(m); n++; } }); draw(d); announce(`${pl(n, 'entry', 'entries')} added`); } });
      OV.onClose = () => { if (snapS() !== before) { withUndo('Members changed', () => { restoreS(before); scRefresh(); }); scRefresh(); } }; } });
}
function audienceDialog(r) {
  const beings = Object.keys(ENTS).filter((i) => ENTS[i].k === 'being' || ENTS[i].k === 'group');
  openDialog({ title: 'Who may read it', body: `<fieldset class="ivfs2"><legend class="sr-only">Audience</legend><label class="ivrd"><input type="radio" name="aud" value="restricted" ${r.aud === 'restricted' ? 'checked' : ''}> <span>Restricted: the GMs and the people named</span></label><label class="ivrd"><input type="radio" name="aud" value="public" ${r.aud === 'public' ? 'checked' : ''}> <span>Everyone who can read both ends</span></label></fieldset><div id="rd"><div class="label">Named recipients</div>${beings.map((i) => `<label class="ivrd"><input type="checkbox" name="rc" value="${i}" ${r.readers.includes(i) ? 'checked' : ''}> <span>${esc(entName(i))}</span><span class="t-meta">${ENTS[i].k}</span></label>`).join('')}</div><p class="t-meta">Changed as a whole, with the version you saw. If someone changed it meanwhile you are asked to review first.</p>`,
    actions: [{ label: 'Cancel' }, { label: 'Save who may read it', kind: 'primary', fn: (d) => { const a = $('input[name=aud]:checked', d).value; const rc = $$('input[name=rc]:checked', d).map((x) => x.value); scSoon(() => scAct('Who may read it changed', () => { const x = relOf(r.id); x.aud = a; x.readers = rc; return null; })); } }] });
}
function typeDialog(t) {
  const isNew = !t; const v = t || { n: '', parent: null, directed: true, reads: '', back: '' };
  openDialog({ title: isNew ? 'New type' : `Edit ${esc(v.n)}`, body: `<label class="label" for="tn">Name</label><input id="tn" class="input" value="${esc(v.n)}" autocomplete="off"><label class="label" for="tp" style="margin-top:var(--s-3)">Part of</label><select id="tp" class="select"><option value="">Nothing</option>${TYPES.filter((x) => !t || x.id !== t.id).map((x) => `<option value="${x.id}" ${v.parent === x.id ? 'selected' : ''}>${esc(x.n)}</option>`).join('')}</select><label class="ivrd" style="margin-top:var(--s-3)"><input type="checkbox" id="td" ${v.directed ? 'checked' : ''}> <span>One-way (it reads differently from each end)</span></label><label class="label" for="tr">Reads as (“A … B”)</label><input id="tr" class="input" value="${esc(v.reads || '')}" autocomplete="off"><label class="label" for="tb" style="margin-top:var(--s-3)">Reads as, from the other end</label><input id="tb" class="input" value="${esc(v.back || '')}" autocomplete="off">`,
    actions: [{ label: 'Cancel' }, { label: isNew ? 'Add the type' : 'Save the type', kind: 'primary', fn: (d) => { const n = $('#tn', d).value.trim(); if (!n) { fieldError($('#tn', d), 'A type needs a name.'); return false; } const par = $('#tp', d).value || null; if (t && par) { let p = typeOf(par); while (p) { if (p.id === t.id) { fieldError($('#tp', d), 'A type cannot be inside itself.'); return false; } p = p.parent ? typeOf(p.parent) : null; } } const id = t ? t.id : n.toLowerCase().replace(/[^a-z0-9]+/g, '-') + uid(); scSoon(() => scAct(isNew ? `${n} added` : `${n} saved`, () => { const rec = { id, n, parent: par, directed: $('#td', d).checked, reads: $('#tr', d).value.trim(), back: $('#tb', d).value.trim() }; if (t) Object.assign(typeOf(id), rec); else TYPES.push(rec); return null; })); } }] });
}
function standingDialog(s) {
  const isNew = !s; const v = s || { n: '', min: null, max: null };
  openDialog({ title: isNew ? 'New standing' : `Scale of ${esc(v.n)}`, body: `${isNew ? '<label class="label" for="sn">Name</label><input id="sn" class="input" autocomplete="off">' : ''}<div class="row2" style="margin-top:var(--s-3)"><div><label class="label" for="smin">Minimum <span class="t-meta">optional</span></label><input id="smin" class="input" inputmode="numeric" value="${v.min !== null ? v.min : ''}"></div><div><label class="label" for="smax">Maximum <span class="t-meta">optional</span></label><input id="smax" class="input" inputmode="numeric" value="${v.max !== null ? v.max : ''}"></div></div><p class="t-meta">A write outside the scale is refused. A scale that existing values would break is refused too, with how many.</p>`,
    actions: [{ label: 'Cancel' }, { label: isNew ? 'Add the standing' : 'Save the scale', kind: 'primary', fn: (d) => { const mn = $('#smin', d).value.trim(), mx = $('#smax', d).value.trim(); const lo = mn === '' ? null : Number(mn), hi = mx === '' ? null : Number(mx); if ((mn !== '' && isNaN(lo)) || (mx !== '' && isNaN(hi))) { fieldError($('#smin', d), 'A bound is a number.'); return false; } if (lo !== null && hi !== null && lo > hi) { fieldError($('#smax', d), 'The maximum is below the minimum.'); return false; } if (s) { const bad = RELS.filter((r) => r.vals[s.id] !== undefined && ((lo !== null && r.vals[s.id] < lo) || (hi !== null && r.vals[s.id] > hi))).length; if (bad) { toast({ kind: 'error', title: 'That scale would break existing values', text: `${pl(bad, 'value is', 'values are')} outside ${lo !== null ? lo : 'no minimum'} to ${hi !== null ? hi : 'no maximum'}. Change them first.`, action: { label: 'Close', fn: () => {} } }); return false; } } const name = isNew ? $('#sn', d).value.trim() : null; if (isNew && !name) { fieldError($('#sn', d), 'A standing needs a name.'); return false; } scSoon(() => scAct(isNew ? `${name} added` : `${v.n} scale saved`, () => { if (s) { stOf(s.id).min = lo; stOf(s.id).max = hi; } else STANDINGS.push({ id: name.toLowerCase().replace(/[^a-z0-9]+/g, '-') + uid(), n: name, min: lo, max: hi }); return null; })); } }] });
}
function newWebDialog() { openDialog({ title: 'New web', body: '<label class="label" for="wn">Name</label><input id="wn" class="input" autocomplete="off"><p class="t-meta">It starts empty. Add the entries it shows from the web itself.</p>', actions: [{ label: 'Cancel' }, { label: 'Make the web', kind: 'primary', fn: (d) => { const n = $('#wn', d).value.trim(); if (!n) { fieldError($('#wn', d), 'A web needs a name.'); return false; } const id = n.toLowerCase().replace(/[^a-z0-9]+/g, '-') + uid(); WEBS.push({ id, n, members: [], layout: 'circle', pos: {} }); SC.noWebs = false; scSoon(() => { location.hash = '#/web/' + id; }); } }], init: (d) => $('#wn', d).focus() }); }
function webMenu(btn, id) { const w = webOf(id); openMenu(btn, [{ label: 'Rename…', icon: 'edit', fn: () => openDialog({ title: 'Rename the web', body: `<label class="label" for="rn">Name</label><input id="rn" class="input" value="${esc(w.n)}">`, actions: [{ label: 'Cancel' }, { label: 'Rename', kind: 'primary', fn: (d) => { const n = $('#rn', d).value.trim(); if (!n) return false; scSoon(() => scAct(`Renamed to ${n}`, () => { webOf(id).n = n; return null; })); } }] }) }, { sep: true }, { label: 'Delete…', icon: 'delete', danger: true, fn: () => openDialog({ title: `Delete ${esc(w.n)}?`, label: 'alertdialog', body: '<p class="muted" style="margin:0">The web goes. The entries and their relationships stay.</p>', actions: [{ label: 'Cancel' }, { label: 'Delete', kind: 'danger', fn: () => scSoon(() => scAct(`${w.n} deleted`, () => { WEBS = WEBS.filter((x) => x.id !== id); return null; })) }] }) }], { label: `Actions for ${w.n}` }); }
function delRelDialog(id) { const r = relOf(id); openDialog({ title: 'Delete this relationship?', label: 'alertdialog', body: `<p class="muted" style="margin:0">${esc(sentence(r))}. Its standings and notes go with it. The two entries stay.</p>`, actions: [{ label: 'Cancel' }, { label: 'Delete', kind: 'danger', fn: () => scSoon(() => { SC.sel = null; scAct('Relationship deleted', () => { RELS = RELS.filter((x) => x.id !== id); RELS.forEach((x) => { x.through = x.through.filter((t) => t !== id); }); return null; }); if (S.route.startsWith('rel')) location.hash = '#/relationships'; }) }] }); }
function pickMenu(btn, items, label) { openMenu(btn, items, { label, align: 'left' }); }
function lensMenu(btn) {
  const items = [{ label: 'Events in story order', heading: true }, ...ORDER.map((id) => ({ label: evOf(id).n, check: SC.lens === id, fn: () => { SC.lens = id; scRefresh(true); announce(`Looking as of ${evOf(id).n}`); } })), { label: 'No recorded order', heading: true }, ...EVENTS.filter((e) => e.unordered || (e.hidden && isGM())).map((e) => ({ label: `${e.n}${e.hidden ? ' (hidden from players)' : ''}`, check: SC.lens === e.id, fn: () => { SC.lens = e.id; scRefresh(true); announce(`Looking as of ${e.n}, which has no recorded order: answers are unknown`); } })), { sep: true }, { label: 'No date lens', fn: () => { SC.lens = null; SC.lensAll = false; scRefresh(true); } }];
  pickMenu(btn, items, 'As of an Event');
}
function readMenu(btn) {
  const who = isGM() ? Object.keys(ENTS).filter((i) => ENTS[i].k === 'being') : [MYBEING];
  pickMenu(btn, [{ label: isGM() ? 'What this being may read' : 'Your beings', heading: true }, ...who.map((i) => ({ label: entName(i), check: SC.asread === i, fn: () => { SC.asread = i; scRefresh(true); announce(`As read by ${entName(i)}`); } })), { sep: true }, { label: 'As you', fn: () => { SC.asread = null; scRefresh(true); } }], 'As read by');
}
function typesMenu(btn) { const L = TYPES.filter((t) => t.reads); pickMenu(btn, [{ label: 'Types shown', heading: true }, ...L.map((t) => ({ label: t.n, check: !SC.hide.has(t.id), fn: () => { SC.hide.has(t.id) ? SC.hide.delete(t.id) : SC.hide.add(t.id); scRefresh(true); } })), { sep: true }, { label: 'Show all', fn: () => { SC.hide = new Set(); scRefresh(true); } }], 'Types shown'); }
function stepsMenu(btn) { const has = SC.sel && SC.sel.k === 'ent'; pickMenu(btn, [{ label: has ? `From ${entName(SC.sel.id)}` : 'Select an entry first', heading: true }, ...[[0, 'All'], [1, '1 step'], [2, '2 steps']].map(([n, t]) => ({ label: t, check: SC.steps === n, fn: () => { if (n && !has) { toast({ title: 'Select an entry first', text: 'Steps are counted from the selected entry.' }); return; } SC.steps = n; scRefresh(true); } }))], 'Steps'); }
/* ---- the matrix: keys, editing, drafts and the save */
const keepFrame = () => { const a = $('.so-a'); if (a) { a.scrollLeft = 0; a.scrollTop = 0; } const f = $('#frame'); if (f) f.scrollLeft = 0; };
function mxMembers() { return orderedMembers(webOf(SC.web)); }
function setDraft(key, val, rid) { SC.undoS.push(JSON.stringify(SC.draft)); SC.redoS = []; SC.draft[key] = { val, rid }; delete SC.refused[key]; }
function commitCell(key, raw) {
  const [a, b] = key.split('>'); const typeMode = SC.mxMode.startsWith('type:'); const sid = mainStanding();
  if (typeMode) { setDraft(key, '1'); SC.editing = null; scRefresh(true); return; }
  const e = raw === '' ? null : validateStanding(sid, raw); if (e) { SC.refused[key] = e; scRefresh(true); return; }
  setDraft(key, raw); SC.editing = null; scRefresh(true);
}
function mxKeydown(e) {
  const td = e.target.closest('[data-cell]'); const inp = e.target.closest('[data-mxin]');
  if (inp) { if (e.key === 'Enter') { e.preventDefault(); commitCell(inp.dataset.mxin, inp.value.trim()); } else if (e.key === 'Escape') { e.preventDefault(); const k = inp.dataset.mxin; SC.editing = null; delete SC.refused[k]; scRefresh(); $(`[data-cell="${k}"]`).focus(); } return; }
  if ((e.ctrlKey || e.metaKey) && td && (e.key === 'z' || e.key === 'y')) { e.preventDefault(); if (e.key === 'z' && SC.undoS.length) { SC.redoS.push(JSON.stringify(SC.draft)); SC.draft = JSON.parse(SC.undoS.pop()); } else if (e.key === 'y' && SC.redoS.length) { SC.undoS.push(JSON.stringify(SC.draft)); SC.draft = JSON.parse(SC.redoS.pop()); } scRefresh(true); return; }
  if (!td) return; const M = mxMembers(); let r = +td.dataset.r, c = +td.dataset.c; const go = (dr, dc) => { r = Math.max(0, Math.min(M.length - 1, r + dr)); c = Math.max(0, Math.min(M.length - 1, c + dc)); SC.cur = [M[r], M[c]]; scRefresh(); const n = $(`[data-cell="${mxKey(M[r], M[c])}"]`); if (n) { n.focus({ preventScroll: true }); n.scrollIntoView({ block: 'nearest', inline: 'nearest' }); keepFrame(); } };
  const k = e.key; if (k === 'ArrowDown') { e.preventDefault(); go(1, 0); } else if (k === 'ArrowUp') { e.preventDefault(); go(-1, 0); } else if (k === 'ArrowLeft') { e.preventDefault(); go(0, -1); } else if (k === 'ArrowRight') { e.preventDefault(); go(0, 1); } else if (k === 'Home') { e.preventDefault(); go(0, -c); } else if (k === 'End') { e.preventDefault(); go(0, M.length); } else if (k === 'PageDown') { e.preventDefault(); go(5, 0); } else if (k === 'PageUp') { e.preventDefault(); go(-5, 0); }
  else if (isGM() && !isPhone() && (k === 'Enter' || k === 'F2' || /^[-0-9]$/.test(k)) && !e.ctrlKey && !e.metaKey) { e.preventDefault(); startEdit(td.dataset.cell, /^[-0-9]$/.test(k) ? k : null); }
  else if (isGM() && !isPhone() && (k === 'Delete' || k === 'Backspace')) { e.preventDefault(); clearCell(td.dataset.cell); }
}
function startEdit(key, first) {
  const [a, b] = key.split('>'); if (a === b) return; const L = cellRels(a, b); const typeMode = SC.mxMode.startsWith('type:');
  if (L.length > 1 && !SC.draft[key]) return openDialog({ title: 'Two relationships fill this cell', body: `<p class="muted" style="margin:0 0 var(--s-2h)">Which one do you want to edit?</p>${L.map((r, i) => `<label class="ivrd"><input type="radio" name="wr" value="${r.id}" ${i === 0 ? 'checked' : ''}> <span>${esc(sentence(r))}</span><span class="t-meta">${standing(r, mainStanding()).v !== null ? standing(r, mainStanding()).v : 'no value'}</span></label>`).join('')}`, actions: [{ label: 'Cancel' }, { label: 'Edit this one', kind: 'primary', fn: (d) => { const rid = $('input[name=wr]:checked', d).value; SC.draft[key] = { val: standing(relOf(rid), mainStanding()).v === null ? '' : String(standing(relOf(rid), mainStanding()).v), rid }; scSoon(() => { SC.editing = key; delete SC.draft[key]; SC.wr = rid; scRefresh(); const i = $('#mxi'); if (i) i.select(); }); } }] });
  if (typeMode) { if (L.length) { toast({ title: 'A relationship is removed from its own page', text: 'Open it from the list to delete it.' }); return; } setDraft(key, '1'); scRefresh(true); return; }
  SC.editing = key; scRefresh(); const i = $('#mxi'); if (i) { if (first) { i.value = first; i.setSelectionRange(1, 1); } else i.select(); i.focus(); }
}
function clearCell(key) {
  const [a, b] = key.split('>'); const L = cellRels(a, b); if (!L.length && !SC.draft[key]) return;
  const go = () => { setDraft(key, ''); scRefresh(true); };
  if (SC.askedClear) return go(); openDialog({ title: 'Clear this value?', label: 'alertdialog', body: '<p class="muted" style="margin:0">The value is removed. The relationship stays. This is asked once.</p>', actions: [{ label: 'Cancel' }, { label: 'Clear', kind: 'primary', fn: () => { SC.askedClear = true; scSoon(go); } }] });
}
function saveDrafts() {
  const sid = mainStanding(); const typeMode = SC.mxMode.startsWith('type:'); const keys = Object.keys(SC.draft); if (!keys.length) return;
  const before = snapS(); const draftBefore = JSON.stringify(SC.draft); let ok = 0; SC.refused = {};
  keys.forEach((key) => {
    const [a, b] = key.split('>'); const d = SC.draft[key];
    if (key === STALE && SC.stale) { SC.refused[key] = 'This cell changed while you were editing it (412). Your draft is kept; reload the cell to see the current value.'; return; }
    if (typeMode) { makeRel(a, b, SC.mxMode.slice(5), {}); delete SC.draft[key]; ok++; return; }
    const L = cellRels(a, b); const r = d.rid ? relOf(d.rid) : L[0];
    if (r) { if (d.val === '') delete r.vals[sid]; else r.vals[sid] = Number(d.val); } else makeRel(a, b, SC.newType || 'ally', { [sid]: Number(d.val) });
    delete SC.draft[key]; ok++;
  });
  if (SC.stale && SC.refused[STALE]) SC.stale = false;
  scRefresh(true); const bad = Object.keys(SC.refused).length;
  if (ok) { announce(`${pl(ok, 'change', 'changes')} saved`); withUndo(`${pl(ok, 'change', 'changes')} saved`, () => { restoreS(before); SC.draft = JSON.parse(draftBefore); SC.refused = {}; scRefresh(); }, bad ? `${pl(bad, 'cell', 'cells')} refused and kept` : undefined); }
  if (bad) toast({ kind: 'error', title: `${pl(bad, 'cell was', 'cells were')} refused`, text: 'The reason is next to each. Nothing else was lost.', action: { label: 'Close', fn: () => {} } });
}
/* ---- clicks */
function scClick(e) {
  if (SC.dragged) { SC.dragged = false; return; }
  const nd = e.target.closest('[data-ent]'); if (nd && !e.target.closest('input') && $('#sosvg') && $('#sosvg').contains(nd)) { nodeClick(nd.dataset.ent); return; }
  const ed = e.target.closest('[data-rel].edge'); if (ed && isPhone()) { location.hash = '#/rel/' + ed.dataset.rel; return; } if (ed) { SC.sel = { k: 'rel', id: ed.dataset.rel }; scRefresh(); announce(sentence(relOf(ed.dataset.rel))); return; }
  const mc = e.target.closest('[data-cell]'); if (mc && !e.target.closest('input')) { SC.cur = mc.dataset.cell.split('>'); const ed2 = SC.editing; if (ed2 && ed2 !== mc.dataset.cell) SC.editing = null; scRefresh(); const n = $(`[data-cell="${mc.dataset.cell}"]`); if (n) { n.focus({ preventScroll: true }); keepFrame(); } return; }
  const t = e.target.closest('[data-so]'); if (!t) return; if (t.getAttribute('aria-disabled') === 'true') return; const k = t.dataset.so, v = t.dataset.v;
  const F = { view: () => { SC.view = v; scRefresh(true); announce(v); }, labels: () => { SC.labels = !SC.labels; scRefresh(true); }, hulls: () => { SC.hulls = !SC.hulls; scRefresh(true); }, types: () => typesMenu(t), steps: () => stepsMenu(t), lens: () => lensMenu(t), asread: () => readMenu(t),
    clear: () => { SC.lens = null; SC.asread = null; SC.lensAll = false; scRefresh(); announce('Lens cleared'); }, lensall: () => { SC.lensAll = !SC.lensAll; scRefresh(true); }, selrel: () => { if (isPhone()) { location.hash = '#/rel/' + v; return; } SC.sel = { k: 'rel', id: v }; scRefresh(true); }, closep: () => { SC.sel = null; scRefresh(); },
    members: membersDialog, connect: () => { SC.connect = SC.connect ? null : { a: null }; scRefresh(true); announce(SC.connect ? 'Connect: choose the first entry' : 'Connect cancelled'); }, connectfrom: () => { SC.connect = { a: v }; SC.sel = null; scRefresh(); announce(`Connecting ${entName(v)}: choose the other entry`); }, cancelconnect: () => { SC.connect = null; scRefresh(); },
    zin: () => { SC.z = Math.min(3, fx(SC.z * 1.25)); scRefresh(true); }, zout: () => { SC.z = Math.max(0.4, fx(SC.z / 1.25)); scRefresh(true); }, zfit: () => { SC.z = 1; SC.px = 0; SC.py = 0; scRefresh(true); },
    newweb: newWebDialog, webmenu: () => webMenu(t, v), newrel: () => newRelDialog(v || null, null), delrel: () => delRelDialog(v), audience: () => audienceDialog(relOf(v)), edittype: () => typeDialog(typeOf(v)), newtype: () => typeDialog(null), newstanding: () => standingDialog(null), editstanding: () => standingDialog(stOf(v)),
    starter: () => { SC.noTypes = false; scRefresh(); toast({ title: 'The ready-made types were added', text: 'They are ordinary content. Edit or remove any of them.' }); }, save: saveDrafts, discard: () => { SC.draft = {}; SC.refused = {}; SC.undoS = []; scRefresh(true); announce('Changes discarded'); } };
  if (F[k]) F[k]();
}
function nodeClick(id) {
  if (SC.connect) { if (!SC.connect.a) { SC.connect.a = id; scRefresh(true); announce(`Connecting ${entName(id)}: choose the other entry`); return; } const a = SC.connect.a; SC.connect = null; scRefresh(); if (a === id) { toast({ kind: 'error', title: 'A relationship needs two different ends', text: 'Choose another entry.', action: { label: 'Close', fn: () => {} } }); return; } newRelDialog(a, id); return; }
  if (isPhone()) { location.hash = '#/entry/' + id; return; }
  SC.sel = { k: 'ent', id }; scRefresh(true); announce(entName(id));
}
function scInput(e) {
  const t = e.target; if (t.id === 'rq') { SC.rq = t.value; scRefresh(true); announce(`${pl(visRels().filter((r) => sentence(r).toLowerCase().includes(SC.rq.toLowerCase())).length, 'relationship', 'relationships')}`); }
}
function scChange(e) {
  const t = e.target;
  if (t.dataset.sv) { const r = relOf(t.dataset.rel); const raw = t.value.trim(); const err = raw === '' ? null : validateStanding(t.dataset.sv, raw); if (err) { fieldError(t, err); return; } clearFieldError(t); scAct(`${stOf(t.dataset.sv).n} of ${sentence(r)}`, () => { if (raw === '') delete relOf(r.id).vals[t.dataset.sv]; else relOf(r.id).vals[t.dataset.sv] = Number(raw); return null; }); return; }
  if (t.dataset.pos) { const w = webOf(SC.web); const P = layoutOf(w); const n = Number(t.value); if (isNaN(n)) { fieldError(t, 'A position is a number.'); return; } const p = (w.pos[t.dataset.ent] || P[t.dataset.ent]).slice(); p[t.dataset.pos === 'x' ? 0 : 1] = n; w.pos[t.dataset.ent] = p; scRefresh(true); return; }
  const so = t.dataset.soSel; if (!so) return;
  if (so === 'since' || so === 'until') { const r = relOf(t.dataset.rel); const val = t.value || null; const s = so === 'since' ? val : r.since, u = so === 'until' ? val : r.until; if (s && u && ORDER.includes(s) && ORDER.includes(u) && ORDER.indexOf(u) < ORDER.indexOf(s)) { fieldError(t, 'It would end before it starts. Choose an Event that is not before the start.'); t.value = r[so] || ''; return; } scAct(`${so === 'since' ? 'Since' : 'Until'} ${val ? evOf(val).n : 'not set'}`, () => { relOf(r.id)[so] = val; return null; }); return; }
  if (so === 'layout') { const w = webOf(SC.web); w.layout = t.value; if (t.value !== 'manual') w.pos = {}; scRefresh(); announce(`Layout: ${t.value}`); }
  else if (so === 'mxmode') { SC.mxMode = t.value; scRefresh(true); } else if (so === 'mxord') { SC.order = t.value; scRefresh(true); } else if (so === 'stent') { SC.ent = t.value; scRefresh(true); } else if (so === 'mxnew') { SC.newType = t.value; }
  else if (so === 'ftype') { SC.rf.type = t.value; scRefresh(true); } else if (so === 'fend') { SC.rf.end = t.value; scRefresh(true); } else if (so === 'fmin') { SC.rf.min = t.value; scRefresh(true); }
}
/* ---- the graph: pan, zoom, drag in manual layout, keys */
function graphBind() {
  const svg = $('#sosvg'); if (!svg) return; const g = $('#scg'); const w = webOf(SC.web); let st = null;
  const apply = () => g.setAttribute('transform', `translate(${SC.px} ${SC.py}) scale(${SC.z})`);
  svg.onpointerdown = (e) => { if (e.button !== 0) return; const n = e.target.closest('.node'); st = { x: e.clientX, y: e.clientY, px: SC.px, py: SC.py, node: n && w.layout === 'manual' && isGM() && !isPhone() ? n.dataset.ent : null, moved: false }; svg.setPointerCapture(e.pointerId); };
  svg.onpointermove = (e) => { if (!st) return; const dx = e.clientX - st.x, dy = e.clientY - st.y; if (!st.moved && Math.hypot(dx, dy) < 5) return; st.moved = true; const k = GW / svg.getBoundingClientRect().width; if (st.node) { const P = layoutOf(w); const p = (w.pos[st.node] || P[st.node]); st.np = [Math.round((p[0] + dx * k / SC.z - (st.lx || 0)) * 100) / 100, Math.round((p[1] + dy * k / SC.z - (st.ly || 0)) * 100) / 100]; const nd = $(`[data-ent="${st.node}"]`); nd.setAttribute('transform', `translate(${dx * k / SC.z} ${dy * k / SC.z})`); } else { SC.px = fx(st.px + dx * k); SC.py = fx(st.py + dy * k); apply(); } };
  svg.onpointerup = (e) => { if (!st) return; if (st.moved) { SC.dragged = true; setTimeout(() => { SC.dragged = false; }, 50); if (st.node) { const P = layoutOf(w); const p = w.pos[st.node] || P[st.node]; const dx = e.clientX - st.x, dy = e.clientY - st.y; const k = GW / svg.getBoundingClientRect().width; w.pos[st.node] = [Math.round((p[0] + dx * k / SC.z) * 100) / 100, Math.round((p[1] + dy * k / SC.z) * 100) / 100]; scRefresh(true); } } st = null; };
  svg.onwheel = (e) => { e.preventDefault(); SC.z = Math.max(0.4, Math.min(3, fx(SC.z * (e.deltaY < 0 ? 1.1 : 1 / 1.1)))); apply(); };
  svg.onkeydown = (e) => {
    const n = e.target.closest('.node'); const ids = $$('.node', svg).map((x) => x.dataset.ent);
    if (e.key === '+' || e.key === '=') { e.preventDefault(); SC.z = Math.min(3, fx(SC.z * 1.25)); apply(); return; } if (e.key === '-') { e.preventDefault(); SC.z = Math.max(0.4, fx(SC.z / 1.25)); apply(); return; }
    if (e.shiftKey && e.key.startsWith('Arrow')) { e.preventDefault(); const d = 40; if (e.key === 'ArrowLeft') SC.px += d; if (e.key === 'ArrowRight') SC.px -= d; if (e.key === 'ArrowUp') SC.py += d; if (e.key === 'ArrowDown') SC.py -= d; apply(); return; }
    if (n && w.layout === 'manual' && e.altKey && e.key.startsWith('Arrow') && isGM()) { e.preventDefault(); const id = n.dataset.ent; const p = (w.pos[id] || layoutOf(w)[id]).slice(); if (e.key === 'ArrowLeft') p[0] -= 10; if (e.key === 'ArrowRight') p[0] += 10; if (e.key === 'ArrowUp') p[1] -= 10; if (e.key === 'ArrowDown') p[1] += 10; w.pos[id] = p; scRefresh(true); return; }
    if (n && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); nodeClick(n.dataset.ent); return; }
    if (e.key === 'Escape') { if (SC.connect) { SC.connect = null; scRefresh(); } else if (SC.sel) { SC.sel = null; scRefresh(); } return; }
    if (n && ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(e.key) && !e.altKey) { e.preventDefault(); const id = n.dataset.ent; const nb = [...new Set(visRels().filter((r) => r.a === id || r.b === id).map((r) => (r.a === id ? r.b : r.a)).filter((x) => ids.includes(x)))]; const pool = nb.length ? nb : ids; const i = pool.indexOf(id); const next = pool[(i + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : pool.length - 1) + (i < 0 ? 0 : 0)) % pool.length]; const el = $(`[data-ent="${next}"]`, svg); if (el) { $$('.node', svg).forEach((x) => x.setAttribute('tabindex', '-1')); el.setAttribute('tabindex', '0'); el.focus(); announce(entName(next)); } }
  };
  const lay = $('#lay'); if (lay) lay.value = w.layout;
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && S.route.startsWith('web') && !OV.el && !$('.menu[data-open]') && SC.sel) { SC.sel = null; scRefresh(); } });
function scAfter() {
  const m = $('#main'); m.onclick = scClick; m.oninput = scInput; m.onchange = scChange; m.onkeydown = mxKeydown; graphBind();
  m.onscroll = () => { if (m.scrollLeft) m.scrollLeft = 0; }; const fr = $('#frame'); if (fr) fr.onscroll = () => { if (fr.scrollLeft) fr.scrollLeft = 0; }; const sa = $('.so-a'); if (sa) sa.onscroll = () => { if (sa.scrollLeft || sa.scrollTop) { sa.scrollLeft = 0; sa.scrollTop = 0; } };
}
/* ---- routes */
const scr = (tab, render, meta, full) => ({ app: 'social', tab, render, full: !!full, after: scAfter, meta: meta || (() => '') });
window.ROUTES_EXT = {
  webs: scr('webs', pWebs, () => pl(SC.noWebs ? 0 : WEBS.length, 'web', 'webs')),
  web: scr('webs', pWeb, () => { const w = webOf(SC.web); return w ? `${pl(w.members.filter(entVisible).length, 'entry', 'entries')}${SC.lens ? ` · as of ${eventN(SC.lens)}` : ''}${SC.asread ? ` · as read by ${entName(SC.asread)}` : ''}` : ''; }, true),
  relationships: scr('relationships', pRels, () => pl(visRels().length, 'relationship', 'relationships')), rel: scr('relationships', pRel), entry: scr('webs', pEntry), types: scr('types', pTypes), problems: scr('problems', pProblems, () => pl(problems().length, 'problem', 'problems')),
};
window.START_ROUTE = 'webs'; window.INWORLD = () => null;
TAB_ICONS.webs = 'social'; TAB_ICONS.relationships = 'relations'; TAB_ICONS.types = 'kinds'; TAB_ICONS.problems = 'warning';
window.TAB_HIDE = (t) => (t === 'types' || t === 'problems') && S.role !== 'gm';
const PBs = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Social</b>${PBs('sctypes', 'x', 'No types in the library', SC.noTypes)}${PBs('scwebs', 'x', 'No webs', SC.noWebs)}${PBs('scopen', 'x', 'Open The harbour court', false)}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p]').forEach((b) => { if (b.dataset.p === 'sctypes') b.setAttribute('aria-pressed', SC.noTypes); if (b.dataset.p === 'scwebs') b.setAttribute('aria-pressed', SC.noWebs); }); };
window.PROTO_CLICK = (k, v) => { if (k === 'sctypes') { SC.noTypes = !SC.noTypes; go('types'); render(true); return true; } if (k === 'scwebs') { SC.noWebs = !SC.noWebs; go('webs'); render(true); return true; } if (k === 'scopen') { go('web/court'); return true; } return false; };

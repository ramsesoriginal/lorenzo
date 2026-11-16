/* Writing: the later slices of RFC 0047, drawn so they have a place before they are built.
   W8b the timer and W8c the session goal (ADR 0393, 0394), W8d reviewed suggestions, W9 manuscript updates, W10 export.
   Also Carrier coverage and special Chapters, and the warning on leaving with unsent work. */
/* ---- text with links and suggestion marks */
function sugCands(text) {
  const out = [];
  WD.entities.forEach((e) => e.match.forEach((w) => { const m = new RegExp('\\b' + w + '\\b', 'i').exec(text); if (m) { let r = out.find((x) => x.word === m[0] && x.idx === m.index); if (!r) { r = { word: m[0], idx: m.index, cands: [] }; out.push(r); } if (!r.cands.some((c) => c.name === e.name)) r.cands.push({ name: e.name, kind: e.kind }); } }));
  WD.dates.forEach((d) => { const m = d.re.exec(text); if (m) out.push({ word: m[0], idx: m.index, cands: [{ name: d.to(m), kind: 'Calendar date' }], date: true }); });
  return out.sort((a, b) => a.idx - b.idx);
}
function pText(it, read) {
  const text = it.text || ''; const spans = [];
  (it.links || []).forEach((l) => { const i = text.indexOf(l.w); if (i >= 0) spans.push({ i, n: l.w.length, cls: 'ent', title: l.to }); });
  if (!read && WS.side === 'suggestions') sugCands(text).forEach((r) => { if (!(it.links || []).some((l) => l.w === r.word) && !(WS.sugNo || {})[it.id + ':' + r.word]) spans.push({ i: r.idx, n: r.word.length, cls: 'sug' }); });
  spans.sort((a, b) => a.i - b.i); let out = '', pos = 0;
  spans.forEach((sp) => { if (sp.i < pos) return; out += esc(text.slice(pos, sp.i)) + `<${sp.cls === 'ent' ? 'a class="ent" href="#" title="' + esc(sp.title) + '"' : 'mark class="sug"'}>${esc(text.slice(sp.i, sp.i + sp.n))}</${sp.cls === 'ent' ? 'a' : 'mark'}>`; pos = sp.i + sp.n; });
  return out + esc(text.slice(pos));
}
/* ---- W8d: reviewed suggestions. Nothing changes until the person accepts one. */
function sugAll(c) { const rows = []; N(c.node).items.forEach((it) => { if (it.t !== 'p') return; sugCands(it.text).forEach((r) => { if ((it.links || []).some((l) => l.w === r.word) || (WS.sugNo || {})[it.id + ':' + r.word]) return; rows.push({ it, r }); }); }); return rows; }
function sugBody(c) {
  const rows = sugAll(c);
  const list = rows.map(({ it, r }, i) => { const a = Math.max(0, r.idx - 28), b = Math.min(it.text.length, r.idx + r.word.length + 28); const ctxt = `${a ? '…' : ''}${esc(it.text.slice(a, r.idx))}<mark class="sug">${esc(r.word)}</mark>${esc(it.text.slice(r.idx + r.word.length, b))}${b < it.text.length ? '…' : ''}`;
    return `<li class="sugrow"><div class="sugctx">${ctxt}</div>${r.cands.length > 1 ? `<div class="t-meta">${r.cands.length} entries match. Choose one, or neither.</div>` : r.date ? '<div class="t-meta">An explicit date. Linking it does not place an Event or say when anything happened.</div>' : ''}<div class="row2">${r.cands.map((cd, j) => `<button type="button" class="btn" data-w="sug-accept" data-i="${i}" data-j="${j}">${ic(r.date ? 'kind-calendar-pin' : 'link')}Link to ${esc(cd.name)}<span class="t-meta">${esc(cd.kind)}</span></button>`).join('')}<button type="button" class="btn btn--quiet" data-w="sug-no" data-i="${i}">Not this one</button></div></li>`; }).join('');
  return `<p class="muted">Names and dates in this ${N(c.node).kind} that match entries you can see. Your wording is never changed. Nothing is linked until you accept it.</p><ul class="sugs">${list || `<li class="empty-inline">No suggestions here.</li>`}</ul><p class="t-meta">No Event, participation or knowledge is inferred from a match. Suggestions are made in your browser from names you can already open.</p>`;
}
/* ---- W8b and W8c: the timer and the session goal, inside Word count */
function timerSessionHTML() {
  const st = TM.state; const note = WS.storage ? 'Only in this tab. It survives a reload and ends when the tab closes. No sound, no notification.' : 'This browser can’t keep it through a reload. It keeps running while this tab is open.';
  const timer = `<section class="tsec" aria-labelledby="tm-h"><h3 class="t-sub" id="tm-h">Writing timer</h3><div class="tm-big" id="tm-left" role="timer" aria-live="off">${st === 'idle' ? mmss(TM.mins * 60000) : mmss(tmLeft())}</div><div class="row2">${st === 'idle' ? `<label class="sr-only" for="tm-min">Minutes</label><input id="tm-min" class="input tm-in" inputmode="numeric" value="${TM.mins}" aria-describedby="tm-n"><span class="t-meta">minutes</span><button type="button" class="btn" data-w="tm" data-v="start">${ic('kind-clock-play')}Start</button>` : st === 'running' ? `<button type="button" class="btn" data-w="tm" data-v="pause">${ic('kind-clock-pause')}Pause</button><button type="button" class="btn btn--quiet" data-w="tm" data-v="reset">Reset</button>` : st === 'paused' ? `<button type="button" class="btn" data-w="tm" data-v="resume">${ic('kind-clock-play')}Resume</button><button type="button" class="btn btn--quiet" data-w="tm" data-v="reset">Reset</button>` : `<b>Time elapsed</b><button type="button" class="btn" data-w="tm" data-v="reset">Reset</button>`}</div><p class="t-meta" id="tm-n">${note}</p></section>`;
  const left = Math.max(0, SS.target - SS.net); const pct = SS.target ? Math.max(0, Math.min(100, SS.net / SS.target * 100)) : 0;
  const sess = `<section class="tsec" aria-labelledby="ss-h"><h3 class="t-sub" id="ss-h">Session goal</h3>${SS.active || SS.done ? `<div class="tm-big" aria-live="polite">${SS.net >= 0 ? '+' : '−'}${Math.abs(SS.net)} <span class="t-meta">net words</span></div><div class="meter" role="img" aria-label="${Math.round(pct)} percent of the session target"><span style="width:${pct}%"></span></div><p class="t-meta">${SS.net >= SS.target ? 'Target reached.' : `${fmt(left)} words to go of ${fmt(SS.target)}.`}${SS.done ? ' Finished.' : ''}</p><div class="row2">${SS.active ? '<button type="button" class="btn" data-w="sess" data-v="finish">Finish</button>' : '<button type="button" class="btn" data-w="sess" data-v="new">Begin a new session</button>'}</div>` : `<div class="row2"><label class="sr-only" for="ss-t">Words to write this session</label><input id="ss-t" class="input tm-in" inputmode="numeric" value="${SS.target || 500}"><span class="t-meta">words</span><button type="button" class="btn" data-w="sess" data-v="start">Start</button></div>`}<p class="t-meta">Counts words you add and take away in the editor after Start, so deleting subtracts. Moving writing, loading a saved version and recovered text earn nothing. It is not saved, shared or a record of activity.</p></section>`;
  return `<div class="tsecs">${timer}${sess}</div>`;
}
/* ---- Carrier form and coverage (W6), and special Chapters (W7b) */
function detailsExtra(c) {
  const n = N(c.node); let h = '';
  if (n.kind === 'chapter' && c.work.kind !== 'Carrier') h += `<div><span class="label">Kind of Chapter</span><div class="seg" role="radiogroup" aria-label="Kind of Chapter">${[['', 'Ordinary'], ['contents', 'Contents'], ['index', 'Index'], ['glossary', 'Glossary']].map(([v, l]) => `<button type="button" role="radio" aria-checked="${(n.special || '') === v}" data-w="special" data-v="${v}">${l}</button>`).join('')}</div><p class="t-meta">${n.special === 'contents' ? 'The list is made from the outline and sits before your writing here.' : n.special ? 'You write it. Nothing is generated yet.' : 'Contents lists the outline for you. Index and Glossary are authored text.'}</p></div>`;
  if (c.work.kind === 'Carrier' && c.node === c.root) {
    n.forms = n.forms || ['Vellum', 'Coptic binding', 'Hardcover'];
    h += `<div><span class="label">Carrier form</span><div class="row2">${n.forms.map((f, i) => `<span class="chip">${esc(f)}<button type="button" class="chip-x" data-w="form-del" data-i="${i}" aria-label="Remove ${esc(f)}">${ic('close')}</button></span>`).join('')}<button type="button" class="btn btn--quiet" data-w="form-add">${ic('add')}Add a form</button></div><p class="t-meta">A real codex can have several forms at once. They are ordinary prototypes; nothing is preset.</p></div>`;
    h += `<div><span class="label">Covered writing</span><ul class="revs">${n.items.map((it, i) => it.t === 'cover' ? `<li><div class="grow"><b>${esc(N(it.ref).title)}</b><div class="t-meta">${esc(N(it.ref).kind)} · from The harbour tales</div></div><button type="button" class="btn btn--quiet" data-w="cov-del" data-id="${it.id}">Remove</button></li>` : '').join('') || '<li class="t-meta">Nothing covered yet.</li>'}</ul><button type="button" class="btn" data-w="cov-add">${ic('add')}Cover more writing</button><p class="t-meta">Coverage names whole Editions, Chapters, Scenes or single blocks. It grants no access and removing it leaves the writing where it is.</p></div>`;
  }
  return h;
}
function specialHTML(c, id) {
  const n = N(id); if (n.special !== 'contents') return '';
  const rows = flat(c.root).filter((x) => x.id !== id && c.lab[x.id] !== undefined).map(({ id: k, depth }) => `<li style="padding-left:${depth * 18}px"><a href="${addr(c, k)}">${c.lab[k] ? `<span class="tn">${esc(c.lab[k])}</span> ` : ''}${esc(N(k).title)}</a></li>`).join('');
  return `<div class="tocblock"><div class="t-meta">${ic('list')}Made from the outline. It updates as you move things.</div><ol>${rows}</ol></div>`;
}
/* ---- W9: updates from the repository this Book was copied from */
const KCHIP = { changed: ['update-available', 'Changed upstream', 'st--stale'], conflict: ['warning', 'Conflict', 'st--conflict'], new: ['add', 'New upstream', 'st--waiting'], removed: ['kind-chapter-remove', 'Removed upstream', 'st--stale'] };
function updRow(u) {
  const chip = `<span class="st ${KCHIP[u.kind][2]}">${ic(KCHIP[u.kind][0])}<span>${KCHIP[u.kind][1]}</span></span>`;
  const col = (t, x, k) => `<div class="ucol"><div class="t-micro">${t}</div><div class="utext ${k || ''}">${x ? esc(x) : '<span class="t-meta">Nothing</span>'}</div></div>`;
  const acts = u.res ? `<span class="t-meta">${ic('select-item')} ${esc(u.res)}</span><button type="button" class="btn btn--quiet" data-w="upd" data-u="${u.id}" data-v="reopen">Reopen</button>` : { changed: [['theirs', 'Apply the change'], ['mine', 'Keep mine']], conflict: [['theirs', 'Take theirs'], ['mine', 'Keep mine'], ['both', 'Keep both']], new: [['theirs', 'Add it'], ['mine', 'Skip']], removed: [['mine', 'Keep it'], ['theirs', 'Remove it']] }[u.kind].map(([v, l]) => `<button type="button" class="btn" data-w="upd" data-u="${u.id}" data-v="${v}">${l}</button>`).join('');
  return `<li class="upd ${u.kind}"><div class="upd-h"><b>${esc(u.title)}</b>${chip}</div><div class="t-meta">${esc(u.note)}</div><div class="ucols">${col('Was (release 1.3)', u.was)}${col('Now (release 1.4)', u.now)}${col('Yours', u.yours)}</div><div class="row2">${acts}</div></li>`;
}
function updBody() {
  const open = WD.updates.filter((u) => !u.res); const clean = open.filter((u) => u.kind === 'changed' || u.kind === 'new');
  const conf = WS.updConfirm ? `<div class="banner" role="alertdialog" aria-label="Apply all clean"><div class="grow"><b>Apply ${clean.length} clean ${clean.length === 1 ? 'update' : 'updates'}?</b><div class="t-meta">It does not touch conflicts, Chapters removed upstream, or anything you edited since the copy. Readers see the result at once. “Quay rules” and the Chapter inside it arrive together.</div></div><button type="button" class="btn btn--primary" data-w="upd-all" data-v="yes">Apply ${clean.length}</button><button type="button" class="btn" data-w="upd-all" data-v="no">Cancel</button></div>` : '';
  return `<p class="muted">${esc(ctx().work.title)} was copied from <b>${esc(ctx().work.source)}</b> at release ${ctx().work.release}. Release ${ctx().work.upstream} changed ${WD.updates.length} places. Each one is compared three ways, and nothing is applied until you choose.</p>${conf}<ul class="upds">${WD.updates.map(updRow).join('')}</ul>`;
}
function updatesDialog() {
  openDialog({ title: `Updates from ${ctx().work.source}`, wide: true, body: `<div id="upd-body">${updBody()}</div>`, actions: [{ label: 'Close' }, { label: 'Apply all clean', kind: 'primary', fn: () => { if (!WD.updates.some((u) => !u.res && (u.kind === 'changed' || u.kind === 'new'))) return false; WS.updConfirm = true; $('#upd-body').innerHTML = updBody(); return false; } }], init: (d) => { d.addEventListener('click', (e) => { const b = e.target.closest('[data-w^="upd"]'); if (b) moreClick(e, b, b.dataset.w, ctx()); }); } });
}
function applyUpd(u, v) {
  if (v === 'reopen') { u.res = null; return; }
  const ed = 'ed4';
  if (u.kind === 'changed' && v === 'theirs') { N('fg-lamps').items[0].text = u.now; u.res = 'Applied'; }
  else if (u.kind === 'conflict' && v === 'theirs') { N('fg-wall').items[0].text = u.now; N('fg-wall').items.splice(1, 1); u.res = 'Took theirs'; }
  else if (u.kind === 'conflict' && v === 'both') { N('fg-wall').items[0].text = u.now; u.res = 'Kept both: your note stays under theirs'; }
  else if (u.kind === 'new' && v === 'theirs') { if (!N('fg-quay')) { WD.nodes['fg-quay'] = { id: 'fg-quay', kind: 'chapter', title: 'Quay rules', items: [{ id: uid(), t: 'p', text: u.now }, { id: uid(), t: 'child', ref: 'fg-night' }] }; WD.nodes['fg-night'] = { id: 'fg-night', kind: 'chapter', title: 'Night rules', items: [{ id: uid(), t: 'p', text: 'After the last bell, no boat leaves the slip without a lamp.' }] }; N(ed).items.splice(3, 0, { id: uid(), t: 'child', ref: 'fg-quay' }); } u.res = 'Added with “Night rules”'; }
  else if (u.kind === 'removed' && v === 'theirs') { const p = parentOf('fg-old'); if (p) removeItem(p.node, p.index); u.res = 'Removed'; }
  else u.res = u.kind === 'new' ? 'Skipped' : 'Kept mine';
}
/* ---- W10: export */
const EX = { fmt: 'pdf', scope: 'edition', toc: true, num: true, size: 'A4', stage: 0, pct: 0 };
function exBody() {
  const c = ctx();
  const opt = (k, v, t, d) => `<label class="opt"><input type="radio" name="ex-${k}" value="${v}" ${EX[k] === v ? 'checked' : ''} data-w="ex" data-k="${k}"><span><b>${t}</b><span class="t-meta" style="display:block">${d}</span></span></label>`;
  const form = `<div class="ex-cols"><div class="fields"><fieldset class="fs"><legend class="label">Format</legend>${opt('fmt', 'pdf', 'PDF', 'Headings, numbers, contents, pictures and footnotes. Basic layout.')}${opt('fmt', 'src', 'LorenzoScript source', 'Lossless. Keeps structure, wording and pictures so it can be opened again.')}</fieldset><fieldset class="fs"><legend class="label">What</legend>${opt('scope', 'edition', c.work.kind === 'Book' ? 'This Edition' : 'All of ' + esc(c.work.title), `${pl(totalWords(c.root), 'word', 'words')}`)}${opt('scope', 'node', 'This Chapter and its subchapters', `${pl(totalWords(c.node), 'word', 'words')}`)}</fieldset>${EX.fmt === 'pdf' ? `<fieldset class="fs"><legend class="label">Pages</legend><label class="chk"><input type="checkbox" data-w="ex" data-k="toc" ${EX.toc ? 'checked' : ''}> Contents</label><label class="chk"><input type="checkbox" data-w="ex" data-k="num" ${EX.num ? 'checked' : ''}> Chapter numbers</label><div style="margin-top:var(--s-2)"><label class="label" for="ex-size">Page size</label><span class="selectwrap"><select id="ex-size" class="select" data-w="ex" data-k="size"><option ${EX.size === 'A4' ? 'selected' : ''}>A4</option><option ${EX.size === 'Letter' ? 'selected' : ''}>Letter</option></select>${ic('expand')}</span></div></fieldset>` : ''}<p class="t-meta">Only what you may read is included. Private notes, review notes, reviewers and goals are never exported.</p></div><div class="ex-prev" aria-label="Preview">${paper()}</div></div>`;
  if (EX.stage === 1) return `<div class="ex-run" role="status"><div class="t-sub">Reading a consistent copy of the manuscript…</div><div class="meter"><span style="width:${EX.pct}%"></span></div><p class="t-meta">${EX.pct < 50 ? 'Reading the Chapters in order' : 'Laying out the pages'}. You can keep writing; the export uses the copy it started from.</p></div>`;
  if (EX.stage === 2) return `<div class="ex-done">${ic('select-item')}<div class="grow"><b>${EX.fmt === 'pdf' ? 'harbour-tales-edition-1.pdf' : 'harbour-tales-edition-1.lorenzoscript.zip'}</b><div class="t-meta">${EX.fmt === 'pdf' ? '9 pages · A4' : '3 files and 1 picture'} · made from the version saved at 19:40</div></div><button type="button" class="btn btn--primary" data-w="ex-dl">Download</button></div>${form}`;
  return form;
}
function paper() {
  const c = ctx(); const rows = flat(c.root).slice(0, 6).map(({ id, depth }, i) => `<li style="padding-left:${depth * 10}px"><span>${EX.num && c.lab[id] ? esc(c.lab[id]) + ' ' : ''}${esc(N(id).title)}</span><i></i><span>${3 + i * 2}</span></li>`).join('');
  if (EX.fmt === 'src') return `<pre class="srcprev">@book "The harbour tales"\n@edition 1\n\n# {#ch2} The blackout\n\nThe lights went out a little\nafter nineteen forty…\n\n## {#ch22} The quay\n\nThe quay was empty when…</pre>`;
  return `<div class="papers"><div class="paper ${EX.size === 'Letter' ? 'letter' : ''}"><div class="p-title">The harbour tales</div>${EX.toc ? `<div class="p-h">Contents</div><ol class="p-toc">${rows}</ol>` : ''}</div><div class="paper ${EX.size === 'Letter' ? 'letter' : ''}"><div class="p-h">${EX.num ? '2.2 ' : ''}The quay</div><p>The quay was empty when Imani reached it. Somewhere behind the warehouses a bell rang the hour, and the water slapped against the stone.</p><p>She counted the lamps along the east wall.<sup>1</sup> Four were lit.</p><div class="p-fn">1  On day 112 of Year 4.</div></div></div>`;
}
let exTimer = null;
function exportDialog() {
  EX.stage = 0; EX.pct = 0; clearInterval(exTimer);
  const d = openDialog({ title: 'Export', wide: true, body: `<div id="ex-body">${exBody()}</div>`, actions: [{ label: 'Close' }, { label: 'Make export', kind: 'primary', fn: () => { if (EX.stage === 1) return false; EX.stage = 1; EX.pct = 0; $('#ex-body').innerHTML = exBody(); exTimer = setInterval(() => { EX.pct += 12; if (EX.pct >= 100) { clearInterval(exTimer); EX.stage = 2; } const b = $('#ex-body'); if (b) b.innerHTML = exBody(); else clearInterval(exTimer); }, 260); return false; } }], init: (dd) => { dd.addEventListener('change', (e) => { const b = e.target.closest('[data-w="ex"]'); if (b) moreClick(e, b, 'ex', ctx()); }); dd.addEventListener('click', (e) => { const b = e.target.closest('[data-w="ex-dl"]'); if (b) toast({ title: 'Download started', text: 'This is a prototype: nothing is saved.' }); }); } });
}
function newEditionDialog() {
  openDialog({ title: 'New Edition from a copy?', body: '<p>It copies the writing, pictures and outline of this Edition. After that the two are independent: changing one never changes the other.</p><p class="muted">The new Edition starts private. Notes, history and reviewers are not copied.</p>', actions: [{ label: 'Cancel' }, { label: 'Make a copy', kind: 'primary', fn: () => toast({ title: 'Edition 3 started', text: 'It is private until you share it.' }) }] });
}
/* ---- actions for the above */
function moreClick(e, b, w, c) {
  if (w === 'tm') { tmAct(b.dataset.v, parseInt(($('#tm-min') || {}).value, 10)); wrPanelRefresh(); return true; }
  if (w === 'sess') { sessAct(b.dataset.v, parseInt(($('#ss-t') || {}).value, 10)); wrPanelRefresh(); return true; }
  if (w === 'sug-accept' || w === 'sug-no') { const rows = sugAll(c); const row = rows[+b.dataset.i]; if (!row) return true; if (w === 'sug-no') { (WS.sugNo = WS.sugNo || {})[row.it.id + ':' + row.r.word] = true; wrRefresh(true); return true; } const cd = row.r.cands[+b.dataset.j]; mutate(`Linked “${row.r.word}” to ${cd.name}`, () => { (row.it.links = row.it.links || []).push({ w: row.r.word, to: cd.name }); }, 'Your wording is unchanged.'); return true; }
  if (w === 'updates') { updatesDialog(); return true; }
  if (w === 'upd') { const u = WD.updates.find((x) => x.id === b.dataset.u); mutate(b.dataset.v === 'reopen' ? 'Reopened' : `${u.title}: ${b.dataset.v === 'theirs' ? (u.kind === 'removed' ? 'removed' : 'applied') : b.dataset.v === 'both' ? 'kept both' : 'kept mine'}`, () => { applyUpd(u, b.dataset.v); WS.updDone = !WD.updates.some((x) => !x.res); }); const ub = $('#upd-body'); if (ub) ub.innerHTML = updBody(); return true; }
  if (w === 'upd-all') { if (b.dataset.v === 'yes') { const clean = WD.updates.filter((u) => !u.res && (u.kind === 'changed' || u.kind === 'new')); mutate(`Applied ${clean.length} clean updates`, () => { clean.forEach((u) => applyUpd(u, 'theirs')); WS.updDone = !WD.updates.some((x) => !x.res); }, 'Conflicts and removed Chapters were left for you.'); } WS.updConfirm = false; const ub = $('#upd-body'); if (ub) ub.innerHTML = updBody(); return true; }
  if (w === 'export') { exportDialog(); return true; }
  if (w === 'ex') { const k = b.dataset.k; EX[k] = b.type === 'checkbox' ? b.checked : b.value; const eb = $('#ex-body'); if (eb) { const keep = document.activeElement && document.activeElement.id; eb.innerHTML = exBody(); if (keep) { const n = $('#' + keep); n && n.focus(); } } return true; }
  if (w === 'special') { const n = N(c.node); n.special = b.dataset.v || undefined; n.unnumbered = !!n.special; wrRefresh(true); return true; }
  if (w === 'form-add') { openMenu(b, [{ label: 'Add a form', heading: true }, ...['Scroll', 'Folio', 'Illuminated', 'Pocket book'].map((f) => ({ label: f, fn: () => mutate('Added a form', () => { N(c.root).forms.push(f); }) }))], { label: 'Forms' }); return true; }
  if (w === 'form-del') { mutate('Removed a form', () => { N(c.root).forms.splice(+b.dataset.i, 1); }); return true; }
  if (w === 'cov-del') { mutate('Removed coverage', () => { const it = N(c.root).items; it.splice(it.findIndex((x) => x.id === b.dataset.id), 1); }, 'The writing itself is untouched.'); return true; }
  if (w === 'cov-add') { const pool = [{ id: 'ed1', t: 'The harbour tales, Edition 1' }, ...flat('ed1').map((x) => ({ id: x.id, t: N(x.id).title })), { id: 'sc-ledger', t: 'The ledger (Scene)' }, { id: 'sc-bell', t: 'The night bell (Scene)' }].filter((x) => !N(c.root).items.some((i) => i.ref === x.id)); openDialog({ title: 'Cover more writing', body: `<p class="muted">Pick what this Carrier covers. It can cross Books and sit among its own writing.</p><ul class="pick" role="listbox" aria-label="Writing">${pool.map((x, i) => `<li><button type="button" role="option" class="menu-item" aria-selected="${i === 0}" data-pick="${x.id}">${ic('kind-chapter')}<span class="grow">${esc(x.t)}</span></button></li>`).join('')}</ul>`, actions: [{ label: 'Cancel' }, { label: 'Cover it', kind: 'primary', fn: (d) => { const id = $('[aria-selected="true"][data-pick]', d).dataset.pick; mutate('Covered writing', () => { N(c.root).items.push({ id: uid(), t: 'cover', ref: id }); }); } }], init: (d) => d.addEventListener('click', (e) => { const x = e.target.closest('[data-pick]'); if (x) $$('[data-pick]', d).forEach((y) => y.setAttribute('aria-selected', y === x)); }) }); return true; }
  return false;
}
function wrPanelRefresh() { const a = $('.wside'); if (a) { a.innerHTML = panelHTML(ctx()); return; } const sh = $('#sheet-side'); if (sh) sh.innerHTML = panelHTML(ctx()).replace(/<div class="side-head">.*?<\/div>(?=<div class="seg")/, ''); }
/* ---- leaving with unsent work: a warning (decided), and the browser's own on closing the tab */
window.NAV_GUARD = () => {
  if (WS.allow) { WS.allow = false; return true; }
  const to = location.hash; if (!/^w\//.test(S.route) || to === '#/' + S.route) return true;
  const why = WS.force === 'conflict' ? 'Autosave stopped on a conflict. Your text is kept in this browser, but it has not reached the server.' : WS.force === 'storage' ? 'This browser can’t keep a copy on this device, so what has not synced is lost if you leave.' : WS.force === 'local' ? 'Your text is saved on this device only. It will be here when you come back, but it has not reached the server.' : null;
  if (!why) return true;
  history.replaceState(null, '', '#/' + S.route);
  openDialog({ title: 'Leave with unsent work?', body: `<p>${why}</p>`, actions: [{ label: 'Stay and keep writing', kind: 'primary' }, { label: 'Leave anyway', fn: () => { WS.allow = true; location.hash = to; } }] });
  return false;
};
addEventListener('beforeunload', (e) => { if (WS.force !== 'saved') { e.preventDefault(); e.returnValue = ''; } });

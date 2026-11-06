/* Writing: the shelf, the writing page (Write and Read are modes of one page), the side views, menus and handlers. */
const pl = (n, a, b) => `${fmt(n)} ${n === 1 ? a : b}`;
const slot2 = (id, text) => `<div class="art-slot" role="img" aria-label="Illustration slot: ${esc(id)}">Illustration<br>${esc(id)}<br>${esc(text)}</div>`;
const grip = (attrs, label) => `<button type="button" class="grip" ${attrs} aria-label="${esc(label)}. Drag, or press Alt and an arrow key. Enter opens Move to.">${ic('drag')}</button>`;
function ctx() {
  const [, wid, nid, mode] = parts(); const work = WK(wid) || WD.works[0]; const root = work.root;
  let node = nid && N(nid) ? nid : (work.kind === 'Book' ? (work.last || kids(root)[0] || root) : root);
  const role = work.role; let md = mode === 'read' || role === 'Reviewer' ? 'read' : 'write';
  return { work, root, node, mode: md, role, lab: labels(root) };
}
const addr = (c, node = c.node, mode = c.mode) => `#/w/${c.work.id}/${node}/${mode}`;
const labOf = (c, id) => (c.lab[id] ? c.lab[id] + ' ' : '');
const rootLabel = (c) => (c.work.kind === 'Book' ? N(c.root).title : '');
/* ------------------------------------------------------------------ the shelf */
function lastWords(w) { return w.kind === 'Book' ? totalWords(w.root) : totalWords(w.root); }
function pShelf() {
  const list = WD.works.filter((w) => !w.hidden && w.role === 'Author');
  const rev = WD.works.filter((w) => w.role === 'Reviewer');
  const f = WS.filter || 'All'; const shown = list.filter((w) => f === 'All' || w.kind + 's' === f || (f === 'Chapters' && w.kind === 'Chapter'));
  const start = `<button type="button" class="btn btn--primary" data-w="start-menu" aria-haspopup="menu">${ic('add')}Start writing${ic('expand')}</button>`;
  if (WS.acct === 'new') return `<div class="page page--wide page-enter"><div class="head-row"><div class="grow"><h1 class="t-title page-title">Writing</h1></div></div><div class="join">${slot2('empty-manuscript', 'Catileo with a blank page and a pen')}<h2 class="t-sub">Nothing written yet</h2><p class="muted">Start with a page, a Chapter or a Book. Add structure when it helps. You can change your mind later.</p>${start}</div></div>`;
  const row = (w) => `<a class="item-row" href="#/w/${w.id}/${w.last || ''}/write">${ic(KIND_ICON[w.kind])}<span class="grow"><span class="nm">${esc(w.title)}</span><span class="t-meta" style="display:block">${w.kind}${w.kind === 'Book' ? ' · ' + pl((w.editions || [1]).length, 'Edition', 'Editions') : ''} · ${pl(lastWords(w), 'word', 'words')} · ${esc(w.edited)}${w.note ? ' · ' + esc(w.note) : ''}</span></span>${w.kind === 'Book' ? '<span class="st">' + ic('kind-edition') + '<span>Edition 1</span></span>' : ''}</a>`;
  const cont = [['harbour', 'ch22', '2.2 The quay', 'The harbour tales · edited today'], ['sc-ledger', '', 'The ledger', 'Scene · edited yesterday'], ['ch-alt', '', 'Opening, other ways', 'Chapter · edited last week']];
  return `<div class="page page--wide page-enter"><div class="head-row"><div class="grow"><h1 class="t-title page-title">Writing</h1><p class="page-sub" style="margin-bottom:0">What you are writing in ${esc(lib())}.</p></div>${start}</div>
  <h2 class="sec-title">Continue</h2><div class="grid cont stagger">${cont.map(([id, n, t, m]) => `<a class="card tile reveal" href="#/w/${id}/${n}/write" style="display:block"><b>${t}</b><span class="t-meta" style="display:block">${m}</span></a>`).join('')}</div>
  <div class="sec-h" style="margin-top:var(--s-5)"><h2 class="sec-title" style="margin:0">Your work</h2><div class="seg" role="radiogroup" aria-label="Show">${['All', 'Books', 'Chapters', 'Scenes', 'Carriers'].map((x) => `<button type="button" role="radio" aria-checked="${f === x}" data-w="filter" data-v="${x}">${x}</button>`).join('')}</div></div>
  <div class="listcard">${shown.map(row).join('') || '<div class="empty-inline">Nothing here yet.</div>'}</div>
  ${rev.length ? `<h2 class="sec-title">Shared with you to review</h2><div class="listcard">${rev.map((w) => `<a class="item-row" href="#/w/${w.id}//read">${ic('kind-book')}<span class="grow"><span class="nm">${esc(w.title)}</span><span class="t-meta" style="display:block">Edition 1 · ${esc(w.edited)} · you can read it and write notes only you and its Authors see</span></span><span class="st">${ic('kind-book')}<span>Review</span></span></a>`).join('')}</div>` : ''}</div>`;
}
/* ------------------------------------------------------------------ the writing page */
const flatTree = (c) => flat(c.root);
function outlineHTML(c) {
  const rows = flatTree(c).map(({ id, depth }) => { const n = N(id); const on = id === c.node;
    return `<div class="trow ${on ? 'on' : ''}" data-node="${id}" style="--d:${depth}" role="treeitem" aria-level="${depth + 1}" ${on ? 'aria-current="true"' : ''}>${c.role === 'Author' ? grip(`data-drag="row" data-node="${id}"`, 'Move ' + n.title) : ''}<span class="tick" aria-hidden="true"></span><a class="tt" href="${addr(c, id)}"><span class="tn">${esc(c.lab[id] || '')}</span> ${esc(n.title || 'Untitled')}</a><span class="t-meta tw">${fmt(totalWords(id))}</span>${c.role === 'Author' ? `<button type="button" class="icon-btn rowmore" data-w="row-menu" data-node="${id}" aria-label="More for ${esc(n.title)}" aria-haspopup="menu">${ic('more')}</button>` : ''}</div>`; }).join('');
  const covers = N(c.root).items.filter((i) => i.t === 'cover').map((i) => `<a class="trow cover" role="treeitem" href="#/w/harbour/${i.ref}/write" style="--d:0">${ic('link')}<span class="tt">Covers: ${esc(N(i.ref).title)}</span></a>`).join('');
  const head = c.work.kind === 'Book' ? `<button type="button" class="kindrow btn btn--quiet" data-w="edition-menu" aria-haspopup="menu">${ic('kind-edition')}<b>${esc(N(c.root).title)}</b>${ic('expand')}</button>` : `<span class="kindrow">${ic(KIND_ICON[c.work.kind])}<b>${esc(c.work.title)}</b></span>`;
  return `<nav class="wout ${WS.pin ? 'pinned' : 'rail'} ${WS.open ? 'open' : ''}" id="wout" aria-label="Outline"><div class="out-head">${head}<button type="button" class="icon-btn" data-w="pin" aria-pressed="${WS.pin}" aria-label="${WS.pin ? 'Unpin the outline' : 'Keep the outline open'}">${ic('pin')}</button></div><div ${rows || covers ? 'role="tree"' : ''} class="tree">${rows || '<div class="t-meta" style="padding:var(--s-2h)">No Chapters yet. Write, then make a Chapter from what you wrote.</div>'}${covers}</div>${c.role === 'Author' && c.work.kind !== 'Scene' ? `<button type="button" class="trow add" aria-label="Add a Chapter" data-w="add-chapter" data-parent="${c.root}">${ic('add')}<span class="tt">Add a Chapter</span></button>` : ''}<div class="out-foot t-meta">${pl(totalWords(c.root), 'word', 'words')} in all</div></nav>`;
}
function itemHTML(c, node, it) {
  const rd = c.role === 'Author';
  const g = (l) => (rd ? grip(`data-drag="item" data-node="${node}" data-item="${it.id}"`, l) : '');
  const a = `data-item="${it.id}" data-node="${node}"`;
  if (it.t === 'p') return `<div class="blk" ${a}>${g('Move this block')}<p class="reading ${it.h ? 'is-h' : ''} ${it.q ? 'is-q' : ''}" contenteditable="${rd}" data-edit="${it.id}" role="textbox" aria-multiline="true" aria-label="Text block" ${it.text ? '' : 'data-empty="Start writing"'}>${pText(it)}</p></div>`;
  if (it.t === 'list') return `<div class="blk" ${a}>${g('Move this list')}<ul class="rlist">${it.rows.map((r) => `<li>${esc(r)}</li>`).join('')}</ul></div>`;
  if (it.t === 'pic') return `<div class="blk" ${a}>${g('Move this picture')}<figure class="pic"><div class="pic-img" role="img" aria-label="Picture: ${esc(it.cap)}"></div><figcaption class="t-meta">${esc(it.cap)}</figcaption></figure></div>`;
  if (it.t === 'tell') { const sc = N(it.scene); return `<div class="blk" ${a}>${g('Move this telling')}<div class="scene-card">${ic('kind-scene')}<div class="grow"><b>${esc(sc.title)}</b><span class="t-meta" style="display:block">Scene · ${it.own ? 'independent copy' : 'shared telling'} · ${pl(it.own ? wc(it.text) : wc(sc.items.map((x) => x.text || '').join(' ')), 'word', 'words')}</span>${it.own ? `<p class="reading-sm" contenteditable="${rd}" data-edit="${it.id}" role="textbox" aria-label="Independent text">${esc(it.text)}</p>` : `<span class="reading-sm">${esc(sc.items[0].text.slice(0, 90))}…</span>`}</div><span class="st">${ic(it.own ? 'select-item' : 'link')}<span>${it.own ? 'Independent' : 'Shared'}</span></span><div class="scene-actions">${rd && !it.own ? `<button type="button" class="btn" data-w="independent" ${a}>Make independent</button>` : ''}<a class="btn btn--quiet" href="#/w/${sc.id}//write">Open the Scene</a></div></div></div>`; }
  if (it.t === 'child') { const n = N(it.ref); return `<div class="blk childcard" ${a} data-child="${it.ref}">${rd ? grip(`data-drag="row" data-node="${it.ref}"`, 'Move ' + n.title) : ''}${ic(KIND_ICON[n.kind])}<a class="grow" href="${addr(c, it.ref)}"><b>${esc(c.lab[it.ref] || '')} ${esc(n.title)}</b><span class="t-meta" style="display:block">${pl(totalWords(it.ref), 'word', 'words')} · ${pl(kids(it.ref).length, 'subchapter', 'subchapters')}</span></a><a class="btn btn--quiet" href="${addr(c, it.ref)}">Open</a></div>`; }
  if (it.t === 'cover') return `<div class="blk childcard" ${a}>${ic('link')}<a class="grow" href="#/w/harbour/${it.ref}/write"><b>Covers: ${esc(N(it.ref).title)}</b><span class="t-meta" style="display:block">From The harbour tales. Edit it there; coverage grants no access.</span></a></div>`;
  return '';
}
function banners(c) {
  const out = [];
  if (WS.force === 'conflict') out.push(`<div class="banner banner--danger" role="alert">${ic('warning')}<div class="grow"><b>This changed in another tab at 19:52. Autosave has stopped.</b><div class="t-meta">Your text is kept. Choose which version to continue from; the other stays in Revisions.</div></div><button type="button" class="btn" data-w="keep" data-v="mine">Keep mine</button><button type="button" class="btn" data-w="keep" data-v="theirs">Use theirs</button><button type="button" class="btn" data-w="keep" data-v="both">Keep both</button></div>`);
  if (WS.force === 'storage') out.push(`<div class="banner banner--warn" role="alert">${ic('warning')}<div class="grow"><b>Your browser can’t keep a copy on this device.</b><div class="t-meta">Keep this tab open until the status bar says Synced. Nothing is lost while it is open.</div></div><button type="button" class="btn" data-w="keep" data-v="ok">I’ll keep it open</button></div>`);
  if (c.work.source && !WS.updDone && c.role === 'Author') out.push(`<div class="banner" role="status">${ic('update-available')}<div class="grow"><b>${pl(WD.updates.filter((u) => !u.res).length, 'update is', 'updates are')} ready from ${esc(c.work.source)}.</b><div class="t-meta">Copied from release ${c.work.release}; release ${c.work.upstream} is out. Nothing changes until you apply it.</div></div><button type="button" class="btn btn--primary" data-w="updates">Review updates</button></div>`);
  if (WS.recovered && c.mode === 'write') out.push(`<div class="banner" role="status">${ic('history')}<div class="grow"><b>Unsent text from 19:38 is kept in this browser.</b><div class="t-meta">Kept for your account on this device. This is recovery, not offline browsing.</div></div><button type="button" class="btn btn--primary" data-w="recover" data-v="restore">Restore it</button><button type="button" class="btn" data-w="recover" data-v="discard">Discard</button></div>`);
  return out.join('');
}
function headHTML(c) {
  const n = N(c.node); const path = crumbs(c.node, c.root);
  const cr = [`<a href="#/shelf">Writing</a>`, c.work.kind === 'Book' ? `<a href="${addr(c, c.root)}">${esc(c.work.title)}</a> · ${esc(N(c.root).title)}` : esc(c.work.kind), ...path.slice(0, -1).map((p) => `<a href="${addr(c, p)}">${esc(N(p).title)}</a>`)].join(' · ');
  const tl = c.node === c.root ? N(c.root).title : (labOf(c, c.node) + (n.title || 'Untitled'));
  const modes = `<div class="seg" role="radiogroup" aria-label="Mode">${c.role === 'Author' ? `<button type="button" role="radio" aria-checked="${c.mode === 'write'}" data-w="mode" data-v="write">${ic('edit')}Write</button>` : ''}<button type="button" role="radio" aria-checked="${c.mode === 'read'}" data-w="mode" data-v="read">${ic('kind-book')}Read</button></div>`;
  const b = (w, i, l, extra = '') => `<button type="button" class="icon-btn" data-w="${w}" ${extra} aria-label="${l}">${ic(i)}</button>`;
  return `<div class="wtop"><button type="button" class="icon-btn only-small" data-w="outline" aria-label="Outline" aria-expanded="${WS.open}">${ic('layout-write')}</button><div class="grow"><div class="t-meta crumbs">${cr}</div><h1 class="wtitle">${c.node !== c.root && c.lab[c.node] ? `<span class="wnum">${esc(c.lab[c.node])}</span>` : ''}<span ${c.role === 'Author' && c.mode === 'write' ? `contenteditable="true" data-title="${c.node}" role="textbox" aria-label="Title" data-empty="Untitled"` : ''}>${c.node === c.root ? esc(N(c.root).title) : esc(n.title)}</span></h1></div>${modes}${b('side', 'info', 'Details', 'data-v="details"')}${c.role === 'Author' ? b('side', 'history', 'Revisions', 'data-v="revisions"') : ''}${b('side', 'word-count', 'Word count', 'data-v="count"')}${b('export', 'export', 'Export')}${c.role === 'Author' ? b('focus', 'focus-mode', 'Focus mode') : ''}</div>`;
}
function toolbarHTML() { const b = (w, i, l) => `<button type="button" class="icon-btn" data-w="tb" data-v="${w}" aria-label="${l}">${ic(i)}</button>`; return `<div class="wtools" role="toolbar" aria-label="Formatting">${b('h', 'heading', 'Heading')}${b('b', 'bold', 'Bold')}${b('i', 'italic', 'Italic')}${b('q', 'quote', 'Quote')}${b('l', 'list', 'List')}${b('pic', 'picture', 'Add a picture')}${b('link', 'entity-link', 'Link an entry')}<span class="grow"></span><button type="button" class="btn btn--quiet wgoal" data-w="side" data-v="count">${ic('goal')}<span id="goal-t">${goalText(WK(ctx().work.id))}</span></button></div>`; }
function goalText(w) { const c = ctx(); const cur = ownWords(c.node); if (!WS.goalOn || !w || !w.goal) return `${fmt(cur)} words`; const tot = totalWords(c.root); return `${fmt(tot)} of ${fmt(w.goal)} words`; }
function pWork() {
  const c = ctx(); if (c.mode === 'read') return pRead(c);
  const items = N(c.node).items; const body = specialHTML(c, c.node) + (items.length ? items.map((i) => itemHTML(c, c.node, i)).join('') : `<div class="blk" data-node="${c.node}"><p class="reading" contenteditable="true" data-edit="new" data-empty="Start writing" role="textbox" aria-label="Text block"></p></div>`);
  return `<div class="wr ${WS.pin ? 'is-pinned' : 'is-rail'} ${WS.focus ? 'focus' : ''} ${WS.side ? 'has-side' : ''}" id="wr" data-work="${c.work.id}" data-node="${c.node}">${WS.focus ? '' : outlineHTML(c)}<div class="wmain">${banners(c)}${headHTML(c)}${toolbarHTML()}<div class="wscroll" id="wscroll"><div class="wdoc" id="wdoc">${body}<button type="button" class="addblock" data-w="add-block" data-node="${c.node}">${ic('add')}Add a block</button></div></div>${WS.focus ? `<button type="button" class="btn focus-exit" data-w="focus">${ic('close')}Leave focus mode</button>` : ''}</div>${WS.side && !isSmall() ? `<aside class="wside" aria-label="${esc(sideTitle())}">${panelHTML(c)}</aside>` : ''}<div class="wscrim" data-w="outline-close"></div></div>`;
}
/* ------------------------------------------------------------------ Read */
function readNode(c, id, depth) {
  const n = N(id); const h = Math.min(depth + 1, 4);
  const items = specialHTML(c, id) + n.items.map((it) => {
    if (it.t === 'child') return readNode(c, it.ref, depth + 1);
    if (it.t === 'p' || it.t === 'tell') { const text = it.t === 'p' ? it.text : (it.own ? it.text : N(it.scene).items.map((x) => x.text || '').join(' ')); const notes = (WD.notes[it.id] || []).filter((x) => c.role === 'Author' || x.you); return `<div class="rblk" data-item="${it.id}"><p class="reading">${it.t === 'p' ? pText(it, true) : esc(text)}</p>${c.role === 'Reviewer' ? `<button type="button" class="icon-btn note-btn" data-w="note" data-item="${it.id}" aria-label="Add a note">${ic('edit')}</button>` : ''}${notes.map((x) => `<div class="rnote">${ic('info')}<div><b>${x.you ? 'Your note' : esc(x.who)}</b><div class="t-meta">Only you and the Authors see this</div>${esc(x.t)}</div></div>`).join('')}</div>`; }
    if (it.t === 'list') return `<ul class="rlist">${it.rows.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`;
    if (it.t === 'pic') return `<figure class="pic"><div class="pic-img" role="img" aria-label="${esc(it.cap)}"></div><figcaption class="t-meta">${esc(it.cap)}</figcaption></figure>`;
    return '';
  }).join('');
  const title = id === c.root ? '' : `<h${h} class="rh rh${h}" id="r-${id}">${c.lab[id] ? `<span class="tn">${esc(c.lab[id])}</span> ` : ''}${esc(n.title)}</h${h}>`;
  return title + items;
}
function pRead(c) {
  const sel = c.work.kind === 'Book' ? c.root : c.root;
  return `<div class="wr is-rail read ${WS.side ? 'has-side' : ''}" id="wr" data-work="${c.work.id}" data-node="${c.node}">${outlineHTML(c)}<div class="wmain">${headHTML(c)}<div class="wscroll" id="wscroll" tabindex="0" role="region" aria-label="Reading"><div class="wdoc rdoc" id="wdoc"><p class="t-meta">Reading ${esc(c.work.title)}${c.work.kind === 'Book' ? ' · ' + esc(N(c.root).title) : ''} as a reader would.${c.role === 'Reviewer' ? ' Select a passage, or use the pencil, to write a note.' : ''}</p>${readNode(c, sel, 0)}</div></div></div>${WS.side && !isSmall() ? `<aside class="wside" aria-label="${esc(sideTitle())}">${panelHTML(c)}</aside>` : ''}<div class="wscrim" data-w="outline-close"></div></div>`;
}
/* ------------------------------------------------------------------ the side views (a drawer above 1100, a sheet below; D26) */
const sideTitle = () => ({ details: 'Details', revisions: 'Revisions', review: 'Review', count: 'Word count', suggestions: 'Suggestions' }[WS.side] || '');
function tabsHTML(c) { const t = [['details', 'Details'], ...(c.role === 'Author' ? [['revisions', 'Revisions']] : []), ...(c.role === 'Author' && c.work.kind === 'Book' ? [['review', 'Review']] : []), ['count', 'Count'], ...(c.role === 'Author' ? [['suggestions', 'Suggest']] : [])]; return `<div class="seg" role="radiogroup" aria-label="Side view">${t.map(([k, l]) => `<button type="button" role="radio" aria-checked="${WS.side === k}" data-w="side-tab" data-v="${k}">${l}</button>`).join('')}</div>`; }
function panelHTML(c) {
  const n = N(c.node); const k = WS.side; let body = '';
  if (k === 'details') body = `<div class="fields"><div><label class="label" for="d-title">Title</label><input id="d-title" class="input" data-w="d-title" value="${esc(n.title)}"></div><div><span class="label">Kind</span><div>${n.kind[0].toUpperCase() + n.kind.slice(1)}${c.work.kind === 'Book' ? ' in ' + esc(N(c.root).title) : ''}</div></div><div><label class="label" for="d-view">Viewpoint</label><span class="selectwrap"><select id="d-view" class="select"><option>None chosen</option>${WD.beings.map((b) => `<option>${esc(b)}</option>`).join('')}</select>${ic('expand')}</span><p class="t-meta">A choice you make. Nothing is inferred from the text.</p></div><div><span class="label">Number</span><div class="seg" role="radiogroup" aria-label="Number">${[['auto', 'Automatic'], ['none', 'Unnumbered']].map(([v, l]) => `<button type="button" role="radio" aria-checked="${(n.unnumbered ? 'none' : 'auto') === v}" data-w="numbering" data-v="${v}">${l}</button>`).join('')}</div><p class="t-meta">Numbers are shown, not typed into the title. They follow every move.</p></div><div><label class="label" for="d-notes">Notes (private to Authors)</label><textarea id="d-notes" class="input" rows="4" placeholder="Anything you want to remember. It is never part of the writing."></textarea></div>${detailsExtra(c)}</div>`;
  else if (k === 'revisions') body = `<ul class="revs">${WD.revisions.map(([t, who, what]) => `<li><div class="grow"><b>${esc(t)}</b><div class="t-meta">${esc(who)} · ${esc(what)}</div></div><button type="button" class="btn" data-w="load-rev" data-t="${esc(t)}">Load into a draft</button></li>`).join('')}</ul><p class="t-meta">Loading a saved version makes a local draft. You decide what to save. Nothing is overwritten, and no sharing comes back with it.</p>`;
  else if (k === 'review') body = `<p class="muted">Reviewers read this Edition and write notes only they and its Authors see. They get no access to your library.</p><div class="listcard" style="margin:var(--s-3) 0">${WD.reviewers.map((r, i) => `<div class="item-row"><span class="grow"><span class="nm">${esc(r.name)}</span><span class="t-meta" style="display:block">${esc(r.email)}</span></span><button type="button" class="btn btn--quiet" data-w="revoke" data-i="${i}">Remove</button></div>`).join('')}</div><div class="row2"><label class="sr-only" for="rv-email">Email of a signed-in account</label><input id="rv-email" class="input" placeholder="Email of a signed-in account" type="email"><button type="button" class="btn" data-w="add-reviewer">Add</button></div><div style="margin-top:var(--s-3)"><span class="label">Review address</span><div class="row2"><code class="code">lorenzo-writing.pages.dev/review/hb-3f9c</code><button type="button" class="btn" data-w="copy-review">Copy</button></div><p class="t-meta">Anyone with the address still has to be on the list.</p></div>`;
  else if (k === 'suggestions') body = sugBody(c);
  else { const goal = c.work.goal; const tot = totalWords(c.root); body = `<dl class="counts"><div><dt>This ${n.kind}, own writing</dt><dd>${pl(ownWords(c.node), 'word', 'words')}</dd></div><div><dt>With its subchapters</dt><dd>${pl(totalWords(c.node), 'word', 'words')}</dd></div><div><dt>The whole ${c.work.kind === 'Book' ? 'Edition' : c.work.kind}</dt><dd>${pl(tot, 'word', 'words')}</dd></div><div><dt>Selected</dt><dd id="sel-count">Select a passage</dd></div></dl><p class="t-meta">Words are prose only. Markup, notes, code, maths and generated titles are not counted. A repeated reference counts each time it is read.</p>${goal !== undefined ? `<div style="margin-top:var(--s-3)"><label class="label" for="goal-in">Your length goal (only you see it)</label><div class="row2"><input id="goal-in" class="input" inputmode="numeric" value="${goal || ''}" placeholder="No goal"><button type="button" class="btn" data-w="goal-set">Set</button><button type="button" class="btn btn--quiet" data-w="goal-clear">Clear</button></div>${goal ? `<div class="meter" role="img" aria-label="${Math.round(tot / goal * 100)} percent of the goal"><span style="width:${Math.min(100, tot / goal * 100)}%"></span></div><p class="t-meta">${fmt(Math.max(0, goal - tot))} words to go.</p>` : ''}</div>` : ''}${c.role === 'Author' ? timerSessionHTML() : ''}`; }
  return `<div class="side-head"><h2 class="t-heading grow">${sideTitle()}</h2><button type="button" class="icon-btn" data-w="side-close" aria-label="Close">${ic('close')}</button></div>${tabsHTML(c)}<div class="side-body">${body}</div>`;
}
function openSide(k) {
  const c = ctx();
  if (WS.side === k && !isSmall()) { WS.side = null; wrRefresh(true); return; }
  WS.side = k;
  if (isSmall()) { WS.side = k; openDialog({ title: sideTitle(), wide: true, body: `<div id="sheet-side">${panelHTML(c).replace(/<div class="side-head">.*?<\/div>(?=<div class="seg")/, '')}</div>`, actions: [{ label: 'Close' }], init: (d) => { d.addEventListener('click', sideClick); } }); return; }
  wrRefresh(true);
}
/* ------------------------------------------------------------------ menus */
function menuAt(x, y, items, label) {
  const f = frame().getBoundingClientRect(); let a = $('#ctx-anchor'); if (!a) { a = document.createElement('span'); a.id = 'ctx-anchor'; a.style.cssText = 'position:fixed;width:1px;height:1px;pointer-events:none'; a.setAttribute('role', 'button'); a.setAttribute('aria-hidden', 'true'); document.body.appendChild(a); }
  a.style.left = x + 'px'; a.style.top = y + 'px'; openMenu(a, items, { label, align: 'left' });
  const m = $('#menu'); if (!isPhone() && m) { const r = m.getBoundingClientRect(); let top = parseFloat(m.style.top) || 0; let left = parseFloat(m.style.left);
    if (r.bottom > f.bottom - 8) top = Math.max(8, Math.min(y - f.top - r.height, f.height - r.height - 8)); m.style.top = top + 'px';
    if (!isNaN(left) && r.right > f.right - 8) m.style.left = Math.max(8, f.width - r.width - 8) + 'px'; }
}
function blockMenu(el, x, y) {
  const c = ctx(); if (c.role !== 'Author') return; const node = el.dataset.node, id = el.dataset.item; const it = N(node).items.find((i) => i.id === id); if (!it) return;
  const sel = getSelection(); const selBlocks = $$('.blk[data-item]').filter((b) => sel.rangeCount && !sel.isCollapsed && sel.getRangeAt(0).intersectsNode(b));
  const ids = selBlocks.length > 1 ? selBlocks.map((b) => b.dataset.item) : [id]; const many = ids.length > 1;
  const textSel = sel.rangeCount && !sel.isCollapsed && el.contains(sel.anchorNode) && it.t === 'p';
  const ed = $('[data-edit]', el); const inText = ed && sel.rangeCount && ed.contains(sel.anchorNode);
  const items = [
    { label: many ? `${ids.length} blocks` : 'This block', heading: true },
    { label: 'Move to…', icon: 'move', kbd: 'Alt+arrows', fn: () => moveDialog({ type: 'item', parent: node, item: id }) },
    { label: textSel ? 'Make a Chapter from the selection' : many ? `Make a Chapter from these ${ids.length}` : 'Make a Chapter from this', icon: 'kind-chapter-add', kbd: 'Or drag out', fn: () => askTitle('Make a Chapter', 'It takes the text with it, in the same place.', (t) => { if (textSel) { const r = selRange(ed); mutate('Made a Chapter', () => extractSelection(node, id, r[0], r[1], t) !== false); } else mutate('Made a Chapter', () => extractChapter(node, ids, t) !== false); }) },
    { label: many ? 'Make a Scene from these' : 'Make a Scene from this', icon: 'kind-scene', fn: () => askTitle('Make a Scene', 'A Scene can be told in more than one place. Here it becomes a shared telling.', (t) => mutate('Made a Scene', () => extractScene(node, ids, t) !== false)) },
    { label: 'Split the text here', icon: 'split', fn: () => { if (!inText) return refuse('Place the cursor in the text first', 'Click where the second part should begin, then choose Split.'); const at = caretOffset(ed); mutate('Split the text', () => splitText(node, id, at) !== false); } },
    { label: 'Join with the one above', icon: 'merge-items', fn: () => mutate('Joined two blocks', () => joinBlocks(node, id) !== false) },
    ...(it.t === 'tell' && !it.own ? [{ label: 'Make independent', icon: 'select-item', fn: () => mutate('Made an independent copy', () => makeIndependent(node, id)) }] : []),
    { sep: true },
    { label: 'Copy link', icon: 'link', fn: () => toast({ title: 'Link copied' }) },
    { label: 'Delete this block', icon: 'delete', danger: true, fn: () => mutate('Deleted a block', () => { N(node).items.splice(itemPos(node, id), 1); }) }];
  menuAt(x, y, items, 'Block actions');
}
function rowMenu(id, x, y) {
  const c = ctx(); const p = parentOf(id); const pn = p && N(p.node).items; const prevSib = pn && pn.slice(0, p.index).reverse().find((i) => i.t === 'child');
  menuAt(x, y, [
    { label: N(id).title, heading: true },
    { label: 'Add a subchapter', icon: 'add', fn: () => { const t = newChapter('Untitled'); mutate('Added a subchapter', () => { N(id).items.push({ id: uid(), t: 'child', ref: t }); }); } },
    { label: 'Rename', icon: 'edit', fn: () => askTitle('Rename', '', (t) => mutate('Renamed', () => { N(id).title = t; }), N(id).title) },
    { label: 'Move to…', icon: 'move', kbd: 'Alt+arrows', fn: () => moveDialog({ type: 'row', node: id }) },
    { label: 'Nest under the one above', icon: 'move', kbd: 'Alt+→', fn: () => mutate('Nested', () => nest(id)) },
    { label: 'Promote one level', icon: 'move', kbd: 'Alt+←', fn: () => mutate('Promoted', () => promote(id)) },
    { label: 'Join with the one above', icon: 'merge-items', fn: () => joinDialog(id) },
    { sep: true },
    { label: 'Take out of the outline', icon: 'kind-chapter-remove', fn: () => { const goTo = () => { if (c.node === id) location.hash = addr(c, c.root); }; mutate('Took out of the outline', () => takeOut(id), 'Its text and subchapters are kept. Find it under Chapters on the shelf.'); } }
  ], 'Chapter actions');
}
function askTitle(title, hint, ok, val = 'Untitled') {
  openDialog({ title, body: `${hint ? `<p class="muted">${esc(hint)}</p>` : ''}<label class="label" for="ask-t">Title</label><input id="ask-t" class="input" value="${esc(val)}">`, actions: [{ label: 'Cancel' }, { label: title, kind: 'primary', fn: (d) => { ok($('#ask-t', d).value.trim() || 'Untitled'); } }], init: (d) => { const i = $('#ask-t', d); i.focus(); i.select(); } });
}
function joinDialog(id) {
  const p = parentOf(id); const prev = p && N(p.node).items.slice(0, p.index).reverse().find((i) => i.t === 'child'); if (!prev) return refuse('There is no Chapter above to join with', 'Joining works between two Chapters that sit next to each other.');
  const a = prev.ref; if (N(a).kind !== N(id).kind) return refuse('Can’t join these');
  openDialog({ title: `Join “${N(id).title}” into “${N(a).title}”?`, body: `<p>Its text, pictures and subchapters move to the end of “${esc(N(a).title)}”, in the same order. Nothing is rewritten.</p><p class="muted">“${esc(N(id).title)}” keeps its notes and history, and a link to its section. You can undo this whole step.</p>`, actions: [{ label: 'Cancel' }, { label: 'Join', kind: 'primary', fn: () => { mutate('Joined two Chapters', () => join(a, id)); } }] });
}
function moveDialog(src) {
  const c = ctx(); const all = [{ id: c.root, depth: -1 }, ...flat(c.root)].filter((x) => !(src.type === 'row' && isInside(x.id, src.node)));
  openDialog({ title: 'Move to…', body: `<p class="muted">Choose where it goes. Nothing moves until you confirm.</p><div class="seg" role="radiogroup" aria-label="Place"><button type="button" role="radio" aria-checked="true" data-pl="in">Inside, at the end</button><button type="button" role="radio" aria-checked="false" data-pl="after">After it</button></div><ul class="pick" role="listbox" aria-label="Chapters">${all.map((x, i) => `<li><button type="button" role="option" class="menu-item" aria-selected="${i === 0}" data-pick="${x.id}" style="padding-left:${10 + (x.depth + 1) * 16}px">${ic(KIND_ICON[N(x.id).kind])}<span class="grow">${esc((c.lab[x.id] ? c.lab[x.id] + ' ' : '') + N(x.id).title)}</span></button></li>`).join('')}</ul>`, actions: [{ label: 'Cancel' }, { label: 'Move', kind: 'primary', fn: (d) => { const pick = $('[aria-selected="true"][data-pick]', d).dataset.pick; const place = $('[data-pl][aria-checked="true"]', d).dataset.pl; let parent = pick, index = N(pick).items.length; if (place === 'after' && pick !== c.root) { const p = parentOf(pick); parent = p.node; index = p.index + 1; } doMove(src, parent, index); } }],
    init: (d) => { d.addEventListener('click', (e) => { const b = e.target.closest('[data-pick]'); if (b) { $$('[data-pick]', d).forEach((x) => x.setAttribute('aria-selected', x === b)); } const q = e.target.closest('[data-pl]'); if (q) $$('[data-pl]', d).forEach((x) => x.setAttribute('aria-checked', x === q)); }); } });
}
function selRange(el) { const r = getSelection().getRangeAt(0); const pre = r.cloneRange(); pre.selectNodeContents(el); pre.setEnd(r.startContainer, r.startOffset); const a = pre.toString().length; return [a, a + r.toString().length]; }
function caretOffset(el) { const r = getSelection().getRangeAt(0); const pre = r.cloneRange(); pre.selectNodeContents(el); pre.setEnd(r.startContainer, r.startOffset); return pre.toString().length; }
function edMenu(e, c) {
  if (e.target.closest('.btn,.icon-btn,input,textarea,select,a,.trow,.wtools,.wtop')) return;
}
/* ------------------------------------------------------------------ refresh and handlers */
function wrRefresh(keep) {
  const sc = $('#wscroll'); const top = sc ? sc.scrollTop : 0; const r = cur(); S.meta = r.meta ? r.meta() : '';
  $('#main').innerHTML = r.render(); wrAfter(); if (keep) { const s2 = $('#wscroll'); if (s2) s2.scrollTop = top; } updateStatus();
}
function wrMeta() { const c = ctx(); const w = c.mode === 'read' ? totalWords(c.root) : ownWords(c.node); const g = c.work.goal && WS.goalOn ? ` · goal ${Math.min(100, Math.round(totalWords(c.root) / c.work.goal * 100))}%` : ''; const t = TM.state === 'idle' ? '' : TM.state === 'done' ? ' · Time elapsed' : ` · ${TM.state === 'paused' ? 'paused ' : ''}${mmss(tmLeft())}`; const se = SS.active ? ' · session ' + sessText() : ''; return `${fmt(w)} words${g}${t}${se}`; }
function sideClick(e) { clickW(e); }
function clickW(e) {
  const b = e.target.closest('[data-w]'); if (!b) return; const w = b.dataset.w; const c = ctx();
  const go2 = (h) => { location.hash = h; };
  if (window.moreClick && moreClick(e, b, w, c)) return;
  if (w === 'start') { const id = 'n' + uid(); WD.nodes[id] = { id, kind: 'scene', title: '', items: [{ id: uid(), t: 'p', text: '' }] }; WD.works.unshift({ id, kind: 'Scene', title: 'Untitled', root: id, role: 'Author', edited: 'edited just now' }); go2(`#/w/${id}//write`); return; }
  if (w === 'start-menu') { openMenu(b, [{ label: 'What are you starting?', heading: true }, { label: 'A Scene', icon: 'kind-scene', kbd: 'A page to write on', fn: () => { const id = 'n' + uid(); WD.nodes[id] = { id, kind: 'scene', title: '', items: [{ id: uid(), t: 'p', text: '' }] }; WD.works.unshift({ id, kind: 'Scene', title: 'Untitled', root: id, role: 'Author', edited: 'edited just now' }); go2(`#/w/${id}//write`); } }, { label: 'A Chapter', icon: 'kind-chapter', kbd: 'Put it in a Book later', fn: () => { const id = 'n' + uid(); WD.nodes[id] = { id, kind: 'chapter', title: '', items: [{ id: uid(), t: 'p', text: '' }] }; WD.works.unshift({ id, kind: 'Chapter', title: 'Untitled', root: id, role: 'Author', edited: 'edited just now', note: 'Not in a Book yet' }); go2(`#/w/${id}//write`); } }, { label: 'A Book', icon: 'kind-book', kbd: 'With its first Edition', fn: () => { const ed = 'n' + uid(), ch = 'n' + uid(), id = 'n' + uid(); WD.nodes[ed] = { id: ed, kind: 'edition', title: 'Edition 1', items: [{ id: uid(), t: 'child', ref: ch }] }; WD.nodes[ch] = { id: ch, kind: 'chapter', title: 'Chapter one', items: [{ id: uid(), t: 'p', text: '' }] }; WD.works.unshift({ id, kind: 'Book', title: 'Untitled Book', root: ed, role: 'Author', edited: 'edited just now', last: ch, editions: [ed] }); go2(`#/w/${id}/${ch}/write`); } }], { label: 'Start writing' }); return; }
  if (w === 'filter') { WS.filter = b.dataset.v; wrRefresh(); return; }
  if (w === 'mode') { go2(addr(c, c.node, b.dataset.v)); return; }
  if (w === 'pin') { WS.pin = !WS.pin; wrRefresh(true); return; }
  if (w === 'outline') { WS.open = !WS.open; $('#wout') && $('#wout').classList.toggle('open', WS.open); b.setAttribute('aria-expanded', WS.open); $('#wr') && $('#wr').classList.toggle('out-open', WS.open); return; }
  if (w === 'outline-close') { WS.open = false; $('#wout') && $('#wout').classList.remove('open'); $('#wr') && $('#wr').classList.remove('out-open'); return; }
  if (w === 'focus') { WS.focus = !WS.focus; wrRefresh(true); return; }
  if (w === 'side') { openSide(b.dataset.v); return; }
  if (w === 'side-tab') { WS.side = b.dataset.v; if ($('.wside')) wrRefresh(true); else { wrPanelRefresh(); const sh = $('#dialog #dlg-t'); if (sh) sh.textContent = sideTitle(); } return; }
  if (w === 'side-close') { WS.side = null; wrRefresh(true); return; }
  if (w === 'edition-menu') { const ed = c.work.editions || [c.root]; openMenu(b, [{ label: 'Editions', heading: true }, { label: 'Edition 1', check: c.root === 'ed1' || !c.work.editions, fn: () => go2(`#/w/${c.work.id}//write`) }, ...(c.work.id === 'harbour' || c.work.id === 'harbour-2' ? [{ label: 'Edition 2, a private copy', check: c.work.id === 'harbour-2', fn: () => go2('#/w/harbour-2//write') }] : []), { label: 'New Edition from a copy', icon: 'add', fn: newEditionDialog }, { sep: true }, { label: 'Numbering…', icon: 'list-numbered', fn: numberingDialog }, { label: 'Contents…', icon: 'list', fn: contentsDialog }, ...(c.work.source ? [{ sep: true }, { label: `Updates from ${c.work.source}…`, icon: 'update-available', fn: updatesDialog }] : []), { sep: true }, { label: 'Export…', icon: 'export', fn: exportDialog }], { label: 'Edition' }); return; }
  if (w === 'row-menu') { const r = b.getBoundingClientRect(); rowMenu(b.dataset.node, r.left, r.bottom); return; }
  if (w === 'add-chapter') { const t = newChapter('Untitled'); mutate('Added a Chapter', () => { N(b.dataset.parent).items.push({ id: uid(), t: 'child', ref: t }); }); setTimeout(() => { location.hash = addr(c, t); }, 0); return; }
  if (w === 'add-block') { const n = b.dataset.node; mutate('Added a block', () => { N(n).items.push({ id: uid(), t: 'p', text: '' }); }); setTimeout(() => { const ps = $$('[data-edit]'); ps[ps.length - 1] && ps[ps.length - 1].focus(); }, 30); return; }
  if (w === 'independent') { const it = N(b.dataset.node).items.find((i) => i.id === b.dataset.item); openDialog({ title: 'Make this telling independent?', body: `<p>It copies the Scene’s current text here. After that, editing it changes only this telling, and the Scene is not touched.</p>`, actions: [{ label: 'Cancel' }, { label: 'Make independent', kind: 'primary', fn: () => { mutate('Made an independent copy', () => makeIndependent(b.dataset.node, b.dataset.item)); } }] }); return; }
  if (w === 'keep') { const v = b.dataset.v; WS.force = 'saved'; wrRefresh(true); toast({ title: v === 'mine' ? 'Continuing from your version' : v === 'theirs' ? 'Continuing from the other version' : v === 'ok' ? 'Keep this tab open' : 'Both versions kept', text: v === 'both' ? 'The other version is a block at the end, marked for you to sort out.' : 'Autosave is on again. The other version stays in Revisions.' }); return; }
  if (w === 'recover') { WS.recovered = false; wrRefresh(true); toast({ title: b.dataset.v === 'restore' ? 'Restored unsent text from 19:38' : 'Discarded the unsent text' }); return; }
  if (w === 'tb') { const v = b.dataset.v; const ed = document.activeElement && document.activeElement.closest && document.activeElement.closest('[data-edit]'); const blk = ed && ed.closest('.blk'); const it = blk && N(blk.dataset.node).items.find((i) => i.id === blk.dataset.item);
    if (v === 'pic') { const n = c.node; mutate('Added a picture', () => { N(n).items.push({ id: uid(), t: 'pic', cap: 'A new picture' }); }); return; }
    if (v === 'link') { openPalette('Entries', 'link', (x) => { document.execCommand('insertText', false, x.name); toast({ title: `Linked ${x.name}` }); }); return; }
    if (v === 'b' || v === 'i') { const s = getSelection(); const t = s.toString(); if (!t) return toast({ kind: 'error', title: 'Select some text first' }); document.execCommand('insertText', false, (v === 'b' ? '**' : '_') + t + (v === 'b' ? '**' : '_')); if (ed) ed.dispatchEvent(new Event('input', { bubbles: true })); return; }
    if (!it) return toast({ kind: 'error', title: 'Place the cursor in a block first' });
    if (v === 'h') it.h = !it.h; else if (v === 'q') it.q = !it.q; else if (v === 'l') { it.t = 'list'; it.rows = (it.text || 'First point').split('. ').filter(Boolean); }
    wrRefresh(true); return; }
  if (w === 'numbering') { const n = N(c.node); n.unnumbered = b.dataset.v === 'none'; wrRefresh(true); return; }
  if (w === 'load-rev') { toast({ title: `Loaded the version from ${b.dataset.t} as a draft`, text: 'Review it, then save. Nothing was overwritten.' }); return; }
  if (w === 'revoke') { const r = WD.reviewers[+b.dataset.i]; openDialog({ title: `Remove ${r.name} as a reviewer?`, body: '<p>Their open review closes at its next check, within 30 seconds. Their notes stay with the Authors.</p>', actions: [{ label: 'Cancel' }, { label: 'Remove', kind: 'danger', fn: () => { WD.reviewers.splice(+b.dataset.i, 1); wrRefresh(true); } }] }); return; }
  if (w === 'add-reviewer') { const i = $('#rv-email'); const v = i && i.value.trim(); if (!/^\S+@\S+\.\S+$/.test(v || '')) return toast({ kind: 'error', title: 'Enter the email of a signed-in account' }); WD.reviewers.push({ name: v.split('@')[0], email: v }); wrRefresh(true); toast({ title: 'Reviewer added' }); return; }
  if (w === 'copy-review') { toast({ title: 'Review address copied', text: 'Only people on the list can open it.' }); return; }
  if (w === 'goal-set') { const v = parseInt(($('#goal-in') || {}).value, 10); if (!(v > 0)) return toast({ kind: 'error', title: 'Enter a number of words above zero' }); c.work.goal = v; wrRefresh(true); return; }
  if (w === 'goal-clear') { c.work.goal = 0; wrRefresh(true); return; }
  if (w === 'note') { const id = b.dataset.item; openDialog({ title: 'Write a note', body: '<p class="muted">Only you and the Authors of this Edition see it.</p><label class="label" for="nt">Note</label><textarea id="nt" class="input" rows="4"></textarea>', actions: [{ label: 'Cancel' }, { label: 'Save note', kind: 'primary', fn: (d) => { const t = $('#nt', d).value.trim(); if (!t) return false; (WD.notes[id] = WD.notes[id] || []).push({ you: true, t, who: 'You' }); wrRefresh(true); toast({ title: 'Note saved' }); } }], init: (d) => $('#nt', d).focus() }); return; }
}
function numberingDialog() {
  const sel = (i, v) => `<span class="selectwrap"><select id="nl${i}" class="select" aria-label="Level ${i + 1}">${[['decimal', '1, 2, 3'], ['roman', 'I, II, III'], ['alpha', 'A, B, C'], ['none', 'No number']].map(([k, l]) => `<option value="${k}" ${k === v ? 'selected' : ''}>${l}</option>`).join('')}</select>${ic('expand')}</span>`;
  openDialog({ title: 'Numbering', body: `<p class="muted">Numbers are shown beside titles and follow every move. Titles stay as you wrote them.</p><div class="fields">${WS.num.map((v, i) => `<div><label class="label" for="nl${i}">${['Chapters', 'Their subchapters', 'Below that'][i]}</label>${sel(i, v)}</div>`).join('')}</div>`, actions: [{ label: 'Cancel' }, { label: 'Apply', kind: 'primary', fn: (d) => { WS.num = [0, 1, 2].map((i) => $(`#nl${i}`, d).value); wrRefresh(true); } }] });
}
function contentsDialog() {
  openDialog({ title: 'Contents', body: '<p class="muted">A list of Chapters, made from the outline. It sits in a Contents Chapter, before the writing there.</p><div class="fields"><div><label class="label" for="cd">Depth</label><span class="selectwrap"><select id="cd" class="select"><option>Chapters only</option><option>Chapters and subchapters</option></select>' + ic('expand') + '</span></div><div><label class="label" for="ct">Each line</label><input id="ct" class="input" value="{number} {title}"></div></div>', actions: [{ label: 'Cancel' }, { label: 'Save', kind: 'primary', fn: () => toast({ title: 'Contents settings saved' }) }] });
}
function keyW(e) {
  const g = e.target.closest && e.target.closest('.grip');
  if (g && e.altKey && e.key.startsWith('Arrow')) { e.preventDefault(); kbMove(g, e.key); return; }
  if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); const d = g.dataset; moveDialog(d.drag === 'row' ? { type: 'row', node: d.node } : { type: 'item', parent: d.node, item: d.item }); return; }
  const ed = e.target.closest && e.target.closest('[data-edit]');
  if (ed && e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const blk = ed.closest('.blk'); const node = blk.dataset.node; const id = blk.dataset.item; if (!id) return; const at = caretOffset(ed); const it = N(node).items.find((i) => i.id === id); if (it.t !== 'p') return; const ix = itemPos(node, id); const ni = { id: uid(), t: 'p', text: it.text.slice(at).trimStart() }; it.text = it.text.slice(0, at).trimEnd(); N(node).items.splice(ix + 1, 0, ni); wrRefresh(true); saveTick(); setTimeout(() => { const el = $(`[data-item="${ni.id}"] [data-edit]`); el && el.focus(); }, 20); return; }
  if (ed && e.key === 'Backspace' && caretOffset(ed) === 0 && getSelection().isCollapsed) { const blk = ed.closest('.blk'); const ix = itemPos(blk.dataset.node, blk.dataset.item); const prev = N(blk.dataset.node).items[ix - 1]; if (ix > 0 && prev && prev.t === 'p') { e.preventDefault(); const len = prev.text.length; joinBlocks(blk.dataset.node, blk.dataset.item); wrRefresh(true); saveTick(); setTimeout(() => { const el = $(`[data-item="${prev.id}"] [data-edit]`); if (el && el.firstChild) { el.focus(); const r = document.createRange(); r.setStart(el.firstChild, Math.min(len, el.firstChild.length)); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); } }, 20); } return; }
  if (e.key === 'Escape' && WS.focus && !OV.el) { WS.focus = false; wrRefresh(true); return; }
  if ((e.key === 'F10' && e.shiftKey || e.key === 'ContextMenu') && e.target.closest) { const blk = e.target.closest('.blk[data-item]'); if (blk) { e.preventDefault(); const r = blk.getBoundingClientRect(); blockMenu(blk, r.left + 40, r.top + 30); } }
}
function inputW(e) {
  const ed = e.target.closest && e.target.closest('[data-edit]');
  if (ed) { const blk = ed.closest('.blk'); const it = N(blk.dataset.node).items.find((i) => i.id === blk.dataset.item); if (it) { it.text = ed.textContent; ed.removeAttribute('data-empty'); } sessEdit(); saveTick(); S.meta = wrMeta(); updateStatus(); if (WS.side === 'count' && !(document.activeElement && document.activeElement.closest('.wside, #dialog'))) wrPanelRefresh(); const g = $('#goal-t'); if (g) g.textContent = goalText(ctx().work); return; }
  const t = e.target.closest && e.target.closest('[data-title]'); if (t) { N(t.dataset.title).title = t.textContent; const w = ctx().work; if (w.root === t.dataset.title) w.title = t.textContent || 'Untitled'; saveTick(); return; }
  if (e.target.matches('[data-w="d-title"]')) { N(ctx().node).title = e.target.value; saveTick(); }
}
function focusoutW(e) { if (e.target.closest && e.target.closest('[data-title]')) { const t = $('[data-title]'); if (t && WS.titleDirty !== false) { const o = $('#wout'); if (o) { const keep = $('#wscroll').scrollTop; const c = ctx(); const html = outlineHTML(c); const tmp = document.createElement('div'); tmp.innerHTML = html; o.replaceWith(tmp.firstElementChild); } } } }
function wrAfter() {
  { const cc = cur().name === 'w' ? ctx().node : null; if (cc !== WS.node) { WS.node = cc; if (cc) sessRebase(); } }
  const bb = $('#wbubble'); if (bb) bb.hidden = true;
  const m = $('#main'); m.onclick = clickW; m.onkeydown = keyW; m.oninput = inputW; m.onfocusout = focusoutW;
  m.oncontextmenu = (e) => { const blk = e.target.closest('.blk[data-item]'); const row = e.target.closest('.trow[data-node]:not(.add)'); if (blk && !e.target.closest('input,textarea')) { e.preventDefault(); blockMenu(blk, e.clientX, e.clientY); } else if (row && ctx().role === 'Author') { e.preventDefault(); rowMenu(row.dataset.node, e.clientX, e.clientY); } };
  let lp = null; m.onpointerdown = (e) => { if (e.pointerType !== 'touch') return; const blk = e.target.closest('.blk[data-item]'); const row = e.target.closest('.trow[data-node]:not(.add)'); if (e.target.closest('.grip')) return; clearTimeout(lp); lp = setTimeout(() => { if (blk) blockMenu(blk, e.clientX, e.clientY); else if (row) rowMenu(row.dataset.node, e.clientX, e.clientY); }, 550); };
  m.onpointerup = m.onpointermove = m.onpointercancel = () => clearTimeout(lp);
  const r = cur(); if (r.name === 'w') { const c = ctx(); if (c.mode === 'read' && parts()[2]) { const t = $('#r-' + c.node); if (t) $('#wscroll').scrollTop = t.offsetTop - 20; } }
  if (window.wrDndBind) window.wrDndBind();
}
document.addEventListener('selectionchange', () => { const s = getSelection(); const el = $('#sel-count'); if (el) el.textContent = s && !s.isCollapsed && $('#wdoc') && $('#wdoc').contains(s.anchorNode) ? pl(wc(s.toString()), 'word', 'words') : 'Select a passage'; wrBubble(); });
/* the selection bubble: Make a Chapter, Make a Scene, and a handle to drag the selection out */
function wrBubble() {
  let b = $('#wbubble'); const s = getSelection(); const ed = s.anchorNode && s.anchorNode.parentElement && s.anchorNode.parentElement.closest && s.anchorNode.parentElement.closest('[data-edit]');
  if (!ed || s.isCollapsed || ctx().role !== 'Author' || ctx().mode !== 'write') { if (b) b.hidden = true; return; }
  if (!b) { b = document.createElement('div'); b.id = 'wbubble'; b.className = 'wbubble'; b.setAttribute('role', 'toolbar'); b.setAttribute('aria-label', 'Selection'); b.innerHTML = `<button type="button" class="icon-btn" data-bub="chapter" aria-label="Make a Chapter">${ic('kind-chapter-add')}</button><button type="button" class="icon-btn" data-bub="scene" aria-label="Make a Scene">${ic('kind-scene')}</button><span class="bub-grip grip" data-drag="sel" role="button" tabindex="0" aria-label="Drag the selection out to make a Chapter">${ic('drag')}</span>`; frame().appendChild(b); b.onmousedown = (e) => e.preventDefault(); b.onclick = (e) => { const x = e.target.closest('[data-bub]'); if (!x) return; const blk = ed.closest('.blk'); const [f, t] = selRange(ed); const node = blk.dataset.node, id = blk.dataset.item; const run = (kind) => askTitle(kind === 'chapter' ? 'Make a Chapter' : 'Make a Scene', '', (ti) => { if (kind === 'chapter') mutate('Made a Chapter', () => extractSelection(node, id, f, t, ti) !== false); else { const it = N(node).items.find((i) => i.id === id); const sc = 'sc' + uid(); WD.nodes[sc] = { id: sc, kind: 'scene', title: ti, items: [{ id: uid(), t: 'p', text: it.text.slice(f, t).trim() }] }; WD.works.push({ id: sc, kind: 'Scene', title: ti, root: sc, role: 'Author', edited: 'edited just now' }); mutate('Made a Scene', () => { const ix = itemPos(node, id); const before = it.text.slice(0, f).trimEnd(), after = it.text.slice(t).trimStart(); const repl = []; if (before) repl.push({ id: it.id, t: 'p', text: before }); repl.push({ id: uid(), t: 'tell', scene: sc, own: false, text: '' }); if (after) repl.push({ id: uid(), t: 'p', text: after }); N(node).items.splice(ix, 1, ...repl); }); } }); run(x.dataset.bub); }; }
  const r = s.getRangeAt(0).getBoundingClientRect(); const f = frame().getBoundingClientRect(); b.hidden = false; b.style.left = Math.max(8, r.left - f.left + r.width / 2 - 70) + 'px'; b.style.top = Math.max(8, r.top - f.top - 46) + 'px';
}
const wrRoutes = {
  shelf: { app: 'writing', tab: 'shelf', render: pShelf, after: () => { const m = $('#main'); m.onclick = clickW; }, meta: () => `${WD.works.filter((w) => !w.hidden).length} works` },
  w: { app: 'writing', tab: 'shelf', render: pWork, full: true, after: wrAfter, meta: wrMeta }
};
window.ROUTES_EXT = wrRoutes; window.START_ROUTE = 'shelf'; window.GO_EXT = { w: 'shelf' };
DATA.apps.find((a) => a.id === 'writing').route = 'shelf';
DATA.appTabs.writing = [['Home', 'shelf']];
const PB2 = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Browser storage</b>${[['1', 'Works'], ['0', 'Fails']].map(([v, t]) => PB2('wstore', v, t, String(+WS.storage) === v)).join('')}</span><span class="group"><b>Account</b>${[['busy', 'Has work'], ['new', 'New']].map(([v, t]) => PB2('wacct', v, t, WS.acct === v)).join('')}</span><span class="group"><b>Save state</b>${[['saved', 'Saved'], ['local', 'On this device'], ['conflict', 'Conflict'], ['storage', 'Storage failed']].map(([v, t]) => PB2('wforce', v, t, WS.force === v)).join('')}</span><span class="group"><b>Unsent text from before</b>${[['0', 'No'], ['1', 'Yes']].map(([v, t]) => PB2('wrec', v, t, String(+WS.recovered) === v)).join('')}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p]').forEach((b) => { const k = b.dataset.p, v = b.dataset.v; if (k === 'wacct') b.setAttribute('aria-pressed', WS.acct === v); else if (k === 'wforce') b.setAttribute('aria-pressed', WS.force === v); else if (k === 'wrec') b.setAttribute('aria-pressed', String(+WS.recovered) === v); else if (k === 'wstore') b.setAttribute('aria-pressed', String(+WS.storage) === v); }); };
window.PROTO_CLICK = (k, v) => {
  if (k === 'wacct') { WS.acct = v; go('shelf'); return true; }
  if (k === 'wforce') { WS.force = v; if (cur().name === 'w') wrRefresh(true); else updateStatus(); return true; }
  if (k === 'wstore') { WS.storage = v === '1'; if (cur().name === 'w') wrPanelRefresh(); return true; }
  if (k === 'wrec') { WS.recovered = v === '1'; if (cur().name === 'w') wrRefresh(true); return true; }
  return false;
};
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && WS.focus && !OV.el && cur().name === 'w') { WS.focus = false; wrRefresh(true); } });
window.INWORLD = () => null; /* no in-world date outside the calendar apps (CS1) */

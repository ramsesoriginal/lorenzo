/* Writing: three directions for the writing page, drawn on the shell. Made-up text. Nothing is saved.
   A: text in the middle, the outline beside it, a grip in the margin of every block.
   B: the outline is the spine: wide rows with a taste of each Chapter, the text beside it.
   C: the whole Edition as one continuous page; Chapters are folds in it; the outline is a thin rail. */
const WR = { dir: 'a', state: 'rest' };
const TREE = [
  { n: '1', t: 'Arrivals', w: 1240, snip: 'Imani came down the hill with one bag and no plan.' },
  { n: '2', t: 'The blackout', w: 3410, snip: 'The lights went out a little after nineteen forty.', kids: [
    { n: '2.1', t: 'Lamps out', w: 820, snip: 'Nobody noticed the first lamp. Everybody noticed the third.' },
    { n: '2.2', t: 'The quay', w: 1120, snip: 'The quay was empty when Imani reached it.', on: 1 }] },
  { n: '3', t: 'Night shift', w: 1980, snip: 'By midnight the harbour had its own weather.' }
];
const fmt = (n) => n.toLocaleString('en');
const grip = (label = 'Move') => `<button type="button" class="grip" aria-label="${label}">${ic('drag')}</button>`;
const P = [
  'The quay was empty when Imani reached it. Somewhere behind the warehouses a bell rang the hour, and the water slapped against the stone as though it had been waiting.',
  'She counted the lamps along the east wall. Four were lit. The fifth, the one the harbourmaster always complained about, had gone dark again.',
  '“You’re late,” said the voice from the dark, and Imani did not turn round.'
];
const scene = () => `<div class="blk blk--scene">${grip('Move the telling')}<div class="scene-card">${ic('kind-scene')}<div class="grow"><b>The ledger</b><span class="t-meta" style="display:block">Scene · shared telling · 214 words</span><span class="reading-sm">Every name in the ledger had been struck through but one.</span></div><span class="st">${ic('link')}<span>Shared</span></span></div></div>`;
const pic = () => `<div class="blk blk--pic">${grip('Move the picture')}<figure class="pic"><div class="pic-img" role="img" aria-label="Picture: the east wall at dusk"></div><figcaption class="t-meta">The east wall at dusk</figcaption></figure></div>`;
const para = (i, cls = '') => `<div class="blk ${cls}">${grip()}<p class="reading">${P[i]}</p></div>`;
const topbar = (extra = '') => `<div class="wtop"><div class="grow"><div class="t-meta crumbs">The harbour tales · Edition 1 · <span>2 The blackout</span></div><h1 class="wtitle">2.2 The quay</h1></div>${extra}<div class="seg" role="radiogroup" aria-label="Mode"><button type="button" role="radio" aria-checked="true">${ic('edit')}Write</button><button type="button" role="radio" aria-checked="false">${ic('kind-book')}Read</button></div><button type="button" class="icon-btn" aria-label="Details">${ic('info')}</button><button type="button" class="icon-btn" aria-label="Revisions">${ic('history')}</button><button type="button" class="icon-btn" aria-label="Focus mode">${ic('focus-mode')}</button></div>`;
const tools = () => `<div class="wtools" role="toolbar" aria-label="Formatting"><button class="icon-btn" aria-label="Heading">${ic('heading')}</button><button class="icon-btn" aria-label="Bold">${ic('bold')}</button><button class="icon-btn" aria-label="Italic">${ic('italic')}</button><button class="icon-btn" aria-label="Quote">${ic('quote')}</button><button class="icon-btn" aria-label="List">${ic('list')}</button><button class="icon-btn" aria-label="Picture">${ic('picture')}</button><button class="icon-btn" aria-label="Link an entry">${ic('entity-link')}</button><span class="grow"></span><span class="t-meta wgoal">${ic('goal')}1,120 of 1,500 words</span></div>`;
const menu = (top, left) => `<div class="menu wmenu" role="menu" style="top:${top}px;left:${left}px"><div class="menu-label">This block</div>${[['move', 'Move to…', 'Drag, or M'], ['kind-chapter-add', 'Make a Chapter from here', 'Select, then drag out'], ['kind-scene', 'Make a Scene from this', ''], ['split', 'Split the text here', 'Enter twice'], ['merge-items', 'Join with the one above', ''], ['link', 'Copy link', '']].map(([i, l, k]) => `<button type="button" role="menuitem" class="menu-item">${ic(i)}<span class="grow">${l}</span><span class="t-meta">${k}</span></button>`).join('')}<div class="menu-sep"></div><button type="button" role="menuitem" class="menu-item danger">${ic('kind-chapter-remove')}<span class="grow">Take out of this Chapter</span></button></div>`;
/* the outline tree (A) */
const trow = (c, deep, o = {}) => `<div class="trow ${c.on ? 'on' : ''} ${o.drop === c.n ? 'drop' : ''}" style="--d:${deep}">${grip('Move ' + c.t)}<span class="tn">${c.n}</span><span class="grow tt">${c.t}</span><span class="t-meta">${fmt(c.w)}</span></div>${(c.kids || []).map((k) => trow(k, deep + 1, o)).join('')}`;
const outlineA = (drop) => `<nav class="wout" aria-label="Outline"><div class="out-head"><span class="kindrow">${ic('kind-edition')}<b>Edition 1</b></span><button class="icon-btn" aria-label="Add a Chapter">${ic('add')}</button></div>${TREE.map((c) => trow(c, 0, { drop })).join('')}<div class="out-foot t-meta">${fmt(8570)} words · pinned open</div></nav>`;
function dirA() {
  const drag = WR.state === 'drag', men = WR.state === 'menu';
  const blocks = `${para(0)}${para(1, drag ? 'is-lifted' : '')}${drag ? '<div class="dropline"><span>Move here</span></div>' : ''}${scene()}${pic()}${para(2, men ? 'is-hover' : '')}`;
  const outline = outlineA(drag ? '2.1' : '');
  return `<div class="wr wr--a page-enter">${outline}<div class="wmain">${topbar()}${tools()}<div class="wscroll"><div class="wdoc">${blocks}</div></div>${men ? menu(400, 560) : ''}</div></div>`;
}
/* B: the spine */
const brow = (c, deep, o = {}) => `${o.lift === c.n ? '<div class="dropline dropline--nest"><span>Into 2 The blackout, after 2.2</span></div>' : ''}<div class="brow ${c.on ? 'on' : ''} ${o.lift === c.n ? 'is-lifted' : ''}" style="--d:${deep}">${grip('Move ' + c.t)}<div class="grow"><div class="bt"><span class="tn">${c.n}</span> ${c.t}</div><div class="bs">${c.snip}</div></div><span class="t-meta">${fmt(c.w)}</span></div>${(c.kids || []).map((k) => brow(k, deep + 1, o)).join('')}`;
function dirB() {
  const drag = WR.state === 'drag', men = WR.state === 'menu';
  let spine = TREE.map((c) => brow(c, 0, { lift: drag ? '3' : '' })).join('');
  if (false) spine = spine.replace('<div class="brow " style="--d:0"><button type="button" class="grip" aria-label="Move Night shift">', '<div class="dropline dropline--nest"><span>Into 2 The blackout, after 2.2</span></div><div class="brow is-lifted" style="--d:0"><button type="button" class="grip" aria-label="Move Night shift">');
  const doc = `<div class="wdoc">${para(0)}${para(1)}${scene()}${pic()}${para(2, men ? 'is-hover' : '')}</div>`;
  return `<div class="wr wr--b page-enter"><nav class="wspine" aria-label="Outline"><div class="out-head"><span class="kindrow">${ic('kind-edition')}<b>Edition 1</b></span><button class="icon-btn" aria-label="Add a Chapter">${ic('add')}</button></div>${spine}</nav><div class="wmain">${topbar()}${tools()}<div class="wscroll">${doc}</div>${men ? menu(400, 560) : ''}</div></div>`;
}
/* C: one continuous page */
const fold = (n, t, w, o = '') => `<div class="cfold ${o}">${grip('Move ' + t)}<span class="tn">${n}</span><h2 class="chead">${t}</h2><span class="t-meta">${fmt(w)} words</span><button class="icon-btn" aria-label="Fold ${t}">${ic('expand')}</button></div>`;
function dirC() {
  const drag = WR.state === 'drag', men = WR.state === 'menu';
  const rail = `<nav class="wrail" aria-label="Outline">${['1', '2', '2.1', '2.2', '3'].map((n) => `<a href="#/wc" class="${n === '2.2' ? 'on' : ''} ${n.includes('.') ? 'sub' : ''}"><span class="tick"></span><span class="rl">${n} ${{ 1: 'Arrivals', 2: 'The blackout', '2.1': 'Lamps out', '2.2': 'The quay', 3: 'Night shift' }[n]}</span></a>`).join('')}<div class="rail-foot t-meta">8,570<br>words</div></nav>`;
  const body = `<div class="cdoc"><div class="blk"><p class="reading dim">…the third lamp had already gone by the time anyone looked up.</p></div>${fold('2.2', 'The quay', 1120, drag ? 'is-lifted' : '')}${drag ? '' : `${para(0)}${para(1)}${scene()}${para(2, men ? 'is-hover' : '')}`}${drag ? '<div class="dropline"><span>Move 2.2 here, after 3 Night shift</span></div>' : ''}${fold('3', 'Night shift', 1980)}<div class="blk"><p class="reading dim">By midnight the harbour had its own weather. The wind came in low…</p></div></div>`;
  return `<div class="wr wr--c page-enter">${rail}<div class="wmain">${topbar()}<div class="wscroll">${body}</div>${men ? menu(400, 560) : ''}</div></div>`;
}
const MAP = { a: [dirA, 'Direction A: the margin'], b: [dirB, 'Direction B: the spine'], c: [dirC, 'Direction C: one page'] };
const wroute = (d) => ({ app: 'writing', tab: 'write', full: true, render: () => MAP[d][0](), after: () => {}, meta: () => '1,120 words · goal 75%' });
window.ROUTES_EXT = { wa: wroute('a'), wb: wroute('b'), wc: wroute('c') };
window.START_ROUTE = 'wa';
const PB = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>Direction</b>${[['a', 'A margin'], ['b', 'B spine'], ['c', 'C one page']].map(([v, t]) => PB('wdir', v, t, WR.dir === v)).join('')}</span><span class="group"><b>Show</b>${[['rest', 'At rest'], ['drag', 'Mid-drag'], ['menu', 'Right-click menu']].map(([v, t]) => PB('wstate', v, t, WR.state === v)).join('')}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p]').forEach((b) => { const k = b.dataset.p, v = b.dataset.v; if (k === 'wdir') b.setAttribute('aria-pressed', WR.dir === v); else if (k === 'wstate') b.setAttribute('aria-pressed', WR.state === v); }); };
window.PROTO_CLICK = (k, v) => {
  if (k === 'wdir') { WR.dir = v; go('w' + v); return true; }
  if (k === 'wstate') { WR.state = v; go('w' + WR.dir); return true; }
  return false;
};

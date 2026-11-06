/* Writing: state, the model, and every operation on it. Each operation checks first, then does, then offers Undo (D26). */
const parts = () => S.route.split("/");
const WS = { acct: 'busy', force: 'saved', typing: false, pin: true, open: false, focus: false, side: null, recovered: false, seq: 100, goalOn: true, num: ['decimal', 'decimal', 'decimal'], dismissed: {}, bold: false };
const N = (id) => WD.nodes[id];
const WK = (id) => WD.works.find((w) => w.id === id);
const uid = () => 'x' + (WS.seq++).toString(36);
const wc = (t) => (String(t || '').trim().match(/\S+/g) || []).length;
const fmt = (n) => Number(n).toLocaleString('en');
const KIND_ICON = { edition: 'kind-edition', chapter: 'kind-chapter', scene: 'kind-scene', carrier: 'kind-book-alt', Book: 'kind-book', Scene: 'kind-scene', Chapter: 'kind-chapter', Carrier: 'kind-book-alt' };
const kids = (id) => N(id).items.filter((i) => i.t === 'child').map((i) => i.ref);
const parentOf = (id) => { for (const k in WD.nodes) { const ix = WD.nodes[k].items.findIndex((i) => i.t === 'child' && i.ref === id); if (ix >= 0) return { node: k, index: ix }; } return null; };
const isInside = (id, anc) => { if (id === anc) return true; return kids(anc).some((k) => isInside(id, k)); };
const ownWords = (id) => N(id).items.reduce((s, i) => s + (i.t === 'p' ? wc(i.text) : i.t === 'list' ? wc(i.rows.join(' ')) : i.t === 'tell' ? (i.own ? wc(i.text) : wc(N(i.scene).items.map((x) => x.text || '').join(' '))) : 0), 0);
const totalWords = (id) => ownWords(id) + kids(id).reduce((s, k) => s + totalWords(k), 0);
const roman = (n) => ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'][n] || String(n);
const alpha = (n) => String.fromCharCode(64 + n);
const piece = (f, n) => (f === 'roman' ? roman(n) : f === 'alpha' ? alpha(n) : String(n));
/* Numbering is presentation, separate from titles (ADR 0380): a label per Chapter, recomputed after every move. */
function labels(root) {
  const out = {};
  const walk = (id, trail, depth) => {
    let n = 0;
    kids(id).forEach((k) => {
      const kn = N(k);
      if (kn.unnumbered || WS.num[Math.min(depth, 2)] === 'none') { out[k] = ''; walk(k, trail, depth + 1); return; }
      n += 1;
      const lab = [...trail, piece(WS.num[Math.min(depth, 2)], n)];
      out[k] = lab.join('.'); walk(k, lab, depth + 1);
    });
  };
  walk(root, [], 0); return out;
}
const snapshot = () => JSON.stringify(WD.nodes);
function mutate(title, fn, text) {
  const snap = snapshot(); const ok = fn(); if (ok === false) return false; if (window.sessRebase) sessRebase();
  WS.dirty = true; wrRefresh(true); saveTick();
  withUndo(title, () => { WD.nodes = JSON.parse(snap); wrRefresh(true); saveTick(); }, text);
  announce(title);
  return true;
}
function announce(t) { const l = $('#dnd-live'); if (l) l.textContent = t; }
function refuse(title, text) { toast({ kind: 'error', title, text }); announce(title + '. ' + (text || '')); return false; }
/* ---- save state (D18: it lives in the status bar; a failure is never hidden, also in focus mode) */
let saveTimer2 = null;
function saveTick() {
  if (WS.force !== 'saved') { updateStatus(); return; }
  WS.typing = true; updateStatus(); clearTimeout(saveTimer2);
  saveTimer2 = setTimeout(() => { WS.typing = false; updateStatus(); }, 900);
}
window.STATUS_SYNC = () => {
  if (WS.force === 'conflict') return ['conflict', 'Conflict: autosave stopped', 'warning'];
  if (WS.force === 'storage') return ['conflict', 'Not kept on this device', 'warning'];
  if (WS.force === 'local') return ['offline', 'Saved on this device', 'local-only'];
  if (WS.typing) return ['saving', 'Saving…', 'refresh'];
  return null;
};
/* ---- operations */
function removeItem(parent, idx) { return N(parent).items.splice(idx, 1)[0]; }
function insertItem(parent, idx, it) { N(parent).items.splice(idx, 0, it); }
function itemPos(node, itemId) { return N(node).items.findIndex((i) => i.id === itemId); }
/* move an item (block) or a child Chapter reference to parent[index] */
function moveTo(src, parent, index, label) {
  if (src.type === 'row') {
    const p = parentOf(src.node); if (!p) return refuse('The Edition cannot be moved');
    if (isInside(parent, src.node)) return refuse('That would put a Chapter inside itself', 'Pick a place outside it. Nothing moved.');
    const it = removeItem(p.node, p.index);
    let ix = index; if (p.node === parent && p.index < index) ix -= 1;
    insertItem(parent, ix, it); return true;
  }
  const from = itemPos(src.parent, src.item); const it = removeItem(src.parent, from);
  let ix = index; if (src.parent === parent && from < index) ix -= 1;
  insertItem(parent, ix, it); return true;
}
function doMove(src, parent, index, label) {
  const name = src.type === 'row' ? `Moved “${N(src.node).title}”` : 'Moved a block';
  return mutate(name + (label ? ': ' + label : ''), () => moveTo(src, parent, index));
}
function join(a, b) { /* join chapter b into the previous sibling a (ADR 0348): b's items move to the end of a; b is taken out of the outline */
  const pb = parentOf(b); const items = N(b).items.filter((i) => i.t !== 'child' || true);
  const bitems = N(b).items.slice(); N(b).items = [];
  N(a).items.push(...bitems);
  N(b).joined = a; removeItem(pb.node, pb.index);
  return true;
}
function takeOut(id) { const p = parentOf(id); removeItem(p.node, p.index); N(id).unassigned = true; return true; }
function newChapter(title, items) { const id = 'n' + uid(); WD.nodes[id] = { id, kind: 'chapter', title, items: items || [{ id: uid(), t: 'p', text: '' }] }; return id; }
function nest(id) { const p = parentOf(id); let j = p.index - 1; while (j >= 0 && N(p.node).items[j].t !== 'child') j--; if (j < 0) return refuse('There is nothing above to nest under'); const target = N(p.node).items[j].ref; const it = removeItem(p.node, p.index); N(target).items.push(it); return true; }
function promote(id) { const p = parentOf(id); const g = parentOf(p.node); if (!g) return refuse('Already at the top of the Edition'); const it = removeItem(p.node, p.index); insertItem(g.node, g.index + 1, it); return true; }
/* split a text item at a character offset */
function splitText(nodeId, itemId, at) {
  const ix = itemPos(nodeId, itemId); const it = N(nodeId).items[ix];
  if (it.t === 'list') return refuse('Can’t split inside a list', 'Place the cursor between two blocks, or after a blank line at the start of the next section.');
  if (it.t !== 'p') return refuse('Only text can be split here');
  const a = it.text.slice(0, at).trimEnd(), b = it.text.slice(at).trimStart();
  if (!a || !b) return refuse('Nothing to split here', 'Place the cursor inside the text, with words on both sides.');
  it.text = a; insertItem(nodeId, ix + 1, { id: uid(), t: 'p', text: b }); return true;
}
function joinBlocks(nodeId, itemId) {
  const ix = itemPos(nodeId, itemId); const items = N(nodeId).items;
  if (ix < 1 || items[ix - 1].t !== 'p' || items[ix].t !== 'p') return refuse('Can’t join these', 'Only two text blocks next to each other can be joined.');
  items[ix - 1].text = (items[ix - 1].text + ' ' + items[ix].text).trim(); items.splice(ix, 1); return true;
}
function extractChapter(nodeId, itemIds, title, at) { /* a consecutive range of whole blocks becomes a Chapter, in the same place (ADR 0345) */
  const items = N(nodeId).items; const ixs = itemIds.map((i) => itemPos(nodeId, i)).sort((a, b) => a - b);
  if (ixs.some((x, k) => k && x !== ixs[k - 1] + 1)) return refuse('Pick blocks that sit together', 'A Chapter can be made from a run of blocks, with nothing between them left out.');
  const moved = items.splice(ixs[0], ixs.length); const id = newChapter(title, moved);
  insertItem(nodeId, ixs[0], { id: uid(), t: 'child', ref: id }); return id;
}
function extractScene(nodeId, itemIds, title) {
  const items = N(nodeId).items; const ixs = itemIds.map((i) => itemPos(nodeId, i)).sort((a, b) => a - b);
  if (ixs.some((x, k) => k && x !== ixs[k - 1] + 1)) return refuse('Pick blocks that sit together');
  if (items.some((i, k) => ixs.includes(k) && i.t === 'child')) return refuse('A Scene can’t take Chapters', 'Pick text and pictures only.');
  const moved = items.splice(ixs[0], ixs.length); const id = 'sc' + uid();
  WD.nodes[id] = { id, kind: 'scene', title, items: moved }; WD.works.push({ id, kind: 'Scene', title, root: id, role: 'Author', edited: 'edited just now', hidden: false });
  insertItem(nodeId, ixs[0], { id: uid(), t: 'tell', scene: id, own: false, text: '' }); return id;
}
/* the text of the selection inside one paragraph becomes a Chapter: before and after stay, in order */
function extractSelection(nodeId, itemId, from, to, title, at) {
  const ix = itemPos(nodeId, itemId); const it = N(nodeId).items[ix]; const full = it.text;
  const before = full.slice(0, from).trimEnd(), mid = full.slice(from, to).trim(), after = full.slice(to).trimStart();
  if (!mid) return refuse('Nothing is selected');
  const id = newChapter(title, [{ id: uid(), t: 'p', text: mid }]);
  const repl = []; if (before) repl.push({ id: it.id, t: 'p', text: before });
  const parent = at && at.parent ? at.parent : nodeId;
  if (parent === nodeId && !at) { repl.push({ id: uid(), t: 'child', ref: id }); }
  if (after) repl.push({ id: uid(), t: 'p', text: after });
  N(nodeId).items.splice(ix, 1, ...repl);
  if (at && at.parent) { let idx = at.index; if (at.parent === nodeId) idx = Math.min(idx, N(nodeId).items.length); insertItem(at.parent, idx, { id: uid(), t: 'child', ref: id }); }
  return id;
}
function makeIndependent(nodeId, itemId) { const it = N(nodeId).items[itemPos(nodeId, itemId)]; it.own = true; it.text = N(it.scene).items.map((x) => x.text || '').join('\n\n'); return true; }
function flat(root, depth = 0) { const out = []; kids(root).forEach((k) => { out.push({ id: k, depth }); out.push(...flat(k, depth + 1)); }); return out; }
const crumbs = (id, root) => { const out = []; let cur = id; while (cur && cur !== root) { out.unshift(cur); const p = parentOf(cur); cur = p && p.node; } return out; };
/* ---- the personal timer (ADR 0393) and the net-new session goal (ADR 0394): this tab only, kept in sessionStorage */
const TM = { mins: 25, state: 'idle', deadline: 0, left: 25 * 60000, msg: '' };
const SS = { target: 0, active: false, net: 0, last: 0, done: false };
WS.storage = true;
const sget = (k) => { try { return JSON.parse(sessionStorage.getItem(k) || 'null'); } catch (e) { return null; } };
function sput(k, v) { if (!WS.storage) return false; try { sessionStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
function persist() { sput('wr-timer', { mins: TM.mins, state: TM.state, deadline: TM.deadline, left: TM.left }); sput('wr-session', { target: SS.target, active: SS.active, net: SS.net, done: SS.done }); }
(() => { const t = sget('wr-timer'); if (t && typeof t.mins === 'number') Object.assign(TM, t); const s = sget('wr-session'); if (s && typeof s.net === 'number') Object.assign(SS, s); })();
const tmLeft = () => (TM.state === 'running' ? Math.max(0, TM.deadline - Date.now()) : TM.left);
const mmss = (ms) => { const s = Math.ceil(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
function tmAct(a, mins) {
  if (a === 'start') { if (mins) TM.mins = Math.min(1440, Math.max(1, Math.round(mins))); TM.left = TM.mins * 60000; TM.deadline = Date.now() + TM.left; TM.state = 'running'; TM.msg = 'Timer started'; }
  else if (a === 'pause') { TM.left = tmLeft(); TM.state = 'paused'; TM.msg = 'Timer paused'; }
  else if (a === 'resume') { TM.deadline = Date.now() + TM.left; TM.state = 'running'; TM.msg = 'Timer resumed'; }
  else if (a === 'reset') { TM.state = 'idle'; TM.left = TM.mins * 60000; TM.msg = 'Timer reset'; }
  persist(); announce(TM.msg); if (cur().name === 'w') S.meta = wrMeta(); updateStatus();
}
setInterval(() => {
  if (TM.state !== 'running') return;
  const l = tmLeft();
  if (l <= 0) { TM.state = 'done'; TM.left = 0; TM.msg = 'Time elapsed'; persist(); announce('Time elapsed'); toast({ title: 'Time elapsed', text: 'Quiet by design: no sound and no notification.' }); }
  const el = $('#tm-left'); if (el) el.textContent = mmss(tmLeft()); if (cur().name === 'w') S.meta = wrMeta(); updateStatus();
}, 500);
/* session goal: signed net words from edits made in the editor. Structure, pictures and loaded revisions rebase and earn nothing. */
const curWords = () => { try { return ownWords(ctx().node); } catch (e) { return 0; } };
function sessRebase() { SS.last = curWords(); }
function sessEdit() { if (!SS.active) return; const w = curWords(); SS.net += w - SS.last; SS.last = w; persist(); }
function sessAct(a, target) {
  if (a === 'start') { SS.target = Math.max(1, Math.round(target || SS.target || 500)); SS.active = true; SS.done = false; SS.net = 0; sessRebase(); }
  else if (a === 'finish') { SS.active = false; SS.done = true; }
  else if (a === 'new') { SS.active = false; SS.done = false; SS.net = 0; }
  persist(); announce(a === 'start' ? 'Session started' : a === 'finish' ? 'Session finished' : 'New session ready'); if (cur().name === 'w') S.meta = wrMeta(); updateStatus();
}
const sessText = () => (SS.net >= SS.target ? `Target reached (${SS.net >= 0 ? '+' : ''}${SS.net})` : `${SS.net >= 0 ? '+' : ''}${SS.net} of ${SS.target}`);

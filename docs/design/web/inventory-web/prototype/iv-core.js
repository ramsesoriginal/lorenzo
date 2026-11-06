/* Inventory: state, what a board shows, and the moves. */
const pl = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const parts = () => S.route.split('/');
const IV = { board: null, sel: null, q: '', multi: false, picked: new Set(), col: 'eq', cat: 'lantern', cq: '', catSave: null, uns: 'Seil', unsTick: null, unsPick: 'rope', self: true, edit: false };
const isGM = () => S.role === 'gm';
const ivStore = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* memory only */ } } };
const fx = (n) => Math.round(n * 100) / 100;
const wt = (i) => fx(i.q * i.w);
const sumw = (L) => fx(L.reduce((n, i) => n + wt(i), 0));
const itemOf = (id) => ITEMS.find((i) => i.id === id);
const catOf = (id) => CAT.find((c) => c.id === id);
const ownerN = (id) => (BOARDS[id] || { n: 'Nobody' }).n;
const colN = (b, c) => ((BOARDS[b] || { cols: [] }).cols.find((x) => x.id === c) || { n: c }).n;
const mySet = () => (isGM() ? Object.keys(BOARDS) : [...MINE, ...GROUPS]);
const canOpen = (b) => isGM() || MINE.includes(b) || GROUPS.includes(b);
const canMove = (i) => isGM() || [MEP, ...GROUPS].includes(i.at);
const uid = (() => { let n = 100; return () => 'x' + (n++).toString(36); })();
const match = (i) => !IV.q || i.n.toLowerCase().includes(IV.q.toLowerCase());
/* a board: its own columns, then read-only columns for whatever else holds something of theirs (ADR 0131) */
function colsOf(b) {
  const own = BOARDS[b].cols.map((c) => ({ ...c, all: ITEMS.filter((i) => i.at === b && i.col === c.id) }));
  own.forEach((c) => { c.items = c.all.filter(match); });
  const ro = {};
  ITEMS.filter((i) => i.owner === b && i.at !== b).forEach((i) => { const k = `${i.at}:${i.col}`; (ro[k] = ro[k] || { id: k, n: colN(i.at, i.col), note: `Not carried, with ${ownerN(i.at)}`, ro: true, all: [] }).all.push(i); });
  const rod = Object.values(ro); rod.forEach((c) => { c.items = c.all.filter(match); });
  return [...own, ...rod];
}
const carriedW = (b) => sumw(ITEMS.filter((i) => i.at === b && (BOARDS[b].cols.find((c) => c.id === i.col) || {}).carried));
const snapI = () => JSON.stringify(ITEMS);
const restoreI = (s) => { ITEMS = JSON.parse(s); };
function announce(t) { let l = $('#iv-live'); if (!l) { l = document.createElement('div'); l.id = 'iv-live'; l.className = 'sr-only'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = ''; setTimeout(() => { l.textContent = t; }, 30); }
/* ---- moves. Each returns null when it worked, or the words of a refusal. */
function sameStack(a, b) { return a.cat && a.cat === b.cat && a.n === b.n && !a.unsorted && !b.unsorted && a.owner === b.owner && a.id !== b.id; }
function moveTo(i, b, c) {
  const col = BOARDS[b].cols.find((x) => x.id === c); if (!col) return 'That column cannot take things.';
  if (col.cap != null) { const now = sumw(ITEMS.filter((x) => x.at === b && x.col === c && x.id !== i.id)); if (now + wt(i) > col.cap) return `The ${col.n.toLowerCase()} holds ${col.cap} lb. With this it would hold ${fx(now + wt(i))} lb.`; }
  const twin = ITEMS.find((x) => x.at === b && x.col === c && sameStack(x, i));
  if (twin) { twin.q += i.q; ITEMS = ITEMS.filter((x) => x.id !== i.id); return null; }
  i.at = b; i.col = c; return null;
}
function setDown(i) {
  const b = i.at; const n = i.q;
  if (n > 1 && i.cat) { const base = { ...i, q: 1 }; ITEMS = ITEMS.filter((x) => x.id !== i.id); for (let k = 0; k < n; k++) ITEMS.push({ ...base, id: uid(), at: b, col: 'nc', notes: k === 0 ? i.notes : [] }); return null; }
  return moveTo(i, b, 'nc');
}
function splitStack(i, k) { if (k < 1 || k >= i.q) return 'Choose a number between 1 and ' + (i.q - 1) + '.'; i.q -= k; ITEMS.push({ ...i, id: uid(), q: k, notes: [] }); return null; }
function mergeStacks(L) { const [a, ...rest] = L; rest.forEach((r) => { a.q += r.q; ITEMS = ITEMS.filter((x) => x.id !== r.id); }); }
function giveTo(i, to, hand, k) {
  if (k < i.q) { const part = { ...i, id: uid(), q: k, notes: [] }; i.q -= k; ITEMS.push(part); i = part; }
  i.owner = to; if (hand) { i.at = to; i.col = 'eq'; }
}

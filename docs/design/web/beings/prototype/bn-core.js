/* Beings: state, who may do what, the steps of Play, and the saving of what is typed in place. */
const pl = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const parts = () => S.route.split('/');
const BN = { view: 'rows', q: '', kind: 'All', layout: 'sheet', mode: 'read', why: null, editAbout: false, editStat: null, adjust: null, hist: [], last: null, saved: '', adjustOpen: null };
const isGM = () => S.role === 'gm';
const bnStore = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* kept in memory only */ } } };
const beingOf = (id) => BEINGS.find((b) => b.id === id);
const personName = (id) => (PEOPLE.find((p) => p.id === id) || { n: 'Not played' }).n;
const mine = (b) => b.played === ME;
/* a being is seen by everyone, or by its GM and player (a conservative stand-in for the library's audiences) */
const canSee = (b) => isGM() || b.seen === 'Everyone' || mine(b);
const canEdit = (b) => isGM() || mine(b);
const canRun = (b) => isGM() || mine(b);
/* a note is absent, not hidden, when it may not be read */
const noteVisible = (b, n) => isGM() || n.aud === 'Everyone' || (n.aud === 'Player note' && mine(b)) || (n.aud === 'Some characters' && (n.who || []).some((w) => BEINGS.some((x) => x.name === w && mine(x))));
const visibleNotes = (b) => b.notes.filter((n) => noteVisible(b, n));
const statDef = (id) => STATDEF.find((d) => d.id === id);
const statVal = (b, d) => (d.derived ? d.derived(b) : b.stats[d.id].v);
const statMax = (b, d) => (d.max ? b.stats[d.id].max : null);
const listBeings = () => (BN.empty ? [] : BEINGS).filter((b) => canSee(b)).filter((b) => (BN.kind === 'All' || b.kind === BN.kind) && (!BN.q || b.name.toLowerCase().includes(BN.q.toLowerCase())) && (S.route !== 'mine' || mine(b)));
const initials = (n) => n.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
const bnClock = () => new Date().toTimeString().slice(0, 5);
/* ---- the steps of Play (BN3): thirty, newest last; Undo takes the last, a step in the list takes everything after it */
function playStep(b, id, to) {
  const d = statDef(id); const cur = b.stats[id]; const max = cur.max; to = Math.max(0, max != null ? Math.min(max, to) : to);
  if (to === cur.v) { announce(`${d.n} is already ${to === 0 ? 'zero' : 'at its limit'}`); return false; }
  const from = cur.v; cur.v = to;
  BN.hist.push({ b: b.id, id, from, to, n: `${d.n} ${from} to ${to}` }); if (BN.hist.length > 30) BN.hist.shift();
  announce(`${d.n} ${to}${max != null ? ` of ${max}` : ''}`); return true;
}
const bnHist = (b) => BN.hist.filter((h) => h.b === b.id);
function undoTo(b, idx) { const list = bnHist(b); let n = 0; while (list.length > idx) { const h = list.pop(); const hb = beingOf(h.b); if (hb) hb.stats[h.id].v = h.from; BN.hist.splice(BN.hist.lastIndexOf(h), 1); n++; } return n; }
function undoLast(b) { const l = bnHist(b); if (!l.length) return false; const h = l[l.length - 1]; undoTo(b, l.length - 1); announce(`Undid: ${h.n}`); return h; }
/* the mode a person lands in (BN5): the player of a being lands in the last mode they used there */
const modeKey = (b) => `bn-mode-${b.id}`;
function openMode(b) { return mine(b) && !isGM() && bnStore.get(modeKey(b)) === 'play' ? 'play' : 'read'; }
const fx = (n) => Math.round(n * 100) / 100;
function announce(t) { let l = $('#bn-live'); if (!l) { l = document.createElement('div'); l.id = 'bn-live'; l.className = 'sr-only'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = ''; setTimeout(() => { l.textContent = t; }, 30); }
const uidn = (() => { let n = 100; return () => 'x' + (n++).toString(36); })();

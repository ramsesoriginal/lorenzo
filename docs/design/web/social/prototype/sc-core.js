/* Social: state, what a reader may see, the standings, the date lens, the layouts and the matrix's edits. */
const pl = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const parts = () => S.route.split('/');
const SC = { web: 'court', view: 'graph', sel: null, labels: true, hulls: true, hide: new Set(), steps: 0, layout: 'circle', lens: null, lensAll: false, asread: null, connect: null, z: 1, px: 0, py: 0, mxMode: 'rep', order: 'name', cur: ['mara', 'tobias'], draft: {}, refused: {}, undoS: [], redoS: [], noTypes: false, noWebs: false, stale: true, q: '', rq: '', rf: { type: '', end: '', min: '' }, ent: 'mara', editing: null };
const isGM = () => S.role === 'gm';
const MYBEING = 'imani'; /* the player's own being */
const entOf = (id) => ENTS[id]; const typeOf = (id) => TYPES.find((t) => t.id === id); const stOf = (id) => STANDINGS.find((s) => s.id === id); const relOf = (id) => RELS.find((r) => r.id === id); const webOf = (id) => WEBS.find((w) => w.id === id);
const evOf = (id) => EVENTS.find((e) => e.id === id);
const uid = (() => { let n = 100; return () => 'x' + (n++).toString(36); })();
const fx = (n) => Math.round(n * 100) / 100;
function announce(t) { let l = $('#sc-live'); if (!l) { l = document.createElement('div'); l.id = 'sc-live'; l.className = 'sr-only'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = ''; setTimeout(() => { l.textContent = t; }, 30); }
/* ---- what a reader may read: a relationship, with both ends (S4) */
const viewer = () => SC.asread || (isGM() ? null : MYBEING);
const entVisible = (id) => isGM() ? true : !ENTS[id].hid;
function relVisible(r) {
  if (!ENTS[r.a] || !ENTS[r.b]) return false; const v = viewer();
  if (isGM() && !v) return true;
  if (!isGM() && ENTS[r.a].hid || ENTS[r.b].hid && !isGM()) return false;
  if (r.aud === 'public') return true; return r.readers.includes(v) || r.a === v || r.b === v;
}
const visRels = () => RELS.filter(relVisible);
/* ---- the date lens: holds, not yet, ended or unknown, only over the reader's recorded order (ADR 0405) */
const ORDER = EVENTS.filter((e) => !e.unordered && !e.hidden).map((e) => e.id);
function stateAt(r, E) {
  if (!E) return 'holds';
  const e = (id) => { if (!id) return undefined; const ev = evOf(id); if (ev.hidden && !isGM()) return null; return ORDER.includes(id) ? ORDER.indexOf(id) : null; };
  const s = e(r.since), u = e(r.until), at = ORDER.indexOf(E);
  if (s === null || u === null) return 'unknown'; if (at < 0) return 'unknown';
  if (s !== undefined && s > at) return 'not yet'; if (u !== undefined && u <= at) return 'ended'; return 'holds';
}
const relState = (r) => stateAt(r, SC.lens);
const shownRels = (web) => { const m = new Set(web.members); return visRels().filter((r) => m.has(r.a) && m.has(r.b) && !SC.hide.has(r.type)); };
/* ---- words */
const entName = (id) => ENTS[id].n;
function sentence(r) { const t = typeOf(r.type); return t.reads ? `${entName(r.a)} ${t.reads} ${entName(r.b)}` : `${entName(r.a)}: ${t.n}: ${entName(r.b)}`; }
const typePath = (id) => { const t = typeOf(id); return t.parent ? `${typeOf(t.parent).n} › ${t.n}` : t.n; };
const twoWay = (r) => !typeOf(r.type).directed;
/* ---- a standing: its own value, one inherited from the type, or none; its scale */
function standing(r, id) {
  const sd = stOf(id); const own = r.vals[id]; const t = typeOf(r.type);
  const inh = t.defaults && t.defaults[id] !== undefined ? t.defaults[id] : (t.parent && typeOf(t.parent).defaults ? typeOf(t.parent).defaults[id] : undefined);
  if (own !== undefined) return { v: own, src: r.through.length ? 'derived' : 'own', sd };
  if (inh !== undefined) return { v: inh, src: 'inherited', sd }; return { v: null, src: 'none', sd };
}
function barPct(v, sd, range) { const lo = sd.min !== null ? sd.min : range[0], hi = sd.max !== null ? sd.max : range[1]; if (hi === lo) return 50; return Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100)); }
const rangeOf = (id) => { const vs = visRels().map((r) => standing(r, id).v).filter((v) => v !== null); return vs.length ? [Math.min(0, ...vs), Math.max(...vs)] : [0, 1]; };
function validateStanding(id, raw) { const sd = stOf(id); const n = Number(raw); if (raw === '' || isNaN(n)) return `${sd.n} is a number.`; if (sd.min !== null && n < sd.min) return `${sd.n} is at least ${sd.min}.`; if (sd.max !== null && n > sd.max) return `${sd.n} is at most ${sd.max}.`; return null; }
/* ---- layouts: stand-ins for the renderer's engines. Same input, same positions. */
const GW = 900, GH = 540;
function layoutOf(web, focus) {
  const ids = web.members; const P = {}; const cx = GW / 2, cy = GH / 2;
  const circle = () => ids.slice().sort((a, b) => (GROUP_OF(a)[0] || 'zz').localeCompare(GROUP_OF(b)[0] || 'zz') || ids.indexOf(a) - ids.indexOf(b)).forEach((id, i) => { const a = (i / ids.length) * 2 * Math.PI - Math.PI / 2; P[id] = [cx + Math.cos(a) * 300, cy + Math.sin(a) * 190]; });
  if (web.layout === 'circle' || web.layout === 'manual') circle();
  else if (web.layout === 'radial') { const f = ids.includes(focus) ? focus : ids[0]; const dist = { [f]: 0 }; const q = [f]; const adj = (x) => RELS.filter((r) => ids.includes(r.a) && ids.includes(r.b) && (r.a === x || r.b === x)).map((r) => (r.a === x ? r.b : r.a)); while (q.length) { const x = q.shift(); adj(x).forEach((y) => { if (dist[y] === undefined) { dist[y] = dist[x] + 1; q.push(y); } }); } const far = Math.max(...Object.values(dist)) + 1; const rings = {}; ids.forEach((id) => { const d = dist[id] === undefined ? far : dist[id]; (rings[d] = rings[d] || []).push(id); }); Object.entries(rings).forEach(([d, L]) => L.forEach((id, i) => { if (+d === 0) P[id] = [cx, cy]; else { const a = (i / L.length) * 2 * Math.PI + d; P[id] = [cx + Math.cos(a) * d * 125 * 1.25, cy + Math.sin(a) * d * 125 * 0.78]; } })); }
  else { circle(); const E = RELS.filter((r) => ids.includes(r.a) && ids.includes(r.b)); for (let it = 0; it < 220; it++) { const F = {}; ids.forEach((id) => { F[id] = [0, 0]; }); ids.forEach((a, i) => ids.slice(i + 1).forEach((b) => { let dx = P[a][0] - P[b][0], dy = P[a][1] - P[b][1]; const d = Math.max(20, Math.hypot(dx, dy)); const f = 9000 / (d * d); dx /= d; dy /= d; F[a][0] += dx * f; F[a][1] += dy * f; F[b][0] -= dx * f; F[b][1] -= dy * f; })); E.forEach((r) => { let dx = P[r.b][0] - P[r.a][0], dy = P[r.b][1] - P[r.a][1]; const d = Math.max(1, Math.hypot(dx, dy)); const f = (d - 140) * 0.02; dx /= d; dy /= d; F[r.a][0] += dx * f; F[r.a][1] += dy * f; F[r.b][0] -= dx * f; F[r.b][1] -= dy * f; }); ids.forEach((id) => { F[id][0] += (cx - P[id][0]) * 0.01; F[id][1] += (cy - P[id][1]) * 0.012; P[id][0] = Math.max(50, Math.min(GW - 50, P[id][0] + F[id][0])); P[id][1] = Math.max(50, Math.min(GH - 60, P[id][1] + F[id][1])); }); } }
  Object.entries(web.pos || {}).forEach(([id, p]) => { if (P[id]) P[id] = p; });
  Object.keys(P).forEach((id) => { P[id] = [Math.round(P[id][0] * 100) / 100, Math.round(P[id][1] * 100) / 100]; });
  return P;
}
const neighbours = (web, id, n) => { const seen = { [id]: 0 }; const q = [id]; while (q.length) { const x = q.shift(); if (seen[x] >= n) continue; visRels().filter((r) => r.a === x || r.b === x).forEach((r) => { const y = r.a === x ? r.b : r.a; if (seen[y] === undefined) { seen[y] = seen[x] + 1; q.push(y); } }); } return Object.keys(seen); };
/* ---- history: a snapshot of the data, for Undo */
const snapS = () => JSON.stringify({ RELS, WEBS, TYPES, STANDINGS });
const restoreS = (s) => { const o = JSON.parse(s); RELS = o.RELS; WEBS = o.WEBS; TYPES = o.TYPES; STANDINGS = o.STANDINGS; };
const GROUP_OF = (id) => Object.keys(GROUP_MEMBERS).filter((g) => GROUP_MEMBERS[g].includes(id));
/* ---- the matrix: a cell per ordered pair */
function cellRels(a, b) { const t = SC.mxMode.startsWith('type:') ? SC.mxMode.slice(5) : null; return visRels().filter((r) => (t ? r.type === t : true) && ((r.a === a && r.b === b) || (twoWay(r) && r.a === b && r.b === a))); }

/* a convex hull of points (monotone chain), for a group's soft outline */
function hullOf(pts) { const P = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]); if (P.length < 3) return P; const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); const lo = []; P.forEach((p) => { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }); const up = []; P.slice().reverse().forEach((p) => { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }); return lo.slice(0, -1).concat(up.slice(0, -1)); }

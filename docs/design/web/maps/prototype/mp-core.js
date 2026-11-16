/* Maps: state, the viewport, history, and the algorithms the generating tools use. */
const MP = { role: 'GM', map: 'harbour', date: null, tool: 'select', sel: null, layers: { Pictures: true, Places: true, People: true, Roads: true, Names: true, Terrain: true, Grid: false, Height: false }, look: 'default', panel: null, snap: true, vp: { x: 0, y: 0, k: 1 }, draft: null, preview: null, hist: [], hi: -1, cmd: [], opt: {}, ov: { pointer: null }, tab: 'item', seed: 4821, height: null, listQ: '', locQ: '', dateTf: false };
const parts = () => S.route.split('/');
const esc2 = esc;
const pl = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const curMap = () => MAPS.find((m) => m.id === MP.map) || MAPS[0];
const places = () => (PL[MP.map] = PL[MP.map] || []);
const placeOf = (id) => places().find((p) => p.id === id);
const uid = (() => { let n = 100; return () => 'x' + (n++).toString(36); })();
const canWrite = () => MP.role === 'GM';
const locOf = (id) => LOCS.find((l) => l.id === id);
const visible = (l) => MP.role === 'GM' || l.open;
const hiddenAnc = (l) => { let p = locOf(l.parent); while (p) { if (!p.open) return true; p = locOf(p.parent); } return false; };
/* a Location is shown under its nearest visible ancestor: a hidden level leaves no trace */
const nearestVisibleParent = (l) => { let p = locOf(l.parent); while (p && !visible(p)) p = locOf(p.parent); return p ? p.id : null; };
const pathOf = (l) => { const out = []; let p = locOf(nearestVisibleParent(l)); while (p) { out.unshift(p.n); p = locOf(nearestVisibleParent(p)); } return out; };
const inWords = (l) => { const p = pathOf(l); return p.length ? (p.length === 1 ? `in ${p[0]}` : `in ${p[p.length - 1]}, within ${p.slice(0, -1).reverse().join(', within ')}`) : 'Not part of another place'; };
/* ---- seeded random and noise */
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function noiseField(w, h, scale, seed, oct = 3) { const r = rng(seed); const L = {}; const lat = (x, y) => { const k = x + ',' + y; if (!(k in L)) L[k] = r(); return L[k]; }; const f = new Float32Array(w * h); for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { let v = 0, amp = 1, tot = 0, sc = scale; for (let o = 0; o < oct; o++) { const gx = x / sc, gy = y / sc; const x0 = Math.floor(gx), y0 = Math.floor(gy); const tx = gx - x0, ty = gy - y0; const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty); const a = lat(x0 + o * 97, y0), b = lat(x0 + 1 + o * 97, y0), c = lat(x0 + o * 97, y0 + 1), d = lat(x0 + 1 + o * 97, y0 + 1); v += amp * ((a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy); tot += amp; amp *= 0.5; sc /= 2; } f[y * w + x] = v / tot; } return f; }
/* ---- marching squares: the loops of a field at a threshold. Points are in field units. */
function marchingLoops(f, w, h, thr) {
  const val = (x, y) => (x < 0 || y < 0 || x >= w || y >= h ? -1 : f[y * w + x]); const segs = [];
  const lerp = (a, b, va, vb) => (a + ((thr - va) / (vb - va || 1e-9)) * (b - a));
  for (let y = -1; y < h; y++) for (let x = -1; x < w; x++) {
    const v = [val(x, y), val(x + 1, y), val(x + 1, y + 1), val(x, y + 1)]; let c = 0; v.forEach((q, i) => { if (q >= thr) c |= 1 << i; }); if (c === 0 || c === 15) continue;
    const e = { t: () => [lerp(x, x + 1, v[0], v[1]), y], r: () => [x + 1, lerp(y, y + 1, v[1], v[2])], b: () => [lerp(x, x + 1, v[3], v[2]), y + 1], l: () => [x, lerp(y, y + 1, v[0], v[3])] };
    const T = { 1: ['l', 't'], 2: ['t', 'r'], 3: ['l', 'r'], 4: ['r', 'b'], 6: ['t', 'b'], 7: ['l', 'b'], 8: ['b', 'l'], 9: ['t', 'b'], 11: ['r', 'b'], 12: ['r', 'l'], 13: ['t', 'r'], 14: ['t', 'l'] }; const t = T[c]; if (t) segs.push([e[t[0]](), e[t[1]]()]); else if (c === 5) { segs.push([e.l(), e.t()], [e.r(), e.b()]); } else if (c === 10) { segs.push([e.t(), e.r()], [e.b(), e.l()]); }
  }
  const key = (p) => p[0].toFixed(3) + ',' + p[1].toFixed(3); const idx = new Map(); segs.forEach((s, i) => { [s[0], s[1]].forEach((p) => { const k = key(p); if (!idx.has(k)) idx.set(k, []); idx.get(k).push(i); }); });
  const used = new Array(segs.length).fill(false); const loops = [];
  for (let i = 0; i < segs.length; i++) { if (used[i]) continue; used[i] = true; const loop = [segs[i][0], segs[i][1]]; let guard = 0; while (guard++ < 5000) { const end = loop[loop.length - 1]; const nxt = (idx.get(key(end)) || []).find((j) => !used[j]); if (nxt === undefined) break; used[nxt] = true; const s = segs[nxt]; loop.push(key(s[0]) === key(end) ? s[1] : s[0]); } if (loop.length > 3) loops.push(loop); }
  return loops;
}
/* ---- Ramer–Douglas–Peucker */
function simplify(pts, tol) { if (pts.length < 3) return pts; const d = (p, a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1]; const l = dx * dx + dy * dy || 1; const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l)); return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)); }; let mx = 0, mi = 0; for (let i = 1; i < pts.length - 1; i++) { const q = d(pts[i], pts[0], pts[pts.length - 1]); if (q > mx) { mx = q; mi = i; } } if (mx <= tol) return [pts[0], pts[pts.length - 1]]; return [...simplify(pts.slice(0, mi + 1), tol).slice(0, -1), ...simplify(pts.slice(mi), tol)]; }
/* ---- a Catmull-Rom spline as cubic Bézier segments */
function splinePath(pts, tension = 0.5, closed = false) { if (pts.length < 2) return ''; const P = closed ? [pts[pts.length - 1], ...pts, pts[0], pts[1]] : [pts[0], ...pts, pts[pts.length - 1]]; let d = `M${P[1][0]},${P[1][1]}`; for (let i = 1; i < P.length - 2; i++) { const p0 = P[i - 1], p1 = P[i], p2 = P[i + 1], p3 = P[i + 2]; const k = tension / 3 * 2; d += `C${p1[0] + (p2[0] - p0[0]) * k / 2},${p1[1] + (p2[1] - p0[1]) * k / 2} ${p2[0] - (p3[0] - p1[0]) * k / 2},${p2[1] - (p3[1] - p1[1]) * k / 2} ${p2[0]},${p2[1]}`; } return d + (closed ? 'Z' : ''); }
/* ---- wave function collapse on a small grid, with a tileset of adjacency rules */
const WFC_SETS = { coast: { tiles: ['water', 'shore', 'land'], ok: { water: ['water', 'shore'], shore: ['water', 'shore', 'land'], land: ['shore', 'land'] } }, caves: { tiles: ['rock', 'wall', 'floor'], ok: { rock: ['rock', 'wall'], wall: ['rock', 'wall', 'floor'], floor: ['wall', 'floor'] } } };
function wfc(w, h, setName, seed) {
  const S = WFC_SETS[setName]; const R = rng(seed);
  for (let attempt = 0; attempt < 30; attempt++) {
    const g = Array.from({ length: w * h }, () => new Set(S.tiles)); let ok = true;
    const nb = (i) => { const x = i % w, y = (i / w) | 0; return [x > 0 && i - 1, x < w - 1 && i + 1, y > 0 && i - w, y < h - 1 && i + w].filter((n) => n !== false); };
    const prop = (start) => { const q = [start]; while (q.length) { const i = q.pop(); for (const n of nb(i)) { const allowed = new Set(); g[i].forEach((t) => S.ok[t].forEach((u) => allowed.add(u))); const before = g[n].size; g[n] = new Set([...g[n]].filter((t) => allowed.has(t))); if (g[n].size === 0) return false; if (g[n].size < before) q.push(n); } } return true; };
    while (true) { let best = -1, be = 99; g.forEach((s, i) => { if (s.size > 1 && s.size + R() * 0.1 < be) { be = s.size + R() * 0.1; best = i; } }); if (best < 0) break; const opts = [...g[best]]; g[best] = new Set([opts[Math.floor(R() * opts.length)]]); if (!prop(best)) { ok = false; break; } }
    if (ok) return g.map((s) => [...s][0]);
    seed += 7919;
  }
  return null;
}
/* ---- history: each step has a name, and a person can step to any of them */
function snap() { return JSON.stringify({ p: PL[MP.map], h: MP.height }); }
function histInit() { MP.hist = [{ n: 'Opened the Map', s: snap() }]; MP.hi = 0; }
function histPush(name) { MP.hist = MP.hist.slice(0, MP.hi + 1); MP.hist.push({ n: name, s: snap() }); MP.hi = MP.hist.length - 1; announce(name); }
function histGo(i) { if (i < 0 || i >= MP.hist.length) return; MP.hi = i; const o = JSON.parse(MP.hist[i].s); PL[MP.map] = o.p; MP.height = o.h; MP.sel = MP.sel && placeOf(MP.sel) ? MP.sel : null; announce('Went to: ' + MP.hist[i].n); }
function announce(t) { let l = $('#mp-live'); if (!l) { l = document.createElement('div'); l.id = 'mp-live'; l.className = 'sr-only'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = t; }
const fx = (n) => Math.round(n * 100) / 100;

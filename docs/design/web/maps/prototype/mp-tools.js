/* Maps: the tool registry, the drawing interactions, the generators and the command line.
   A tool is a declaration. The header, the options bar, the palette, the key map and the command line are all drawn from this list (MP6). */
const GROUPS = ['Select', 'Place', 'Draw', 'Terrain', 'Generate'];
const TOOLDEF = [
  { id: 'select', g: 'Select', n: 'Select', icon: 'tool-select', key: 'V', input: 'a click, or a drag for a box', out: 'nothing', opts: [] },
  { id: 'pin', g: 'Place', n: 'Pin', icon: 'pin', key: 'P', input: 'one click', out: 'a pin', opts: ['entry', 'role'] },
  { id: 'circle', g: 'Place', n: 'Circle', icon: 'tool-circle', key: 'C', input: 'a click for the centre, a click for the edge', out: 'a circle', opts: ['entry', 'role'] },
  { id: 'line', g: 'Draw', n: 'Line', icon: 'tool-line', key: 'L', input: 'a click for each point, Enter to finish', out: 'a line', opts: ['entry', 'role', 'style'], min: 2 },
  { id: 'spline', g: 'Draw', n: 'Spline', icon: 'route', key: 'S', input: 'a click for each point, Enter to finish', out: 'a smooth curve through the points', opts: ['entry', 'role', 'tension'], min: 2 },
  { id: 'freehand', g: 'Draw', n: 'Freehand', icon: 'edit', key: 'F', input: 'drag the pointer', out: 'a line, simplified as you set', opts: ['entry', 'role', 'smoothing'] },
  { id: 'area', g: 'Draw', n: 'Area', icon: 'tool-area', key: 'A', input: 'a click for each point, Enter to finish', out: 'an area', opts: ['entry', 'role'], min: 3, closed: true },
  { id: 'cells', g: 'Draw', n: 'Cells', icon: 'grid', key: 'G', input: 'click or drag over cells', out: 'a region of whole cells', opts: ['entry', 'role'], needs: 'grid' },
  { id: 'contour', g: 'Terrain', n: 'Height line', icon: 'timeline', key: 'T', input: 'a click for each point, Enter to finish', out: 'a line that carries a value', opts: ['entry', 'value', 'unit'], min: 2 },
  { id: 'height', g: 'Terrain', n: 'Height brush', icon: 'layers', key: 'H', input: 'drag to raise, Alt to lower', out: 'a heightmap', opts: ['radius', 'strength'], planned: 'A heightmap is a raster, and the Map holds none today. It needs its own decision before it is built. The height lines it makes are ordinary lines.' },
  { id: 'cave', g: 'Generate', n: 'Cave system', icon: 'kind-location', key: '', input: 'a region: the selected Area, or the whole sheet', out: 'areas', opts: ['size', 'density', 'smooth', 'seed', 'split'], gen: true },
  { id: 'march', g: 'Generate', n: 'Fill by marching squares', icon: 'filter', key: '', input: 'a region', out: 'areas, and optionally height lines', opts: ['scale', 'threshold', 'lines', 'seed', 'split'], gen: true },
  { id: 'wfc', g: 'Generate', n: 'Fill by wave function collapse', icon: 'kind-group-items', key: '', input: 'a region of a grid', out: 'cells, by tile', opts: ['tileset', 'seed', 'split'], gen: true, needs: 'grid' }
];
const tdef = (id) => TOOLDEF.find((t) => t.id === id);
const DEFKEYS = Object.fromEntries(TOOLDEF.map((t) => [t.id, t.key]));
(() => { try { const k = JSON.parse(localStorage.getItem('mp-keys') || 'null'); if (k) TOOLDEF.forEach((t) => { if (k[t.id] !== undefined) t.key = k[t.id]; }); } catch (e) { /* storage may be unavailable */ } })();
function saveKeys() { try { localStorage.setItem('mp-keys', JSON.stringify(Object.fromEntries(TOOLDEF.map((t) => [t.id, t.key])))); } catch (e) { /* ignore */ } }
const OPTDEF = {
  entry: { l: 'Drawing', t: 'text', d: '' }, role: { l: 'Role', t: 'select', c: ['none', 'site', 'road', 'wall', 'water', 'cave'], d: 'none' }, style: { l: 'Line', t: 'seg', c: ['Solid', 'Dashed', 'Dotted'], d: 'Solid' },
  tension: { l: 'Tension', t: 'range', min: 0, max: 1, step: 0.05, d: 0.5 }, smoothing: { l: 'Smoothing', t: 'range', min: 0, max: 20, step: 1, d: 6 }, value: { l: 'Height', t: 'number', d: 100 }, unit: { l: 'Unit', t: 'text', d: 'm' },
  radius: { l: 'Radius', t: 'range', min: 4, max: 60, step: 1, d: 24 }, strength: { l: 'Strength', t: 'range', min: 1, max: 10, step: 1, d: 4 },
  size: { l: 'Size', t: 'range', min: 20, max: 90, step: 1, d: 48 }, density: { l: 'Density', t: 'range', min: 0.3, max: 0.6, step: 0.01, d: 0.46 }, smooth: { l: 'Smooth', t: 'range', min: 0, max: 8, step: 1, d: 4 },
  scale: { l: 'Scale', t: 'range', min: 2, max: 20, step: 1, d: 8 }, threshold: { l: 'Level', t: 'range', min: 0.2, max: 0.8, step: 0.01, d: 0.5 }, lines: { l: 'Height lines', t: 'toggle', d: true }, tileset: { l: 'Tiles', t: 'select', c: ['coast', 'caves'], d: 'coast' },
  seed: { l: 'Seed', t: 'seed', d: 4821 }, split: { l: 'Compare', t: 'toggle', d: false }
};
const optv = (tool, k) => { const o = MP.opt[tool]; return o && k in o ? o[k] : OPTDEF[k].d; };
const gridMap = () => !!curMap().cell;
const toolOK = (t) => !t.needs || (t.needs === 'grid' && gridMap());
/* ---- coordinates, snapping */
function toMap(e) { const svg = $('#mapsvg'); if (!svg) return null; const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const m = svg.getScreenCTM(); if (!m) return null; const p = pt.matrixTransform(m.inverse()); return snapPt([p.x, p.y]); }
function toMapRaw(e) { const svg = $('#mapsvg'); if (!svg) return null; const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const m = svg.getScreenCTM(); if (!m) return null; const p = pt.matrixTransform(m.inverse()); return [p.x, p.y]; }
function snapPt(p) { const m = curMap(); const g = m.cell || 5; const q = MP.snap ? [Math.round(p[0] / (m.cell ? g / 2 : g)) * (m.cell ? g / 2 : g), Math.round(p[1] / (m.cell ? g / 2 : g)) * (m.cell ? g / 2 : g)] : [fx(p[0]), fx(p[1])]; return [Math.max(0, Math.min(m.w, q[0])), Math.max(0, Math.min(m.h, q[1]))]; }
const cellOf = (p) => [Math.floor(p[0] / curMap().cell), Math.floor(p[1] / curMap().cell)];
/* ---- creating placements: an undoable, named step */
function ensureEntry(name) { let l = LOCS.find((x) => x.n === name); if (!l) { l = { id: 'l-' + uid(), n: name, parent: curMap().shows || null, open: false, tie: [] }; LOCS.push(l); } return l; }
function addPlacement(p, label) { const t = tdef(p.tool || MP.tool); p.id = 'p-' + uid(); p.order = places().length + 1; p.layer = p.layer || (p.role === 'road' ? 'Roads' : p.role === 'water' || p.k === 'contour' ? 'Terrain' : 'Places'); const l = ensureEntry(p.ent); p.loc = l.id; places().push(p); MP.sel = p.id; histPush(label || `Drew “${p.ent}”`); return p; }
function entryName(t) { return (optv(t.id, 'entry') || '').trim() || `${t.n} ${places().length + 1}`; }
function mk(k, pts, extra = {}) { const t = tdef(MP.tool); return Object.assign({ ent: entryName(t), k, role: optv(t.id, 'role') === 'none' ? '' : optv(t.id, 'role'), pts, style: optv(t.id, 'style') || 'Solid', tool: t.id }, extra); }
function finishDraft() {
  const d = MP.draft; if (!d) return; const t = tdef(MP.tool);
  if (d.pts.length < (t.min || 2)) { cmdOut(`A ${t.n.toLowerCase()} needs ${t.min} points. Nothing was made.`, 'err'); return; }
  const base = { line: 'line', spline: 'spline', area: 'area', contour: 'contour' }[t.id];
  const p = mk(base, d.pts.slice(), t.id === 'spline' ? { tension: optv('spline', 'tension') } : t.id === 'contour' ? { value: Number(optv('contour', 'value')), unit: optv('contour', 'unit'), role: '', layer: 'Terrain' } : {});
  MP.draft = null; addPlacement(p, `Drew a ${t.n.toLowerCase()}, “${p.ent}”`); cvRedraw(); sideRedraw();
}
function cancelDraft() { MP.draft = null; MP.preview && !tdef(MP.tool).gen && (MP.preview = null); ovRedraw(); }
/* ---- generators: they preview as an overlay and write nothing until Apply */
function region() { const m = curMap(); const s = MP.sel && placeOf(MP.sel); if (s && s.k === 'area') { const xs = s.pts.map((p) => p[0]), ys = s.pts.map((p) => p[1]); return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys), named: s.ent }; } return { x: 0, y: 0, w: m.w, h: m.h, named: 'the whole sheet' }; }
function inside(pt, poly) { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { if ((poly[i][1] > pt[1]) !== (poly[j][1] > pt[1]) && pt[0] < ((poly[j][0] - poly[i][0]) * (pt[1] - poly[i][1])) / (poly[j][1] - poly[i][1]) + poly[i][0]) c = !c; } return c; }
function runGen(id) {
  const R = region(); const seed = Number(optv(id, 'seed')) || 1; const out = { id, seed, R, areas: [], lines: [], cells: null, note: '' };
  const toMapPts = (loop, gw, gh) => loop.map((p) => [fx(R.x + ((p[0] + 0.5) / gw) * R.w), fx(R.y + ((p[1] + 0.5) / gh) * R.h)]);
  if (id === 'cave') {
    const gw = Number(optv('cave', 'size')), gh = Math.max(12, Math.round(gw * R.h / R.w)); const r = rng(seed); let g = Array.from({ length: gw * gh }, (_, i) => { const x = i % gw, y = (i / gw) | 0; return x === 0 || y === 0 || x === gw - 1 || y === gh - 1 ? 0 : r() < Number(optv('cave', 'density')) ? 0 : 1; });
    for (let it = 0; it < Number(optv('cave', 'smooth')); it++) { g = g.map((v, i) => { const x = i % gw, y = (i / gw) | 0; if (x === 0 || y === 0 || x === gw - 1 || y === gh - 1) return 0; let n = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) n += g[(y + dy) * gw + x + dx] ? 0 : 1; return n >= 5 ? 0 : 1; }); }
    const f = Float32Array.from(g); const loops = marchingLoops(f, gw, gh, 0.5).filter((l) => l.length > 8); out.areas = loops.map((l) => simplify(toMapPts(l, gw, gh), Math.max(R.w, R.h) / 400)).filter((l) => l.length > 4);
    out.note = `${pl(out.areas.length, 'cave', 'caves')} in ${R.named}`;
  } else if (id === 'march') {
    const gw = 60, gh = Math.max(20, Math.round(60 * R.h / R.w)); const f = noiseField(gw, gh, Number(optv('march', 'scale')), seed); const th = Number(optv('march', 'threshold'));
    out.areas = marchingLoops(f, gw, gh, th).filter((l) => l.length > 6).map((l) => simplify(toMapPts(l, gw, gh), Math.max(R.w, R.h) / 300)).filter((l) => l.length > 3);
    if (optv('march', 'lines')) [th - 0.12, th + 0.12].forEach((lv, k) => marchingLoops(f, gw, gh, lv).filter((l) => l.length > 6).forEach((l) => out.lines.push({ pts: simplify(toMapPts(l, gw, gh), Math.max(R.w, R.h) / 300), value: (k === 0 ? 50 : 150) }))); out.note = `${pl(out.areas.length, 'area', 'areas')}${out.lines.length ? ' and ' + pl(out.lines.length, 'height line', 'height lines') : ''} in ${R.named}`;
  } else if (id === 'wfc') {
    const c = curMap().cell; const cw = Math.max(2, Math.round(R.w / c)), ch = Math.max(2, Math.round(R.h / c)); const g = wfc(cw, ch, optv('wfc', 'tileset'), seed); if (!g) { out.note = 'No tiling fits these rules at this size. Try another seed.'; out.cells = []; return out; }
    out.cells = g.map((t, i) => ({ t, x: Math.round(R.x / c) + (i % cw), y: Math.round(R.y / c) + ((i / cw) | 0) })); out.note = `${cw} by ${ch} cells in ${R.named}`;
  }
  return out;
}
function setPreview() { const t = tdef(MP.tool); if (!t.gen || !toolOK(t)) { MP.preview = null; return; } MP.preview = runGen(t.id); }
function applyPreview() {
  const P = MP.preview; if (!P) return; const t = tdef(P.id);
  if (P.id === 'wfc') { const by = {}; P.cells.forEach((c) => { (by[c.t] = by[c.t] || []).push(`${c.x},${c.y}`); }); Object.entries(by).filter(([k]) => !['water', 'rock'].includes(k)).forEach(([k, cs]) => { const p = { tool: 'wfc', ent: `${entryName(t)} ${k}`, k: 'cells', role: k === 'floor' ? 'cave' : 'site', cells: cs, pts: [], layer: 'Places' }; p.id = 'p-' + uid(); p.order = places().length + 1; p.loc = ensureEntry(p.ent).id; places().push(p); }); histPush(`Filled by wave function collapse (${optv('wfc', 'tileset')}, seed ${P.seed})`); }
  else { const first = P.areas[0]; if (!first && !P.lines.length) { cmdOut('Nothing to apply. Try another seed.', 'err'); return; } if (first) { const p = { tool: P.id, ent: entryName(t), k: 'area', role: P.id === 'cave' ? 'cave' : 'site', pts: first, parts: P.areas.slice(1), layer: 'Places' }; p.id = 'p-' + uid(); p.order = places().length + 1; p.loc = ensureEntry(p.ent).id; places().push(p); MP.sel = p.id; } P.lines.forEach((l, i) => { const p = { tool: P.id, ent: `${entryName(t)} height line ${i + 1}`, k: 'contour', value: l.value, unit: 'm', pts: l.pts, layer: 'Terrain' }; p.id = 'p-' + uid(); p.order = places().length + 1; p.loc = ensureEntry(p.ent).id; places().push(p); }); histPush(`${t.n}, seed ${P.seed}: ${P.note}`); }
  MP.preview = null; cvRedraw(); sideRedraw(); optRedraw();
}
function roll() { const t = tdef(MP.tool); MP.opt[t.id] = Object.assign(MP.opt[t.id] || {}, { seed: Math.floor(Math.random() * 90000) + 1 }); setPreview(); ovRedraw(); optRedraw(); }
/* ---- heights (planned): a raster the Map does not hold; drawn so the tool has a place */
function paintHeight(p, lower) { const m = curMap(); const w = 60, h = 40; MP.height = MP.height || { w, h, d: new Array(w * h).fill(0) }; const r = Number(optv('height', 'radius')) / 10, s = Number(optv('height', 'strength')) / 40 * (lower ? -1 : 1); const cx = p[0] / m.w * w, cy = p[1] / m.h * h; for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const d2 = (x - cx) ** 2 + (y - cy) ** 2; if (d2 < r * r * 4) MP.height.d[y * w + x] = Math.max(0, Math.min(1, MP.height.d[y * w + x] + s * Math.exp(-d2 / (r * r)))); } MP.layers.Height = true; }
/* ---- the command line: the same actions as the tools, typed */
function cmdOut(t, kind = '') { MP.cmd.push({ t, kind }); if (MP.cmd.length > 40) MP.cmd.shift(); const l = $('#cmd-h'); if (l) { l.innerHTML = cmdHTML(); l.scrollTop = l.scrollHeight; } }
const cmdHTML = () => MP.cmd.slice(-4).map((c) => `<li class="${c.kind}">${esc(c.t)}</li>`).join('');
function cmdPrompt() { const d = MP.draft; const t = tdef(MP.tool); if (d) return `${t.n.toUpperCase()}  Next point (x,y), [C]lose, Enter to finish, [U]ndo point:`; if (MP.preview) return `${t.n.toUpperCase()}  [R]oll another seed, [A]pply, [D]iscard, or SEED n:`; return t.gen ? `${t.n.toUpperCase()}  Press Enter to preview:` : 'Command:'; }
function runCommand(line) {
  const raw = line.trim(); cmdOut(`${cmdPrompt().split('  ')[0]}${raw ? ' ' + raw : ''}`);
  const parts = raw.split(/\s+/).filter(Boolean); const w = (parts[0] || '').toLowerCase(); const xy = (s) => { const m = /^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/.exec(s || ''); return m ? [Number(m[1]), Number(m[2])] : null; };
  const ptsOf = (a) => a.map(xy).filter(Boolean);
  if (!raw) { if (MP.draft) finishDraft(); else if (tdef(MP.tool).gen) { setPreview(); ovRedraw(); optRedraw(); cmdOut(MP.preview ? `Preview: ${MP.preview.note}. Seed ${MP.preview.seed}.` : 'This tool needs a grid Map.'); } return; }
  if (MP.draft && xy(w)) { const p = snapPt(xy(w)); MP.draft.pts.push(p); cmdOut(`Point ${MP.draft.pts.length}: ${p[0]},${p[1]}`); ovRedraw(); return; }
  if (MP.draft && (w === 'c' || w === 'close')) { cmdOut('Closed.'); finishDraft(); return; }
  if (MP.draft && (w === 'u' || w === 'undo')) { MP.draft.pts.pop(); cmdOut('Took back a point.'); ovRedraw(); return; }
  if (MP.preview && (w === 'r' || w === 'roll')) { roll(); cmdOut(`Seed ${MP.preview.seed}: ${MP.preview.note}`); return; }
  if (MP.preview && (w === 'a' || w === 'apply')) { applyPreview(); cmdOut('Applied.'); return; }
  if (MP.preview && (w === 'd' || w === 'discard')) { MP.preview = null; ovRedraw(); optRedraw(); cmdOut('Discarded. Nothing was written.'); return; }
  if (w === 'seed' && parts[1]) { MP.opt[MP.tool] = Object.assign(MP.opt[MP.tool] || {}, { seed: Number(parts[1]) }); setPreview(); ovRedraw(); optRedraw(); cmdOut(MP.preview ? `Seed ${parts[1]}: ${MP.preview.note}` : 'Set.'); return; }
  const t = TOOLDEF.find((x) => x.n.toLowerCase() === raw.toLowerCase() || x.id === w);
  if (w === 'undo') { histGo(MP.hi - 1); cvRedraw(); sideRedraw(); cmdOut('Undone.'); return; } if (w === 'redo') { histGo(MP.hi + 1); cvRedraw(); sideRedraw(); cmdOut('Redone.'); return; }
  if (w === 'fit') { MP.vp = { x: 0, y: 0, k: 1 }; cvRedraw(); cmdOut('Framed the whole sheet.'); return; }
  if (w === 'help') { cmdOut('Tools: ' + TOOLDEF.map((x) => x.id).join(', ') + '. Commands: undo, redo, fit, seed n, select <name>.'); return; }
  if (w === 'select') { const n = parts.slice(1).join(' ').toLowerCase(); const p = places().find((x) => x.ent.toLowerCase() === n); if (p) { MP.sel = p.id; cvRedraw(); sideRedraw(); cmdOut(`Selected “${p.ent}”.`); } else cmdOut(`Nothing named “${parts.slice(1).join(' ')}” on this Map.`, 'err'); return; }
  if (t) { if (t.planned) { cmdOut(`${t.n} is planned: ${t.planned}`, 'err'); return; } if (!toolOK(t)) { cmdOut(`${t.n} needs a grid Map.`, 'err'); return; } setTool(t.id); const pts = ptsOf(parts.slice(1)); if (pts.length) { if (t.id === 'pin') { addPlacement(mk('pin', [snapPt(pts[0])])); cvRedraw(); sideRedraw(); } else if (t.id === 'circle' && pts[1]) { const p = mk('circle', [snapPt(pts[0])], { r: Math.round(Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) * 100) / 100 }); addPlacement(p); cvRedraw(); sideRedraw(); } else if (t.min) { MP.draft = { pts: pts.map(snapPt) }; finishDraft(); } } else cmdOut(`${t.n}: ${t.input}.`); return; }
  cmdOut(`“${raw}” is not a command here. Type help.`, 'err');
}
/* ---- tools: choosing, the key map, and the canvas */
function setTool(id) { const t = tdef(id); if (!t) return; if (t.planned) { toast({ title: `${t.n} is planned`, text: t.planned }); } if (!toolOK(t)) { toast({ kind: 'error', title: `${t.n} needs a grid Map`, text: 'This Map has no cells.' }); return; } MP.tool = id; MP.draft = null; MP.gtool = MP.gtool || {}; MP.gtool[t.g] = id; MP.preview = null; if (t.gen) setPreview(); headRedraw(); optRedraw(); ovRedraw(); cmdOut(`Tool: ${t.n}. ${t.input}.`); }
function keyTool(e) {
  const tag = (e.target.tagName || '').toLowerCase(); if (['input', 'select', 'textarea'].includes(tag) || e.target.isContentEditable) return false; if (!/^edit/.test(S.route)) return false;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); histGo(MP.hi + (e.shiftKey ? 1 : -1)); cvRedraw(); sideRedraw(); return true; }
  if (e.key === '/' || e.key === ':') { e.preventDefault(); const i = $('#cmd-in'); i && i.focus(); return true; }
  if (e.key === 'Escape') { if (MP.draft || MP.preview) { MP.draft = null; MP.preview = null; ovRedraw(); optRedraw(); cmdOut('Cancelled.'); } else { MP.sel = null; cvRedraw(); sideRedraw(); } return true; }
  if (e.key === 'Enter') { if (MP.draft) { finishDraft(); return true; } if (MP.preview) { applyPreview(); return true; } }
  if (e.key === 'Backspace' && MP.draft) { MP.draft.pts.pop(); ovRedraw(); return true; }
  if (e.key === 'Home') { MP.vp = { x: 0, y: 0, k: 1 }; cvRedraw(); return true; }
  if ((e.key === 'Delete' || e.key === 'Backspace') && MP.sel && !MP.draft) { const p = placeOf(MP.sel); PL[MP.map] = places().filter((x) => x.id !== MP.sel); histPush(`Deleted “${p.ent}”`); MP.sel = null; cvRedraw(); sideRedraw(); return true; }
  if (e.key.startsWith('Arrow') && MP.sel && !MP.draft) { e.preventDefault(); const p = placeOf(MP.sel); const st = (curMap().cell || 1) * (e.shiftKey ? 5 : 1) / (curMap().cell ? 1 : 1); const dx = e.key === 'ArrowLeft' ? -st : e.key === 'ArrowRight' ? st : 0, dy = e.key === 'ArrowUp' ? -st : e.key === 'ArrowDown' ? st : 0; p.pts = p.pts.map((q) => [fx(q[0] + dx), fx(q[1] + dy)]); if (p.cells) p.cells = p.cells.map((c) => { const [a, b] = c.split(',').map(Number); return `${a + Math.sign(dx)},${b + Math.sign(dy)}`; }); histPush(`Moved “${p.ent}”`); cvRedraw(); sideRedraw(); return true; }
  const t = TOOLDEF.find((x) => x.key && x.key.toLowerCase() === e.key.toLowerCase() && !e.ctrlKey && !e.metaKey); if (t) { setTool(t.id); return true; } return false;
}
let drag = null;
function cvDown(e) {
  if (!canWrite() || !/^edit/.test(S.route)) return; const svg = $('#mapsvg'); if (!svg || !svg.contains(e.target)) return; const ae = document.activeElement; if (ae && /^(input|select|textarea)$/i.test(ae.tagName)) ae.blur(); const t = tdef(MP.tool); const p = toMap(e); if (!p) return;
  if (e.target.closest && e.target.closest('[data-splith]')) { drag = { split: true }; return; }
  if (e.button === 1 || e.spaceKey || MP.space) { drag = { pan: true, x: e.clientX, y: e.clientY, vp: { ...MP.vp } }; return; }
  if (e.button !== 0 || t.planned && t.id !== 'height' || !toolOK(t) || t.gen) return;
  if (t.id === 'select') { const hit = e.target.closest('[data-pid]'); MP.sel = hit ? hit.dataset.pid : null; cvRedraw(); sideRedraw(); return; }
  if (t.id === 'pin') { addPlacement(mk('pin', [p])); cvRedraw(); sideRedraw(); return; }
  if (t.id === 'circle') { if (!MP.draft) { MP.draft = { pts: [p], circle: true }; } else { const c = MP.draft.pts[0]; addPlacement(mk('circle', [c], { r: fx(Math.hypot(p[0] - c[0], p[1] - c[1])) })); MP.draft = null; cvRedraw(); sideRedraw(); } ovRedraw(); return; }
  if (['line', 'spline', 'area', 'contour'].includes(t.id)) { if (!MP.draft) MP.draft = { pts: [] }; MP.draft.pts.push(p); ovRedraw(); return; }
  if (t.id === 'freehand') { drag = { free: true, pts: [p] }; MP.draft = { pts: [p], free: true }; ovRedraw(); return; }
  if (t.id === 'cells') { const c = cellOf(p); drag = { cells: true, set: new Set([c.join(',')]) }; MP.draft = { cells: drag.set }; ovRedraw(); return; }
  if (t.id === 'height') { drag = { height: true, lower: e.altKey }; paintHeight(p, e.altKey); cvRedraw(); return; }
}
function cvMove(e) {
  const svg = $('#mapsvg'); if (!svg) return;
  if (drag && drag.split) { const R = (MP.preview || {}).R; const pt = toMapRaw(e); if (R && pt) { MP.splitAt = Math.max(0.05, Math.min(0.95, (pt[0] - R.x) / R.w)); ovRedraw(); } return; }
  if (drag && drag.pan) { const k = MP.vp.k; const m = svg.getScreenCTM(); const sc = m ? m.a : 1; MP.vp.x = drag.vp.x - (e.clientX - drag.x) / sc; MP.vp.y = drag.vp.y - (e.clientY - drag.y) / sc; applyVB(); return; }
  const p = toMap(e); if (!p) return; MP.ov.pointer = p; const st = $('#sb-xy'); if (st) st.textContent = `${p[0].toFixed(2)}, ${p[1].toFixed(2)} ${curMap().unit}`;
  if (drag && drag.free) { const l = drag.pts[drag.pts.length - 1]; if (Math.hypot(p[0] - l[0], p[1] - l[1]) > 1) { drag.pts.push(p); MP.draft.pts = drag.pts; } }
  if (drag && drag.cells) { const c = cellOf(p).join(','); drag.set.add(c); }
  if (drag && drag.height) paintHeight(p, drag.lower);
  if (!drag || !drag.height) ovRedraw(); else cvRedraw();
}
function cvUp() {
  if (!drag) return; const d = drag; drag = null;
  if (d.free) { const t = tdef('freehand'); const pts = simplify(d.pts, Number(optv('freehand', 'smoothing')) / 4); MP.draft = null; if (pts.length >= 2) { addPlacement(mk('line', pts, { role: optv('freehand', 'role') === 'none' ? '' : optv('freehand', 'role') }), `Drew a freehand line (${d.pts.length} samples, ${pts.length} points)`); } cvRedraw(); sideRedraw(); }
  if (d.cells) { MP.draft = null; const arr = [...d.set]; const sel = MP.sel && placeOf(MP.sel); if (sel && sel.k === 'cells') { arr.forEach((c) => { if (!sel.cells.includes(c)) sel.cells.push(c); }); histPush(`Added cells to “${sel.ent}”`); } else addPlacement(mk('cells', [], { cells: arr }), `Drew ${pl(arr.length, 'cell', 'cells')}`); cvRedraw(); sideRedraw(); }
  if (d.height) { histPush('Painted heights (planned tool, not stored)'); sideRedraw(); }
}
function cvDbl(e) { if (MP.draft && ['line', 'spline', 'area', 'contour'].includes(MP.tool)) { MP.draft.pts.pop(); finishDraft(); } }
function cvWheel(e) { const svg = $('#mapsvg'); if (!svg || !svg.contains(e.target)) return; e.preventDefault(); const f = e.deltaY < 0 ? 1.15 : 1 / 1.15; zoomAt(e, f); }
function zoomAt(e, f) { const svg = $('#mapsvg'); const before = e ? (() => { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; return pt.matrixTransform(svg.getScreenCTM().inverse()); })() : null; MP.vp.k = Math.max(0.5, Math.min(12, MP.vp.k * f)); applyVB(); if (before) { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const after = pt.matrixTransform(svg.getScreenCTM().inverse()); MP.vp.x += before.x - after.x; MP.vp.y += before.y - after.y; applyVB(); } const z = $('#sb-zoom'); if (z) z.textContent = Math.round(MP.vp.k * 100) + '%'; }
function applyVB() { const svg = $('#mapsvg'); if (!svg) return; const m = curMap(); const w = m.w || 600, h = m.h || 400; svg.setAttribute('viewBox', `${MP.vp.x} ${MP.vp.y} ${w / MP.vp.k} ${h / MP.vp.k}`); }
document.addEventListener('pointerdown', cvDown); document.addEventListener('pointermove', cvMove); document.addEventListener('pointerup', cvUp); document.addEventListener('dblclick', cvDbl); document.addEventListener('wheel', cvWheel, { passive: false });
document.addEventListener('keydown', (e) => { if (e.code === 'Space' && !/^(input|select|textarea)$/i.test(e.target.tagName)) { if (/^edit/.test(S.route)) { MP.space = true; e.preventDefault(); } } }); document.addEventListener('keyup', (e) => { if (e.code === 'Space') MP.space = false; });

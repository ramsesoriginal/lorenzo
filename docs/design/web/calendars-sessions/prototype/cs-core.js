/* Calendars and Sessions: state and calendar arithmetic. The API calculates in the real app; here it is a few lines. */
const CS = { role: 'GM', clocks: true, y: 4, sg: 3, day: 22, view: 'month', acct: 'busy', cal: 'one', hid: {}, fold: {}, viewName: 'Prepare', views: { Prepare: ['details', 'roster', 'notes', 'scenes', 'time'], Played: ['played', 'notes', 'scenes'], All: ['details', 'roster', 'notes', 'refs', 'time', 'scenes', 'played', 'order', 'lived'] }, seq: 0, tf: null, ses: 's7', fl: { who: '', when: null, cause: '', order: false } };
const parts = () => S.route.split('/');
const pl = (n, a, b) => `${n} ${n === 1 ? a : b}`;
const fmt = (n) => Number(n).toLocaleString('en');
const segPresent = (i, y) => { const s = CAL.seg[i]; return s.k !== 'leap' || (y % s.every) === s.rem; };
const segDays = (i, y) => (segPresent(i, y) ? CAL.seg[i].d : 0);
const keyOf = (y, sg, d) => `${y}/${sg}/${d}`;
const unkey = (k) => { const [y, sg, d] = k.split('/').map(Number); return { y, sg, d }; };
const dpy = (y) => CAL.seg.reduce((s, _, i) => s + segDays(i, y), 0);
const dayOfYear = (y, sg, d) => { let n = 0; for (let i = 0; i < sg; i++) n += segDays(i, y); return n + d; };
const gday = (y, sg, d) => { let n = 0; for (let k = 1; k < y; k++) n += dpy(k); return n + dayOfYear(y, sg, d); };
const dateName = (k) => { const { y, sg, d } = unkey(k); return `${CAL.seg[sg].n} ${d}, Year ${y}`; };
const longDate = (k) => dateName(k);
const MOON = ['moon-new', 'moon-waxing-crescent', 'moon-first-quarter', 'moon-waxing-gibbous', 'moon-full', 'moon-waning-gibbous', 'moon-last-quarter', 'moon-waning-crescent'];
const MOON_NAME = ['New', 'Waxing crescent', 'First quarter', 'Waxing gibbous', 'Full', 'Waning gibbous', 'Last quarter', 'Waning crescent'];
const phase = (m, y, sg, d) => Math.floor((((gday(y, sg, d) + m.off) % m.cycle) / m.cycle) * 8) % 8;
const obsOn = (sg, d) => CAL.obs.filter((o) => (o.segs === 'all' ? CAL.seg[sg].k !== 'leap' && CAL.seg[sg].k !== 'festival' : o.segs.includes(sg)) && d % o.every === 0);
const evOn = (k) => EV.filter((e) => e.dates.includes(k));
const factsOn = (k) => FACTS.filter((f) => f.dates.includes(k));
const sessOn = (k) => SESS.filter((s) => s.start === k || s.covers.includes(k));
const notesOn = (k) => (CAL.periods[k] ? CAL.periods[k].notes : []);
/* what a reader may see: Restricted Events are for GMs and Authors only; Participants for participants; Everyone for all */
const canSee = (e) => CS.role === 'GM' || e.aud === 'everyone' || (e.aud === 'participants' && CS.role === 'Player' && e.part.some((p) => ['mara'].includes(p)));
const marksOf = (k) => { const { sg, d } = unkey(k); const m = []; sessOn(k).filter((x) => (window.mySess ? mySess().includes(x) : true)).forEach(() => m.push('kind-session')); evOn(k).filter(canSee).forEach(() => m.push('kind-event')); factsOn(k).forEach(() => m.push('kind-fact')); obsOn(sg, d).forEach(() => m.push('kind-calendar-repeat')); notesOn(k).forEach(() => m.push('kind-fact')); return m; };
const snapshot = () => JSON.stringify({ CAL: CAL.periods, EV, FACTS, ORD, SESS, SCENES, LIVED, CLOCKS });
function restore(s) { const o = JSON.parse(s); CAL.periods = o.CAL; EV.length = 0; EV.push(...o.EV); FACTS.length = 0; FACTS.push(...o.FACTS); ORD.length = 0; ORD.push(...o.ORD); SESS.length = 0; SESS.push(...o.SESS); SCENES.length = 0; SCENES.push(...o.SCENES); Object.keys(LIVED).forEach((k) => delete LIVED[k]); Object.assign(LIVED, o.LIVED); CLOCKS.length = 0; CLOCKS.push(...o.CLOCKS); }
function mutate(title, fn, text) { const snap = snapshot(); const r = fn(); if (r === false) return false; csRefresh(); withUndo(title, () => { restore(snap); csRefresh(); }, text); announce(title); return true; }
function announce(t) { let l = $('#cs-live'); if (!l) { l = document.createElement('div'); l.id = 'cs-live'; l.className = 'sr-only'; l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } l.textContent = t; }
function refuse(title, text) { toast({ kind: 'error', title, text }); announce(title + '. ' + (text || '')); return false; }
const uid = (() => { let n = 100; return () => 'x' + (n++).toString(36); })();
const canWrite = () => CS.role === 'GM';
const canAdd = () => CS.role === 'GM' || CS.role === 'Player';
const gm = (s) => CS.role === 'GM' && !s.mine;
/* the person's saved views are theirs alone: remembered in this browser, never shared */
const lsGet = (k) => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage may be unavailable */ } };
(() => { const v = lsGet('cs-views'); if (v) Object.assign(CS.views, v); })();

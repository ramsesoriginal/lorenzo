/* Calendars and Sessions: routes, the controls bar, and the wiring. */
const CSH = []; /* click handlers, tried in order */
const CSB = []; /* bind hooks, run after every draw */
function csClick(e) { for (const h of CSH) if (h(e)) return; calClick(e); }
function csKey(e) { if (window.tfKeys && tfKeys(e)) return; if (window.sesKeys && sesKeys(e)) return; calKeys(e); }
function csAfter() { const m = $('#main'); m.onclick = csClick; m.onkeydown = csKey; CSB.forEach((f) => f(m)); }
function csRefresh(keep) { const sc = $('#main'); const top = sc.scrollTop; const r = cur(); S.meta = r.meta ? r.meta() : ''; sc.innerHTML = r.render(); csAfter(); if (keep) sc.scrollTop = top; updateStatus(); }
window.INWORLD = () => { if (/^session\//.test(S.route)) { const s = SESS.find((x) => x.id === parts()[1]); if (s && s.start && !s.mine) return `In-world: ${dateName(s.start)}`; } return null; };
const R = (app, tab, render, meta) => ({ app, tab, render, after: csAfter, meta: meta || (() => '') });
window.ROUTES_EXT = {
  cal: R('calendars', 'cal', pCal, () => { const c = calCtx(); return CS.view === 'year' ? `Year ${c.y}` : `${CAL.seg[c.sg].n} ${c.d} · ${CAL.periods[c.k] ? 'period written' : 'no period yet'}`; })
};
window.START_ROUTE = 'cal';
window.GO_EXT = {};
DATA.apps.find((a) => a.id === 'calendars').route = 'cal'; DATA.apps.find((a) => a.id === 'sessions').route = 'sessions';
DATA.appTabs.calendars = [['Calendar', 'cal'], ['Events', 'events'], ['Clocks', 'clocks']];
DATA.appTabs.sessions = [['Home', 'sessions'], ['Scenes', 'scenes'], ['Lived order', 'lived']];
window.TAB_HIDE = (t) => t === 'clocks' && !CS.clocks;
const PBc = (k, v, t, on) => `<button type="button" data-p="${k}" data-v="${v}" aria-pressed="${on}">${t}</button>`;
window.PROTO_EXT = () => `<span class="group"><b>You are</b>${[['GM', 'A GM'], ['Player', 'A player'], ['Reader', 'A reader']].map(([v, t]) => PBc('csrole', v, t, CS.role === v)).join('')}</span><span class="group"><b>Library has clocks</b>${[['1', 'Yes'], ['0', 'No']].map(([v, t]) => PBc('csclocks', v, t, String(+CS.clocks) === v)).join('')}</span>`;
window.PROTO_SYNC = () => { $$('#proto [data-p]').forEach((b) => { const k = b.dataset.p, v = b.dataset.v; if (k === 'csrole') b.setAttribute('aria-pressed', CS.role === v); else if (k === 'csclocks') b.setAttribute('aria-pressed', String(+CS.clocks) === v); }); };
window.PROTO_CLICK = (k, v) => { if (k === 'csrole') { CS.role = v; csRefresh(true); renderHeader(); return true; } if (k === 'csclocks') { CS.clocks = v === '1'; renderHeader(); renderTabbar(); if (!CS.clocks && /^clock/.test(S.route)) go('cal'); return true; } return false; };

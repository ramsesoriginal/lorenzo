/* Writing: drag and drop, by pointer and by keyboard. Every gesture has a menu or a dialog twin (WR6). */
(function () {
  const live = document.createElement('div'); live.id = 'dnd-live'; live.className = 'sr-only'; live.setAttribute('aria-live', 'polite'); document.body.appendChild(live);
  let D = null;
  const srcOf = (g) => { const d = g.dataset; if (d.drag === 'row') return { type: 'row', node: d.node }; if (d.drag === 'item') return { type: 'item', parent: d.node, item: d.item }; return { type: 'sel' }; };
  document.addEventListener('pointerdown', (e) => {
    const g = e.target.closest && e.target.closest('.grip[data-drag]'); if (!g || e.button > 0) return;
    const src = srcOf(g); if (src.type === 'sel') { const s = getSelection(); const ed = s.anchorNode && s.anchorNode.parentElement && s.anchorNode.parentElement.closest('[data-edit]'); if (!ed) return; const blk = ed.closest('.blk'); const r = selRange(ed); src.node = blk.dataset.node; src.item = blk.dataset.item; src.from = r[0]; src.to = r[1]; src.text = s.toString(); }
    e.preventDefault(); D = { g, src, x0: e.clientX, y0: e.clientY, started: false, T: null };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up, { once: true }); window.addEventListener('pointercancel', cancel, { once: true }); window.addEventListener('keydown', escKey, true);
  });
  function start() {
    D.started = true; const f = frame(); const ghost = document.createElement('div'); ghost.className = 'dnd-ghost';
    const s = D.src; const label = s.type === 'row' ? N(s.node).title : s.type === 'sel' ? s.text.slice(0, 48) + '…' : (N(s.parent).items.find((i) => i.id === s.item) || {}).text ? N(s.parent).items.find((i) => i.id === s.item).text.slice(0, 48) + '…' : 'This block';
    ghost.innerHTML = `${ic(s.type === 'row' ? 'kind-chapter' : s.type === 'sel' ? 'kind-chapter-add' : 'drag')}<span>${esc(label)}</span>`; f.appendChild(ghost); D.ghost = ghost;
    const line = document.createElement('div'); line.id = 'dnd-line'; line.hidden = true; f.appendChild(line); D.line = line;
    const chip = document.createElement('div'); chip.id = 'dnd-chip'; chip.hidden = true; f.appendChild(chip); D.chip = chip;
    document.body.classList.add('is-dragging');
    const el = s.type === 'row' ? $(`.trow[data-node="${s.node}"], .childcard[data-child="${s.node}"]`) : s.type === 'item' ? $(`.blk[data-item="${s.item}"]`) : null; D.el = el; if (el) el.classList.add('dragging');
    if (s.type === 'row') { const c = ctx(); const p = parentOf(s.node); const prev = p && N(p.node).items.slice(0, p.index).reverse().find((i) => i.t === 'child'); if (prev) { const row = $(`.trow[data-node="${prev.ref}"]`); if (row) { const j = document.createElement('span'); j.className = 'joinz'; j.dataset.a = prev.ref; j.textContent = 'Join'; row.appendChild(j); D.join = j; } } }
    announce('Picked up. Drop it where the line shows, or press Escape to cancel.');
  }
  function target(x, y) {
    const s = D.src; const el = document.elementFromPoint(x, y); if (!el) return null; const c = ctx();
    const jz = el.closest('.joinz'); if (jz && s.type === 'row') return { kind: 'join', a: jz.dataset.a, el: jz.closest('.trow'), label: `Join into “${N(jz.dataset.a).title}”` };
    const row = el.closest('.trow[data-node]'); if (row && !row.classList.contains('add') && !row.classList.contains('cover')) {
      const r = row.getBoundingClientRect(); const rel = (y - r.top) / r.height; const node = row.dataset.node; const p = parentOf(node); const t = N(node).title;
      if (s.type === 'row' && isInside(node, s.node) && node === s.node) return { invalid: true, label: 'Can’t go inside itself' };
      const zone = rel < 0.28 ? 'before' : rel > 0.72 ? 'after' : 'into';
      let T = zone === 'into' ? { parent: node, index: N(node).items.length, label: `Inside “${t}”`, el: row, into: true } : { parent: p.node, index: p.index + (zone === 'after' ? 1 : 0), label: `${zone === 'after' ? 'After' : 'Before'} “${t}”`, el: row, edge: zone === 'after' ? 'bottom' : 'top' };
      if (s.type === 'row' && isInside(T.parent, s.node)) return { invalid: true, label: 'Can’t go inside itself' };
      return T;
    }
    const add = el.closest('.trow.add'); if (add) return { parent: c.root, index: N(c.root).items.length, label: 'At the end', el: add, edge: 'top' };
    if (s.type === 'sel') return null;
    const blk = el.closest('#wdoc .blk[data-item]'); if (blk) { const r = blk.getBoundingClientRect(); const before = y < r.top + r.height / 2; const node = blk.dataset.node; return { parent: node, index: itemPos(node, blk.dataset.item) + (before ? 0 : 1), label: 'Here', el: blk, edge: before ? 'top' : 'bottom' }; }
    return null;
  }
  function move(e) {
    if (!D) return; if (!D.started) { if (Math.hypot(e.clientX - D.x0, e.clientY - D.y0) < 5) return; start(); }
    const f = frame().getBoundingClientRect(); D.ghost.style.left = e.clientX - f.left + 12 + 'px'; D.ghost.style.top = e.clientY - f.top + 12 + 'px';
    $$('.drop-into').forEach((x) => x.classList.remove('drop-into'));
    const T = target(e.clientX, e.clientY); D.T = T && !T.invalid ? T : null;
    const ln = D.line, ch = D.chip; ln.hidden = true; ch.hidden = true;
    if (T) {
      ch.hidden = false; ch.textContent = T.label; ch.classList.toggle('no', !!T.invalid);
      ch.style.left = Math.min(f.width - 220, e.clientX - f.left + 16) + 'px'; ch.style.top = e.clientY - f.top + 38 + 'px';
      if (!T.invalid && T.el) { if (T.into || T.kind === 'join') T.el.classList.add('drop-into'); else { const r = T.el.getBoundingClientRect(); ln.hidden = false; ln.style.left = r.left - f.left + 'px'; ln.style.width = r.width + 'px'; ln.style.top = (T.edge === 'top' ? r.top : r.bottom) - f.top - 1 + 'px'; } }
    }
    const sc = $('#wscroll'); if (sc) { const r = sc.getBoundingClientRect(); if (e.clientY < r.top + 50) sc.scrollTop -= 14; else if (e.clientY > r.bottom - 50) sc.scrollTop += 14; }
    const tr = $('.wout .tree'); if (tr) { const r = tr.getBoundingClientRect(); if (e.clientX >= r.left && e.clientX <= r.right) { if (e.clientY < r.top + 40) tr.scrollTop -= 12; else if (e.clientY > r.bottom - 40) tr.scrollTop += 12; } }
  }
  function end() { window.removeEventListener('pointermove', move); window.removeEventListener('keydown', escKey, true); if (!D) return; D.ghost && D.ghost.remove(); D.line && D.line.remove(); D.chip && D.chip.remove(); D.join && D.join.remove(); D.el && D.el.classList.remove('dragging'); $$('.drop-into').forEach((x) => x.classList.remove('drop-into')); document.body.classList.remove('is-dragging'); }
  function up() {
    const d = D; end(); D = null; if (!d) return;
    if (!d.started) { const g = d.g; const r = g.getBoundingClientRect(); if (d.src.type === 'row') rowMenu(d.src.node, r.left, r.bottom); else if (d.src.type === 'item') { const b = g.closest('.blk'); blockMenu(b, r.right, r.top); } return; }
    const T = d.T; if (!T) { announce('Not dropped. Nothing moved.'); return; }
    if (T.kind === 'join') { joinDialog(d.src.node); return; }
    if (d.src.type === 'sel') { askTitle('Make a Chapter', 'The selected text becomes a Chapter at the place you dropped it.', (t) => mutate('Made a Chapter', () => extractSelection(d.src.node, d.src.item, d.src.from, d.src.to, t, { parent: T.parent, index: T.index }) !== false)); return; }
    doMove(d.src, T.parent, T.index, T.label.replace(/[“”]/g, ''));
  }
  function cancel() { end(); D = null; announce('Cancelled. Nothing moved.'); }
  function escKey(e) { if (e.key === 'Escape' && D) { e.stopPropagation(); cancel(); window.removeEventListener('pointerup', up); } }
  window.wrDndBind = () => {};
  /* keyboard: Alt+arrows on a grip */
  window.kbMove = (g, key) => {
    const src = srcOf(g); let ok = false;
    if (src.type === 'row') {
      const p = parentOf(src.node); if (!p) return;
      if (key === 'ArrowUp') { if (p.index === 0) return announce('Already first here'); ok = mutate('Moved up', () => moveTo(src, p.node, p.index - 1)); }
      else if (key === 'ArrowDown') { if (p.index >= N(p.node).items.length - 1) return announce('Already last here'); ok = mutate('Moved down', () => moveTo(src, p.node, p.index + 2)); }
      else if (key === 'ArrowRight') ok = mutate('Nested', () => nest(src.node)); else if (key === 'ArrowLeft') ok = mutate('Promoted', () => promote(src.node));
    } else if (src.type === 'item') {
      const ix = itemPos(src.parent, src.item); const len = N(src.parent).items.length;
      if (key === 'ArrowUp') { if (ix === 0) return announce('Already first'); ok = mutate('Moved up', () => moveTo(src, src.parent, ix - 1)); }
      else if (key === 'ArrowDown') { if (ix >= len - 1) return announce('Already last'); ok = mutate('Moved down', () => moveTo(src, src.parent, ix + 2)); }
      else announce('Use the arrows up and down to move a block. Enter opens Move to.');
    }
    if (ok !== false) setTimeout(() => { const sel = g.dataset.drag === 'row' ? `.grip[data-drag="row"][data-node="${g.dataset.node}"]` : `.grip[data-item="${g.dataset.item}"]`; const n = $(sel); n && n.focus(); }, 40);
  };
})();

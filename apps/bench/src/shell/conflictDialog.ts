// Reviewing what could not be sent (ADR 0254): each conflict with what it was, what the person
// wrote and what the server has now, and a choice; and what the server refused, with a way on.

import type { Bench } from '../core/bench';
import type { Command } from '../core/commands';
import { fieldLabel, showValue } from './entryPane';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const button = (text: string, run: () => void, cls = 'btn') => {
  const b = el('button', cls, text);
  b.type = 'button';
  b.addEventListener('click', run);
  return b;
};

export function openConflicts(bench: Bench, go: (id: string) => void): void {
  const dialog = el('dialog', 'confirm review');
  dialog.setAttribute('aria-labelledby', 'review-title');
  let off = () => {};
  const close = () => {
    off();
    dialog.close();
    dialog.remove();
  };
  const card = (c: Command) => {
    const box = el('li', `review-item ${c.state}`);
    const head = el('div', 'review-head');
    head.append(
      button(
        bench.displayName(c.entryId) || 'A new entry',
        () => {
          go(c.entryId);
          close();
        },
        'btn link',
      ),
      el('span', 'muted', fieldLabel(c)),
    );
    box.append(head);
    if (c.state === 'conflict') {
      const grid = el('dl', 'review-values');
      for (const [term, value] of [
        ['Was', c.base],
        ['Mine', c.mine],
        ['Theirs', c.theirs],
      ] as const) {
        const d = el('div');
        d.append(el('dt', undefined, term), el('dd', undefined, showValue(value, bench, c)));
        grid.append(d);
      }
      box.append(
        grid,
        button('Keep mine', () => bench.keepMine(c.id), 'btn primary'),
        button('Use theirs', () => bench.discard(c.id)),
      );
    } else {
      box.append(
        el('p', undefined, c.error ?? 'The server refused this change.'),
        button('Try again', () => bench.retry(c.id)),
        button('Discard', () => bench.discard(c.id)),
      );
    }
    return box;
  };
  const draw = () => {
    const items = bench.outbox.filter((c) => c.state === 'conflict' || c.state === 'attention');
    if (!items.length) return close();
    const title = el(
      'h2',
      undefined,
      `${items.length} ${items.length === 1 ? 'change needs' : 'changes need'} a look`,
    );
    title.id = 'review-title';
    const list = el('ul', 'review-list');
    list.append(...items.map(card));
    dialog.replaceChildren(
      title,
      list,
      el('p', 'muted', 'Other entries keep syncing while these wait.'),
      button('Close', close),
    );
  };
  off = bench.subscribe(draw);
  dialog.addEventListener('close', () => {
    off();
    dialog.remove();
  });
  document.body.append(dialog);
  draw();
  if (dialog.isConnected && !dialog.open) dialog.showModal();
}

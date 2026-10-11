// The status bar (ADR 0254): how the changes are doing, what is selected, and the connection.

import type { Bench } from '../core/bench';
import type { Command } from '../core/commands';
import { kindsText } from './entryPane';

export interface Sync {
  conflicts: number;
  attention: number;
  waiting: number;
}

export function summarize(outbox: readonly Command[]): Sync {
  const n = (state: Command['state']) => outbox.filter((c) => c.state === state).length;
  return {
    conflicts: n('conflict'),
    attention: n('attention'),
    waiting: n('waiting') + n('sending'),
  };
}

/** The sync part, in words: the worst thing first. */
export function syncText(s: Sync): string {
  if (s.conflicts) return `Conflict (${s.conflicts})`;
  if (s.attention) return `Needs attention (${s.attention})`;
  if (s.waiting) return `Waiting to sync (${s.waiting})`;
  return 'Synced';
}

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

/** Draws the bar into `bar`. A problem opens `review`. */
export function drawStatusBar(
  bar: HTMLElement,
  bench: Bench,
  selected: string | null,
  review: () => void,
): void {
  const sync = summarize(bench.outbox);
  const problem = sync.conflicts + sync.attention > 0;
  const state = el(problem ? 'button' : 'span', `sb-sync ${problem ? 'bad' : ''}`, syncText(sync));
  if (state instanceof HTMLButtonElement) {
    state.type = 'button';
    state.title = 'Review what could not be sent';
    state.addEventListener('click', review);
  }
  const item = selected ? bench.view(selected) : null;
  const what = el(
    'span',
    'sb-selection',
    item
      ? `${item.name} · ${kindsText(item.kinds) || 'no kind'} · ${bench.linkCount(item.id)} links`
      : 'Nothing selected',
  );
  const line = el(
    'span',
    `sb-online${bench.offline ? ' bad' : ''}`,
    bench.offline ? 'Offline' : 'Online',
  );
  bar.replaceChildren(state, what, line);
}

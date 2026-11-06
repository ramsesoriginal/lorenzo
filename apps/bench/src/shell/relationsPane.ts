// The Relations pane: the relationships the selected entry is an end of, drawn around it with the
// shared graph renderer (ADR 0407) and told in words. An entry is opened from the drawing with
// Enter, or from the list. Read only: relationships are written in Lorenzo Social.

import { createGraphView, type GraphViewHandle } from '@lorenzo/graph-renderer';
import type { Bench } from '../core/bench';
import type { RelationRow } from '../core/transport';

/** One sentence for a relationship: who it ties, and which way. */
export function relationSentence(row: RelationRow): string {
  const ties = row.oneWay
    ? `From ${row.endA.name} to ${row.endB.name}`
    : `Between ${row.endA.name} and ${row.endB.name}, both ways`;
  return `${row.name}: ${ties}.`;
}

/** The graph a set of relationships makes around one entry. */
export function relationModel(entry: { id: string; name: string }, rows: readonly RelationRow[]) {
  const names = new Map<string, string>([[entry.id, entry.name]]);
  for (const row of rows) {
    names.set(row.endA.id, row.endA.name);
    names.set(row.endB.id, row.endB.name);
  }
  return {
    nodes: [...names].map(([id, name]) => ({ id, name })),
    edges: rows.map((row) => ({
      id: row.id,
      a: row.endA.id,
      b: row.endB.id,
      directed: row.oneWay,
      label: row.name,
      status: 'direct' as const,
    })),
  };
}

// The drawing a pane holds is dropped when the pane is drawn again, so none is left listening.
let drawing: GraphViewHandle | null = null;

export function renderRelations(
  bench: Bench,
  id: string | null,
  go: (id: string) => void,
): HTMLElement {
  drawing?.destroy();
  drawing = null;
  const c = document.createElement('div');
  c.className = 'pane pane-relations';
  const say = (text: string) => {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = text;
    c.append(p);
    return p;
  };
  if (!id) {
    say('Choose an entry in the explorer.');
    return c;
  }
  const read = bench.transport.relationshipsOf;
  if (!read) {
    say('This repository holds no relationships here.');
    return c;
  }
  const status = say('Reading the relationships…');
  status.setAttribute('role', 'status');
  const name = bench.displayName(id);
  void read
    .call(bench.transport, id)
    .then((rows) => {
      if (rows.length === 0) {
        status.textContent = 'No relationship you may see has this entry as an end.';
        return;
      }
      status.textContent = '';
      const host = document.createElement('div');
      host.className = 'relations-graph';
      const list = document.createElement('ul');
      list.className = 'relations-list';
      list.setAttribute('aria-label', 'Relationships of this entry');
      for (const row of rows) {
        const item = document.createElement('li');
        item.textContent = relationSentence(row);
        list.append(item);
      }
      c.append(host, list);
      drawing = createGraphView(host, {
        title: `Relations of ${name}`,
        model: relationModel({ id, name }, rows),
        view: { layout: 'radial', focus: id, seed: 1, labels: true },
        onOpen: (other) => {
          if (other !== id) go(other);
        },
      });
    })
    .catch((error: unknown) => {
      status.textContent = `Could not read the relationships. ${error instanceof Error ? error.message : ''}`;
    });
  return c;
}

// A manuscript as the flat, ordered parts a file format needs: headings, texts and pictures (ADR
// 0521). It follows the same walk as the printable export, so a Markdown or Word file has the same
// order, the same numbers and the same selected passages as what is printed.
import type { ExportSnapshot } from '../manuscript-export';

export type Part =
  | { kind: 'heading'; depth: number; text: string }
  | { kind: 'text'; content: string }
  | { kind: 'picture'; mediaType: string; data: string };

type Task = { kind: 'entry' | 'payload'; id: string; selected?: string; depth: number };

export function exportParts(snapshot: ExportSnapshot): Part[] {
  const entries = new Map(snapshot.entries.map((entry) => [entry.id, entry]));
  const payloads = new Map((snapshot.payloads ?? []).map((payload) => [payload.id, payload]));
  const parts: Part[] = [];
  const pending: Task[] = [{ kind: 'entry', id: snapshot.root_id, depth: 1 }];
  // An entry could in principle be reached again through a coverage; each walk is bounded.
  let steps = 0;
  while (pending.length && steps++ < 100_000) {
    const task = pending.pop();
    if (!task) break;
    if (task.kind === 'payload') {
      const payload = payloads.get(task.id);
      if (!payload) continue;
      if (payload.kind === 'picture')
        parts.push({
          kind: 'picture',
          mediaType: payload.media_type ?? 'image/png',
          data: payload.data ?? '',
        });
      else parts.push({ kind: 'text', content: payload.content ?? '' });
      continue;
    }
    const entry = entries.get(task.id);
    if (!entry) continue;
    parts.push({
      kind: 'heading',
      depth: Math.min(task.depth, 6),
      text: `${entry.number ? `${entry.number} ` : ''}${entry.name}`,
    });
    if (entry.joined)
      parts.push({ kind: 'text', content: 'This section was joined to another section.' });
    for (const element of [...entry.elements].reverse()) {
      if (task.selected && element.id !== task.selected) continue;
      if (element.kind === 'payload')
        pending.push({ kind: 'payload', id: element.id, depth: task.depth });
      else if (element.kind === 'coverage' && element.target_id)
        pending.push({
          kind: 'entry',
          id: element.target_id,
          selected: element.payload_id ?? undefined,
          depth: task.depth + 1,
        });
      else if (element.kind === 'chapter' || element.kind === 'scene_telling')
        pending.push({ kind: 'entry', id: element.id, depth: task.depth + 1 });
    }
  }
  return parts;
}

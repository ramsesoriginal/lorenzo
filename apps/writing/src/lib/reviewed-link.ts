import { type Block, type Inline, parse } from '@lorenzo/lorenzoscript';

function* inlineGroups(nodes: Inline[]): Generator<Inline[]> {
  yield nodes;
  for (const node of nodes) {
    if ('children' in node && node.type !== 'link' && node.type !== 'image')
      yield* inlineGroups(node.children);
  }
}

function* proseGroups(blocks: Block[]): Generator<Inline[]> {
  for (const block of blocks) {
    switch (block.type) {
      case 'paragraph':
      case 'heading':
        yield* inlineGroups(block.children);
        break;
      case 'blockquote':
      case 'div':
        yield* proseGroups(block.children);
        break;
      case 'list':
        for (const item of block.items) yield* proseGroups(item.children);
        break;
      case 'table':
        for (const row of [block.head, ...block.rows])
          for (const cell of row) yield* inlineGroups(cell);
        break;
    }
  }
}

/** Require both parses to agree with replacing one plain-text occurrence by exactly one link. */
export function reviewedLink(source: string, start: number, end: number, slug: string) {
  const label = source.slice(start, end);
  if (!label || label.length > 300 || label.trim() !== label || /[\r\n]/u.test(label)) return null;
  const left = source.slice(0, start);
  const right = source.slice(end);
  if (/[\p{L}\p{M}\p{N}\p{Pc}]$/u.test(left) || /^[\p{L}\p{M}\p{N}\p{Pc}]/u.test(right))
    return null;
  const markup = `[[${slug}|${label}]]`;
  const block = parse(markup).children[0];
  if (block?.type !== 'paragraph' || block.children.length !== 1) return null;
  const link = block.children[0];
  if (
    link.type !== 'link' ||
    link.ref?.slug !== slug ||
    link.children.length !== 1 ||
    link.children[0].type !== 'text' ||
    link.children[0].text !== label
  )
    return null;

  const marker = `LorenzoProbe${crypto.randomUUID().replaceAll('-', '')}`;
  const probe = parse(left + marker + right);
  for (const nodes of proseGroups([
    ...probe.children,
    ...probe.footnotes.flatMap((note) => note.children),
  ])) {
    const index = nodes.findIndex((node) => node.type === 'text' && node.text.includes(marker));
    const node = nodes[index];
    if (node?.type !== 'text') continue;
    const [before, after] = node.text.split(marker);
    node.text = before + label + after;
    if (JSON.stringify(probe) !== JSON.stringify(parse(source))) return null;
    const replacement: Inline[] = [];
    if (before) replacement.push({ type: 'text', text: before });
    replacement.push(link);
    if (after) replacement.push({ type: 'text', text: after });
    nodes.splice(index, 1, ...replacement);
    return JSON.stringify(probe) === JSON.stringify(parse(left + markup + right)) ? markup : null;
  }
  return null;
}

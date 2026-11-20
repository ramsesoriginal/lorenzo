// A Word file as LorenzoScript text (ADR 0523): headings, paragraphs, bold, italic, links, lists,
// quotes, code, tables and footnotes. What Word keeps beyond that (pictures, comments, tracked
// changes, layout) is not read, and the author is told what was left out.
import { strFromU8, unzipSync } from 'fflate';
import type { Imported } from './markdown';
import { elementsOf, firstOf, parseXml, type XmlElement } from './xml';

export type DocxImport = Imported & { notes: string[] };

type Style = { name: string };
type Run = {
  text: string;
  bold: boolean;
  italic: boolean;
  strike: boolean;
  sup: boolean;
  sub: boolean;
  code: boolean;
  link: string;
};

const on = (el: XmlElement | undefined) =>
  el !== undefined &&
  !['0', 'false', 'off', 'none'].includes((el.attrs['w:val'] ?? '').toLowerCase());

/** Text with the characters LorenzoScript reads as syntax made plain; [[links]] stay links. */
function plain(text: string, inTable = false): string {
  return text
    .split(/(\[\[[^[\]\n]+\]\])/)
    .map((piece, index) =>
      index % 2 === 1
        ? piece
        : piece.replace(inTable ? /[\\`*_[\]<>~^{}|]/g : /[\\`*_[\]<>~^{}]/g, (c) => `\\${c}`),
    )
    .join('');
}

function codeSpan(text: string): string {
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map((ticks) => ticks.length));
  const fence = '`'.repeat(longest + 1);
  return `${fence}${text.startsWith('`') || text.endsWith('`') ? ` ${text} ` : text}${fence}`;
}

const sameFormat = (a: Run, b: Run) =>
  a.bold === b.bold &&
  a.italic === b.italic &&
  a.strike === b.strike &&
  a.sup === b.sup &&
  a.sub === b.sub &&
  a.code === b.code &&
  a.link === b.link;

function renderRuns(runs: Run[], inTable = false): string {
  const merged: Run[] = [];
  for (const run of runs) {
    const last = merged[merged.length - 1];
    if (last && sameFormat(last, run)) last.text += run.text;
    else merged.push({ ...run });
  }
  const pieces = merged.map((run) => {
    if (run.text.length === 0) return '';
    const lead = /^\s*/.exec(run.text)?.[0] ?? '';
    const trail = run.text.length > lead.length ? (/\s*$/.exec(run.text)?.[0] ?? '') : '';
    const core = run.text.slice(lead.length, run.text.length - trail.length);
    if (core.length === 0) return run.text;
    let out = run.code ? codeSpan(core) : plain(core, inTable);
    if (run.sup) out = `^${out}^`;
    if (run.sub) out = `~${out}~`;
    if (run.strike) out = `~~${out}~~`;
    if (run.italic) out = `*${out}*`;
    if (run.bold) out = `**${out}**`;
    if (run.link) out = `[${out}](${run.link.replace(/[()\s]/g, (c) => encodeURIComponent(c))})`;
    return `${lead}${out}${trail}`;
  });
  return pieces.join('').replace(/[ \t]+\n/g, '\n');
}

export function fromDocx(fileName: string, bytes: Uint8Array): DocxImport {
  let files: Record<string, Uint8Array>;
  try {
    files = unzipSync(bytes, { filter: (file) => file.name.startsWith('word/') });
  } catch {
    throw new Error(`“${fileName}” is not a Word (.docx) file.`);
  }
  const read = (name: string) => (files[name] ? strFromU8(files[name]) : null);
  const documentXml = read('word/document.xml');
  if (!documentXml) throw new Error(`“${fileName}” is not a Word (.docx) file.`);

  const styles = new Map<string, Style>();
  const stylesXml = read('word/styles.xml');
  if (stylesXml)
    for (const style of elementsOf(parseXml(stylesXml), 'w:style')) {
      const id = style.attrs['w:styleId'];
      if (id) styles.set(id, { name: firstOf(style, 'w:name')?.attrs['w:val'] ?? id });
    }

  const targets = new Map<string, string>();
  const relsXml = read('word/_rels/document.xml.rels');
  if (relsXml)
    for (const rel of elementsOf(parseXml(relsXml), 'Relationship'))
      if (rel.attrs.Type?.endsWith('/hyperlink') && rel.attrs.Id && rel.attrs.Target)
        targets.set(rel.attrs.Id, rel.attrs.Target);

  // Which numbering ids are bullets and which are counted.
  const ordered = new Map<string, boolean>();
  const numberingXml = read('word/numbering.xml');
  if (numberingXml) {
    const root = parseXml(numberingXml);
    const abstract = new Map<string, boolean>();
    for (const def of elementsOf(root, 'w:abstractNum')) {
      const level = elementsOf(def, 'w:lvl')[0];
      const format = level ? firstOf(level, 'w:numFmt')?.attrs['w:val'] : undefined;
      abstract.set(def.attrs['w:abstractNumId'] ?? '', format !== undefined && format !== 'bullet');
    }
    for (const num of elementsOf(root, 'w:num')) {
      const id = firstOf(num, 'w:abstractNumId')?.attrs['w:val'] ?? '';
      ordered.set(num.attrs['w:numId'] ?? '', abstract.get(id) ?? false);
    }
  }

  const notes: string[] = [];
  let pictures = 0;
  const footnoteText = new Map<string, string>();
  const footnotesXml = read('word/footnotes.xml');

  const runOf = (el: XmlElement, link: string): Run[] => {
    const props = firstOf(el, 'w:rPr');
    const vertical = props ? firstOf(props, 'w:vertAlign')?.attrs['w:val'] : undefined;
    const fonts = props ? firstOf(props, 'w:rFonts')?.attrs['w:ascii'] : undefined;
    const format = {
      bold: props ? on(firstOf(props, 'w:b')) : false,
      italic: props ? on(firstOf(props, 'w:i')) : false,
      strike: props ? on(firstOf(props, 'w:strike')) : false,
      sup: vertical === 'superscript',
      sub: vertical === 'subscript',
      code: /courier|consolas|mono/i.test(fonts ?? ''),
      link,
    };
    const out: Run[] = [];
    for (const child of elementsOf(el)) {
      if (child.name === 'w:t') out.push({ ...format, text: text(child) });
      else if (child.name === 'w:tab') out.push({ ...format, text: ' ' });
      else if (child.name === 'w:br' && child.attrs['w:type'] !== 'page')
        out.push({ ...format, text: '\n' });
      else if (child.name === 'w:footnoteReference')
        out.push({
          ...format,
          bold: false,
          italic: false,
          code: false,
          text: `\uE000${child.attrs['w:id'] ?? ''}\uE000`,
        });
      else if (child.name === 'w:drawing' || child.name === 'w:pict') pictures += 1;
    }
    return out;
  };
  const text = (el: XmlElement) =>
    el.children.map((child) => (typeof child === 'string' ? child : '')).join('');

  const runsOf = (el: XmlElement, link = ''): Run[] =>
    elementsOf(el).flatMap((child): Run[] => {
      if (child.name === 'w:r') return runOf(child, link);
      if (child.name === 'w:hyperlink') {
        const target = child.attrs['r:id'] ? (targets.get(child.attrs['r:id']) ?? '') : '';
        return runsOf(child, target);
      }
      // Wrappers that hold runs: tracked insertions, smart tags, content controls, fields.
      if (['w:ins', 'w:smartTag', 'w:sdt', 'w:sdtContent', 'w:fldSimple'].includes(child.name))
        return runsOf(child, link);
      return [];
    });

  // Footnote text, so a reference can be given its definition.
  if (footnotesXml)
    for (const note of elementsOf(parseXml(footnotesXml), 'w:footnote')) {
      if (note.attrs['w:type'] === 'separator' || note.attrs['w:type'] === 'continuationSeparator')
        continue;
      const paragraphs = elementsOf(note, 'w:p').map((p) =>
        renderRuns(runsOf(p).filter((run) => !run.text.includes('\uE000'))).trim(),
      );
      footnoteText.set(note.attrs['w:id'] ?? '', paragraphs.filter(Boolean).join(' '));
    }

  type Block = {
    kind: 'text' | 'heading' | 'bullet' | 'number' | 'quote' | 'code';
    level: number;
    md: string;
  };
  const blocks: Block[] = [];
  const body = firstOf(parseXml(documentXml), 'w:body');
  if (!body) throw new Error(`“${fileName}” holds no text.`);

  const paragraph = (p: XmlElement, inTable = false): Block | null => {
    const props = firstOf(p, 'w:pPr');
    const styleId = props ? (firstOf(props, 'w:pStyle')?.attrs['w:val'] ?? '') : '';
    const style = (styles.get(styleId)?.name ?? styleId).toLowerCase();
    const runs = runsOf(p);
    const md = renderRuns(runs, inTable)
      .replace(/\n/g, inTable ? ' ' : '  \n')
      .trim();
    const heading = /^(?:heading|überschrift|titre)\s*(\d)$/.exec(style);
    if (heading || style === 'title') {
      const level = style === 'title' ? 1 : Math.min(Number(heading?.[1] ?? 1), 6);
      const words = renderRuns(runs.map((run) => ({ ...run, bold: false, italic: false })))
        .replace(/\n/g, ' ')
        .trim();
      return words ? { kind: 'heading', level, md: words } : null;
    }
    if (!md) return null;
    const numbering = props ? firstOf(props, 'w:numPr') : undefined;
    const numId = numbering ? firstOf(numbering, 'w:numId')?.attrs['w:val'] : undefined;
    if (numId && numId !== '0') {
      const level = Number(firstOf(numbering as XmlElement, 'w:ilvl')?.attrs['w:val'] ?? 0);
      return { kind: ordered.get(numId) ? 'number' : 'bullet', level: Math.min(level, 8), md };
    }
    if (/list bullet/.test(style)) return { kind: 'bullet', level: 0, md };
    if (/list number/.test(style)) return { kind: 'number', level: 0, md };
    if (/quote/.test(style)) return { kind: 'quote', level: 0, md };
    if (/^(code|source code|html preformatted|preformatted text)/.test(style)) {
      const raw = runs.map((run) => run.text).join('');
      return { kind: 'code', level: 0, md: raw };
    }
    return { kind: 'text', level: 0, md };
  };

  for (const child of elementsOf(body)) {
    if (child.name === 'w:p') {
      const block = paragraph(child);
      if (block) blocks.push(block);
    } else if (child.name === 'w:tbl') {
      const rows = elementsOf(child, 'w:tr').map((row) =>
        elementsOf(row, 'w:tc').map((cell) =>
          elementsOf(cell, 'w:p')
            .map((p) => paragraph(p, true)?.md ?? '')
            .filter(Boolean)
            .join(' '),
        ),
      );
      const width = Math.max(1, ...rows.map((row) => row.length));
      const line = (cells: string[]) =>
        `| ${Array.from({ length: width }, (_, i) => cells[i] ?? '').join(' | ')} |`;
      if (rows.length > 0)
        blocks.push({
          kind: 'text',
          level: 0,
          md: [
            line(rows[0] ?? []),
            `| ${Array.from({ length: width }, () => '---').join(' | ')} |`,
            ...rows.slice(1).map(line),
          ].join('\n'),
        });
    }
  }

  // Footnote references become numbered labels, in the order they are met.
  const order: string[] = [];
  const label = (id: string) => {
    if (!order.includes(id)) order.push(id);
    return String(order.indexOf(id) + 1);
  };
  const withNotes = (md: string) =>
    md.replace(/\uE000([^\uE000]*)\uE000/g, (_, id: string) =>
      footnoteText.has(id) ? `[^${label(id)}]` : '',
    );

  // The first heading of level 1 names the document and leaves its text.
  let title = '';
  const first = blocks.findIndex((block) => block.kind === 'text' || block.kind === 'heading');
  const firstBlock = blocks[first];
  if (firstBlock && firstBlock.kind === 'heading' && firstBlock.level === 1) {
    title = firstBlock.md;
    blocks.splice(first, 1);
  }

  const out: string[] = [];
  let index = 0;
  while (index < blocks.length) {
    const block = blocks[index] as Block;
    if (block.kind === 'heading') {
      out.push(`${'#'.repeat(block.level)} ${withNotes(block.md)}`);
      index += 1;
    } else if (block.kind === 'bullet' || block.kind === 'number') {
      const lines: string[] = [];
      while (index < blocks.length) {
        const item = blocks[index] as Block;
        if (item.kind !== 'bullet' && item.kind !== 'number') break;
        lines.push(
          `${'  '.repeat(item.level)}${item.kind === 'number' ? '1.' : '-'} ${withNotes(item.md).replace(/\n/g, `\n${'  '.repeat(item.level + 1)}`)}`,
        );
        index += 1;
      }
      out.push(lines.join('\n'));
    } else if (block.kind === 'quote') {
      const lines: string[] = [];
      while (index < blocks.length && (blocks[index] as Block).kind === 'quote') {
        lines.push(`> ${withNotes((blocks[index] as Block).md)}`);
        index += 1;
      }
      out.push(lines.join('\n>\n'));
    } else if (block.kind === 'code') {
      const lines: string[] = [];
      while (index < blocks.length && (blocks[index] as Block).kind === 'code') {
        lines.push((blocks[index] as Block).md);
        index += 1;
      }
      out.push(`\`\`\`\n${lines.join('\n')}\n\`\`\``);
    } else {
      out.push(withNotes(block.md));
      index += 1;
    }
  }
  for (const [number, id] of order.entries())
    out.push(`[^${number + 1}]: ${footnoteText.get(id) ?? ''}`);

  if (pictures > 0)
    notes.push(`${pictures} ${pictures === 1 ? 'picture was' : 'pictures were'} not imported`);
  const fallback = fileName
    .replace(/\.[^./\\]+$/, '')
    .replace(/[-_]+/g, ' ')
    .trim();
  return {
    title: (title || fallback || 'Untitled').slice(0, 300),
    content: out.join('\n\n').trim(),
    notes,
  };
}

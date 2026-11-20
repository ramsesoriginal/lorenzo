// A manuscript as a Word document (ADR 0522), made in the browser from the same parts as the
// Markdown export. The text is read from its LorenzoScript syntax tree, not from rendered HTML, so
// nothing depends on a page: headings, paragraphs, bold, italic, links, lists, quotes, code,
// tables, footnotes and pictures become what Word calls the same things.
import { type Block, type Document, type Inline, parse } from '@lorenzo/lorenzoscript';
import { strToU8, zipSync } from 'fflate';
import type { Part } from './export-parts';

const escapeXml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    // Characters XML 1.0 cannot hold would make the whole file unreadable.
    // biome-ignore lint/suspicious/noControlCharactersInRegex: this is the point
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g, '');

const NS =
  'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' +
  'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' +
  'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" ' +
  'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' +
  'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"';

type Format = {
  bold?: boolean;
  italic?: boolean;
  strike?: boolean;
  sub?: boolean;
  sup?: boolean;
  code?: boolean;
  link?: boolean;
};

function runProps(format: Format): string {
  let props = '';
  if (format.link) props += '<w:rStyle w:val="Hyperlink"/>';
  if (format.code)
    props += '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>';
  if (format.bold) props += '<w:b/>';
  if (format.italic) props += '<w:i/>';
  if (format.strike) props += '<w:strike/>';
  if (format.sup) props += '<w:vertAlign w:val="superscript"/>';
  if (format.sub) props += '<w:vertAlign w:val="subscript"/>';
  return props ? `<w:rPr>${props}</w:rPr>` : '';
}

const run = (text: string, format: Format = {}) =>
  text.length === 0
    ? ''
    : `<w:r>${runProps(format)}<w:t xml:space="preserve">${escapeXml(text)}</w:t></w:r>`;

type Image = { name: string; bytes: Uint8Array; extension: string };

/** The pixel size of a PNG, GIF or JPEG, or null when it cannot be read. */
export function imageSize(bytes: Uint8Array): { width: number; height: number } | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.length > 24 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47)
    return { width: view.getUint32(16), height: view.getUint32(20) };
  if (bytes.length > 10 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46)
    return { width: view.getUint16(6, true), height: view.getUint16(8, true) };
  if (bytes.length > 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    let at = 2;
    while (at + 9 < bytes.length) {
      if (bytes[at] !== 0xff) return null;
      const marker = bytes[at + 1] ?? 0;
      const length = view.getUint16(at + 2);
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker))
        return { width: view.getUint16(at + 7), height: view.getUint16(at + 5) };
      at += 2 + length;
    }
  }
  return null;
}

const EXTENSIONS: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpeg',
  'image/gif': 'gif',
  'image/webp': 'webp',
};

function base64Bytes(data: string): Uint8Array {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

class Builder {
  body: string[] = [];
  footnotes: string[] = [];
  links: { id: string; url: string }[] = [];
  images: Image[] = [];
  numbers: { ordered: boolean; start: number }[] = [];
  private listLevel = 0;
  private quoted = 0;
  private footnoteId = 1;
  private drawingId = 0;

  /** The inlines of one text, with its own footnote labels resolved against its document. */
  inlines(list: Inline[], doc: Document, labels: Map<string, number>, format: Format = {}): string {
    return list.map((inline) => this.inline(inline, doc, labels, format)).join('');
  }

  private inline(
    inline: Inline,
    doc: Document,
    labels: Map<string, number>,
    format: Format,
  ): string {
    switch (inline.type) {
      case 'text':
        return run(inline.text, format);
      case 'codespan':
        return run(inline.text, { ...format, code: true });
      case 'em':
      case 'i':
        return this.inlines(inline.children, doc, labels, { ...format, italic: true });
      case 'strong':
      case 'b':
        return this.inlines(inline.children, doc, labels, { ...format, bold: true });
      case 'del':
        return this.inlines(inline.children, doc, labels, { ...format, strike: true });
      case 'sub':
        return this.inlines(inline.children, doc, labels, { ...format, sub: true });
      case 'sup':
        return this.inlines(inline.children, doc, labels, { ...format, sup: true });
      case 'span':
        return this.inlines(inline.children, doc, labels, format);
      case 'link': {
        const inner = this.inlines(inline.children, doc, labels, { ...format, link: !inline.ref });
        // A link to an entry of the library has no address outside it: its words stay.
        if (inline.ref || !/^(https?:|mailto:)/i.test(inline.url)) return inner;
        const id = `rIdLink${this.links.length + 1}`;
        this.links.push({ id, url: inline.url });
        return `<w:hyperlink r:id="${id}">${inner}</w:hyperlink>`;
      }
      case 'image':
        return run(inline.children.map(plain).join('') || inline.title || '[image]', format);
      case 'math':
        return run(inline.tex, { ...format, italic: true });
      case 'footnote': {
        const key = inline.label.toLowerCase().replace(/\s+/g, ' ');
        const existing = labels.get(key);
        if (existing !== undefined) return footnoteReference(existing);
        const note = doc.footnotes.find((footnote) => footnote.label === key);
        if (!note) return run(`[${inline.label}]`, format);
        this.footnoteId += 1;
        const id = this.footnoteId;
        labels.set(key, id);
        const paragraphs = note.children.flatMap((block) =>
          this.plainParagraphs(block, doc, labels),
        );
        this.footnotes.push(
          `<w:footnote w:id="${id}">${paragraphs
            .map((content, index) =>
              paragraph(
                `${index === 0 ? '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>' : ''}${content}`,
                'FootnoteText',
              ),
            )
            .join('')}</w:footnote>`,
        );
        return footnoteReference(id);
      }
      case 'date':
        return run(inline.date, format);
      case 'calendar':
        return run(inline.expression, format);
      case 'stat':
        return run(`{${inline.name}}`, format);
      case 'break':
        return '<w:r><w:br/></w:r>';
    }
  }

  /** A footnote's blocks as the runs of paragraphs: only the words matter there. */
  private plainParagraphs(block: Block, doc: Document, labels: Map<string, number>): string[] {
    if (block.type === 'paragraph') return [this.inlines(block.children, doc, labels)];
    if (block.type === 'heading')
      return [this.inlines(block.children, doc, labels, { bold: true })];
    if (block.type === 'code') return [run(block.text, { code: true })];
    if (block.type === 'blockquote' || block.type === 'div')
      return block.children.flatMap((child) => this.plainParagraphs(child, doc, labels));
    if (block.type === 'list')
      return block.items.flatMap((item) =>
        item.children.flatMap((child) => this.plainParagraphs(child, doc, labels)),
      );
    return [];
  }

  blocks(list: Block[], doc: Document, labels: Map<string, number>, base: number, indent = 0) {
    for (const block of list) this.block(block, doc, labels, base, indent);
  }

  private block(
    block: Block,
    doc: Document,
    labels: Map<string, number>,
    base: number,
    indent: number,
  ) {
    switch (block.type) {
      case 'paragraph':
        this.body.push(
          paragraph(
            this.inlines(block.children, doc, labels),
            this.quoted > 0 ? 'Quote' : undefined,
            indent,
          ),
        );
        return;
      case 'heading':
        this.body.push(
          paragraph(
            this.inlines(block.children, doc, labels),
            `Heading${Math.min(Math.max(block.level + base, 1), 6)}`,
          ),
        );
        return;
      case 'blockquote':
        this.quoted += 1;
        this.blocks(block.children, doc, labels, base, indent + 720);
        this.quoted -= 1;
        return;
      case 'list': {
        const level = Math.min(this.listLevel, 8);
        this.numbers.push({ ordered: block.ordered, start: block.start });
        const id = this.numbers.length;
        for (const item of block.items) {
          const [first, ...rest] = item.children;
          const mark = item.checked === null ? '' : item.checked ? '☒ ' : '☐ ';
          const text = first?.type === 'paragraph' ? this.inlines(first.children, doc, labels) : '';
          this.body.push(paragraph(`${run(mark)}${text}`, undefined, 0, { id, level }));
          this.listLevel += 1;
          if (first && first.type !== 'paragraph') this.block(first, doc, labels, base, indent);
          this.blocks(rest, doc, labels, base, indent + 720 * (level + 1));
          this.listLevel -= 1;
        }
        return;
      }
      case 'code':
        this.body.push(
          paragraph(
            block.text
              .replace(/\n$/, '')
              .split('\n')
              .map((line, i) => `${i > 0 ? '<w:r><w:br/></w:r>' : ''}${run(line, { code: true })}`)
              .join(''),
            'Code',
            indent,
          ),
        );
        return;
      case 'rule':
        this.body.push(
          '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="808080"/></w:pBdr></w:pPr></w:p>',
        );
        return;
      case 'table': {
        const cell = (inlines: Inline[], header: boolean) =>
          `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>${paragraph(
            this.inlines(inlines, doc, labels, header ? { bold: true } : {}),
          )}</w:tc>`;
        const rows = [block.head, ...block.rows].map(
          (cells, index) =>
            `<w:tr>${cells.map((inlines) => cell(inlines, index === 0)).join('')}</w:tr>`,
        );
        this.body.push(
          `<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>${[
            'top',
            'left',
            'bottom',
            'right',
            'insideH',
            'insideV',
          ]
            .map((side) => `<w:${side} w:val="single" w:sz="4" w:space="0" w:color="999999"/>`)
            .join('')}</w:tblBorders></w:tblPr>${rows.join('')}</w:tbl>`,
          '<w:p/>',
        );
        return;
      }
      case 'div':
        this.blocks(block.children, doc, labels, base, indent);
        return;
      case 'math':
        this.body.push(paragraph(run(block.tex, { italic: true }), undefined, indent));
        return;
      case 'toc':
        return;
    }
  }

  picture(mediaType: string, data: string) {
    const extension = EXTENSIONS[mediaType.toLowerCase()];
    if (!extension) {
      this.body.push(paragraph(run('[picture not shown: its format is not one Word reads]')));
      return;
    }
    const bytes = base64Bytes(data);
    const size = imageSize(bytes) ?? { width: 480, height: 320 };
    const maxWidth = 6 * 96;
    const scale = Math.min(1, maxWidth / Math.max(size.width, 1));
    const cx = Math.round(size.width * scale * 9525);
    const cy = Math.round(size.height * scale * 9525);
    const number = this.images.length + 1;
    this.images.push({ name: `image${number}.${extension}`, bytes, extension });
    this.drawingId += 1;
    const id = this.drawingId;
    this.body.push(
      `<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${id}" name="Picture ${id}" descr="Manuscript illustration"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="${id}" name="image${number}.${extension}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rIdImage${number}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`,
    );
  }
}

const plain = (inline: Inline): string =>
  inline.type === 'text' || inline.type === 'codespan'
    ? inline.text
    : 'children' in inline
      ? inline.children.map(plain).join('')
      : '';

const footnoteReference = (id: number) =>
  `<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="${id}"/></w:r>`;

type Numbering = { id: number; level: number };

function paragraph(content: string, style?: string, left = 0, numbering?: Numbering): string {
  const props =
    (style ? `<w:pStyle w:val="${style}"/>` : '') +
    (numbering
      ? `<w:numPr><w:ilvl w:val="${numbering.level}"/><w:numId w:val="${numbering.id}"/></w:numPr>`
      : '') +
    (left ? `<w:ind w:left="${left}"/>` : '');
  return `<w:p>${props ? `<w:pPr>${props}</w:pPr>` : ''}${content}</w:p>`;
}

const STYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" w:cs="Georgia"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
${[1, 2, 3, 4, 5, 6]
  .map(
    (level) =>
      `<w:style w:type="paragraph" w:styleId="Heading${level}"><w:name w:val="heading ${level}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="${level === 1 ? 480 : 280}" w:after="120"/><w:outlineLvl w:val="${level - 1}"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:b/><w:sz w:val="${[40, 32, 28, 26, 24, 24][level - 1]}"/></w:rPr></w:style>`,
  )
  .join('\n')}
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="120" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:qFormat/><w:rPr><w:i/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>
</w:styles>`;

/** One bullet and one decimal list definition, and a numbered instance for every list. */
function numberingXml(lists: { ordered: boolean; start: number }[]): string {
  const levels = (ordered: boolean) =>
    Array.from({ length: 9 }, (_, level) => {
      const text = ordered ? `%${level + 1}.` : '•';
      return `<w:lvl w:ilvl="${level}"><w:start w:val="1"/><w:numFmt w:val="${ordered ? 'decimal' : 'bullet'}"/><w:lvlText w:val="${text}"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="${720 * (level + 1)}" w:hanging="360"/></w:pPr></w:lvl>`;
    }).join('');
  const instances = lists
    .map((list, index) => {
      const restart = list.ordered
        ? `<w:lvlOverride w:ilvl="0"><w:startOverride w:val="${list.start}"/></w:lvlOverride>`
        : '';
      return `<w:num w:numId="${index + 1}"><w:abstractNumId w:val="${list.ordered ? 1 : 0}"/>${restart}</w:num>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>${levels(false)}</w:abstractNum><w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/>${levels(true)}</w:abstractNum>${instances}</w:numbering>`;
}

/** The parts as the bytes of a .docx file. */
export function toDocx(parts: Part[]): Uint8Array {
  const builder = new Builder();
  let base = 0;
  for (const part of parts) {
    if (part.kind === 'heading') {
      base = part.depth;
      builder.body.push(
        paragraph(run(part.text), `Heading${Math.min(Math.max(part.depth, 1), 6)}`),
      );
    } else if (part.kind === 'picture') {
      builder.picture(part.mediaType, part.data);
    } else {
      const doc = parse(part.content);
      builder.blocks(doc.children, doc, new Map(), base);
    }
  }
  const files: Record<string, Uint8Array> = {
    '[Content_Types].xml': strToU8(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Default Extension="jpeg" ContentType="image/jpeg"/><Default Extension="gif" ContentType="image/gif"/><Default Extension="webp" ContentType="image/webp"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>`,
    ),
    '_rels/.rels': strToU8(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`,
    ),
    'word/document.xml': strToU8(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${NS}><w:body>${builder.body.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>`,
    ),
    'word/styles.xml': strToU8(STYLES),
    'word/numbering.xml': strToU8(numberingXml(builder.numbers)),
    'word/footnotes.xml': strToU8(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes ${NS}><w:footnote w:type="separator" w:id="0"><w:p><w:r><w:separator/></w:r></w:p></w:footnote><w:footnote w:type="continuationSeparator" w:id="1"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>${builder.footnotes.join('')}</w:footnotes>`,
    ),
    'word/_rels/document.xml.rels': strToU8(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/><Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>${builder.links
        .map(
          (link) =>
            `<Relationship Id="${link.id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="${escapeXml(link.url)}" TargetMode="External"/>`,
        )
        .join('')}${builder.images
        .map(
          (image, index) =>
            `<Relationship Id="rIdImage${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${image.name}"/>`,
        )
        .join('')}</Relationships>`,
    ),
  };
  for (const image of builder.images) files[`word/media/${image.name}`] = image.bytes;
  return zipSync(files);
}

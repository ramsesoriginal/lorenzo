// A small reader for the XML inside a Word file (ADR 0523): elements, attributes and text, with
// no page to build and no network to ask. It reads what Word writes; it is not a validating parser.
export type XmlElement = {
  name: string;
  attrs: Record<string, string>;
  children: (XmlElement | string)[];
};

const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };

function decode(text: string): string {
  return text.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-z]+);/g, (whole, body: string) => {
    if (body.startsWith('#x')) return safeChar(Number.parseInt(body.slice(2), 16), whole);
    if (body.startsWith('#')) return safeChar(Number.parseInt(body.slice(1), 10), whole);
    return ENTITIES[body] ?? whole;
  });
}

function safeChar(code: number, fallback: string): string {
  try {
    return Number.isFinite(code) && code >= 0 && code <= 0x10ffff
      ? String.fromCodePoint(code)
      : fallback;
  } catch {
    return fallback;
  }
}

const ATTRIBUTE = /([A-Za-z_][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;

function attributesOf(source: string): Record<string, string> {
  const attrs: Record<string, string> = {};
  for (const match of source.matchAll(ATTRIBUTE))
    attrs[match[1] as string] = decode(match[2] ?? match[3] ?? '');
  return attrs;
}

/** The root element of an XML text. Throws when there is none. */
export function parseXml(xml: string): XmlElement {
  const root: XmlElement = { name: '#root', attrs: {}, children: [] };
  const stack: XmlElement[] = [root];
  let at = 0;
  while (at < xml.length) {
    const open = xml.indexOf('<', at);
    const top = stack[stack.length - 1] as XmlElement;
    if (open === -1) {
      top.children.push(decode(xml.slice(at)));
      break;
    }
    if (open > at) top.children.push(decode(xml.slice(at, open)));
    if (xml.startsWith('<!--', open)) {
      const end = xml.indexOf('-->', open + 4);
      at = end === -1 ? xml.length : end + 3;
    } else if (xml.startsWith('<![CDATA[', open)) {
      const end = xml.indexOf(']]>', open + 9);
      top.children.push(xml.slice(open + 9, end === -1 ? xml.length : end));
      at = end === -1 ? xml.length : end + 3;
    } else if (xml.startsWith('<?', open) || xml.startsWith('<!', open)) {
      const end = xml.indexOf('>', open + 2);
      at = end === -1 ? xml.length : end + 1;
    } else {
      const end = xml.indexOf('>', open + 1);
      if (end === -1) break;
      const tag = xml.slice(open + 1, end);
      at = end + 1;
      if (tag.startsWith('/')) {
        if (stack.length > 1) stack.pop();
        continue;
      }
      const selfClosing = tag.endsWith('/');
      const body = selfClosing ? tag.slice(0, -1) : tag;
      const space = body.search(/\s/);
      const element: XmlElement = {
        name: space === -1 ? body : body.slice(0, space),
        attrs: space === -1 ? {} : attributesOf(body.slice(space)),
        children: [],
      };
      top.children.push(element);
      if (!selfClosing) stack.push(element);
    }
  }
  const first = root.children.find((child): child is XmlElement => typeof child !== 'string');
  if (!first) throw new Error('This file holds no document.');
  return first;
}

export const elementsOf = (element: XmlElement, name?: string): XmlElement[] =>
  element.children.filter(
    (child): child is XmlElement => typeof child !== 'string' && (!name || child.name === name),
  );

export const firstOf = (element: XmlElement, name: string): XmlElement | undefined =>
  elementsOf(element, name)[0];

/**
 * The smallest stand-in for the DOM that `paintSvg` uses, so the package needs no jsdom: elements
 * with attributes, children and `textContent`, and a document that creates them. There is no
 * `innerHTML`: asking for it throws, which is how a test shows the painter never touches it.
 */

export class FakeElement {
  readonly localName: string;
  readonly attrs = new Map<string, string>();
  readonly kids: FakeElement[] = [];
  readonly ownerDocument: FakeDocument;
  private text = '';
  parent: FakeElement | null = null;

  constructor(doc: FakeDocument, tag: string) {
    this.ownerDocument = doc;
    this.localName = tag;
  }

  get tagName(): string {
    return this.localName;
  }

  get children(): FakeElement[] {
    return this.kids;
  }

  get lastElementChild(): FakeElement | null {
    return this.kids[this.kids.length - 1] ?? null;
  }

  get innerHTML(): string {
    throw new Error('innerHTML must never be read');
  }

  set innerHTML(_value: string) {
    throw new Error('innerHTML must never be set');
  }

  get textContent(): string {
    return this.text;
  }

  set textContent(value: string) {
    this.text = value;
    this.kids.length = 0;
  }

  setAttribute(name: string, value: string): void {
    this.attrs.set(name, value);
  }

  getAttribute(name: string): string | null {
    return this.attrs.get(name) ?? null;
  }

  getAttributeNames(): string[] {
    return [...this.attrs.keys()];
  }

  removeAttribute(name: string): void {
    this.attrs.delete(name);
  }

  appendChild(child: FakeElement): FakeElement {
    child.parent = this;
    this.kids.push(child);

    return child;
  }

  replaceChild(next: FakeElement, old: FakeElement): FakeElement {
    const i = this.kids.indexOf(old);

    if (i < 0) throw new Error('not a child');

    next.parent = this;
    old.parent = null;
    this.kids[i] = next;

    return old;
  }

  removeChild(child: FakeElement): FakeElement {
    const i = this.kids.indexOf(child);

    if (i < 0) throw new Error('not a child');

    this.kids.splice(i, 1);
    child.parent = null;

    return child;
  }
}

export class FakeDocument {
  created = 0;

  createElementNS(_ns: string, tag: string): FakeElement {
    this.created += 1;

    return new FakeElement(this, tag);
  }
}

/** The element tree as the markup `sceneToSvg` writes, to compare the two. */
export function fakeToSvg(el: FakeElement, root = true): string {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const attrs = [
    ...(root ? ([['xmlns', 'http://www.w3.org/2000/svg']] as [string, string][]) : []),
    ...el.attrs,
  ]
    .map(([k, v]) => ` ${k}="${esc(v).replace(/"/g, '&quot;')}"`)
    .join('');

  if (el.kids.length === 0 && el.textContent === '') return `<${el.tagName}${attrs}/>`;

  if (el.kids.length === 0) return `<${el.tagName}${attrs}>${esc(el.textContent)}</${el.tagName}>`;

  return `<${el.tagName}${attrs}>${el.kids.map((c) => fakeToSvg(c, false)).join('')}</${el.tagName}>`;
}

export function fakeSvg(): { svg: SVGSVGElement; el: FakeElement; doc: FakeDocument } {
  const doc = new FakeDocument();
  const el = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');

  return { svg: el as unknown as SVGSVGElement, el, doc };
}

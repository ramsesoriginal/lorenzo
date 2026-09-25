// The static demo (ADR 0106): the editor over a fake, in-memory resolver, so everything
// works without an API. Bundled to demo.js by `mise run //packages/lorenzoscript-editor:build`.
import { parse, type Reference, type Resolver, references, render } from '@lorenzo/lorenzoscript';
import { createEditor, type Editor } from '../src';

/** Served as a blob: URL, the way an app serves a picture it fetched with the viewer's token. */
const SKETCH = URL.createObjectURL(
  new Blob(
    [
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 90">',
      '<rect width="240" height="90" rx="8" fill="#f4efe5"/>',
      '<path d="M40 45h140l16-7v14l-16-7" stroke="#08131f" stroke-width="5" fill="none" stroke-linejoin="round"/>',
      '<path d="M64 27v36" stroke="#b88a3b" stroke-width="7" stroke-linecap="round"/>',
      '<path d="M196 45c22-14 26-26 22-38 12 16 8 30-8 38 16 8 20 22 8 38 4-12 0-24-22-38z" fill="#7b2638"/>',
      '</svg>',
    ],
    { type: 'image/svg+xml' },
  ),
);

const ENTITIES: Record<string, { name: string; picture?: string }> = {
  ashfang: { name: 'Ashfang', picture: SKETCH },
  emberdeep: { name: 'Emberdeep' },
};
const CALENDAR: Record<string, string> = { 'harptos 1492-mirtul-12': '12 Mirtul 1492 DR' };

const resolve: Resolver = {
  entity: ({ hint, slug }) => {
    const entity = ENTITIES[slug];
    return entity ? { href: `#${hint || 'entity'}/${slug}`, title: entity.name } : null;
  },
  image: ({ slug }) => {
    const picture = ENTITIES[slug]?.picture;
    return picture ? { src: picture } : null;
  },
  calendar: (expression) => CALENDAR[expression] ?? null,
};

/** What an author sees about each reference: the one place a broken link shows. */
function describe(ref: Reference): string {
  switch (ref.kind) {
    case 'entity':
    case 'image': {
      const target = ref.hint ? `${ref.hint}/${ref.slug}` : ref.slug;
      const what = ref.kind === 'image' ? 'Picture of' : 'Link to';
      return `${what} ${target}: ${ENTITIES[ref.slug]?.name ?? 'no entity has this slug yet'}`;
    }
    case 'date':
      return `Date: ${ref.date}`;
    case 'calendar':
      return `In-world date "${ref.expression}": ${CALENDAR[ref.expression] ?? 'not a date this calendar reads'}`;
  }
}

const byId = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const textarea = byId<HTMLTextAreaElement>('description');
const layout = byId<HTMLSelectElement>('layout');
const found = byId<HTMLUListElement>('references');

let editor: Editor | undefined;
function start(): void {
  editor?.destroy();
  editor = createEditor({
    textarea,
    layout: layout.value === 'tabs' ? 'tabs' : 'split',
    render: (source) => {
      const doc = parse(source);
      found.replaceChildren(
        ...references(doc).map((ref) => {
          const item = document.createElement('li');
          item.textContent = describe(ref);
          return item;
        }),
      );
      return render(doc, { resolve, locale: [...navigator.languages] });
    },
  });
}

layout.addEventListener('change', start);
start();
byId('unbuilt').remove();

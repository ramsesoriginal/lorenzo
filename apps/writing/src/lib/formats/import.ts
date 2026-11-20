// Bring documents in as Chapters (ADR 0521): one Chapter for a single file, a new Book with a
// Chapter for each file for several. The writing is the file's own text; its [[links]] stay as
// they are, for the author to review with the link review.
import { client, unwrap } from '../api';
import { countLinks, type Imported } from './markdown';

export type ImportResult = {
  /** The page to open: the Chapter, or the Book's first Edition. */
  entry: string;
  /** What was made, named for the author. */
  name: string;
  chapters: number;
  links: number;
};

async function makeChapter(tenant: string, doc: Imported): Promise<string> {
  const made = await unwrap(
    await client.POST('/tenants/{tenant_id}/writing/chapters', {
      params: { path: { tenant_id: tenant } },
      body: { id: crypto.randomUUID(), name: doc.title },
    }),
  );
  if (doc.content.length > 0)
    await unwrap(
      await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenant, entity_id: made.id } },
        body: {
          type: 'manuscript',
          title: 'Manuscript',
          content: doc.content,
          is_public: false,
          locale: 'en',
        },
      }),
    );
  return made.id;
}

/** Make the documents into Chapters; several go into a new Book, in the order given. */
export async function importDocuments(
  tenant: string,
  docs: Imported[],
  bookName = 'Imported writing',
): Promise<ImportResult> {
  if (docs.length === 0) throw new Error('There is nothing to import.');
  const links = docs.reduce((sum, doc) => sum + countLinks(doc.content), 0);
  const [only] = docs;
  if (docs.length === 1 && only) {
    const id = await makeChapter(tenant, only);
    return { entry: id, name: only.title, chapters: 1, links };
  }
  const book = await unwrap(
    await client.POST('/tenants/{tenant_id}/writing/books', {
      params: { path: { tenant_id: tenant } },
      body: {
        id: crypto.randomUUID(),
        first_edition_id: crypto.randomUUID(),
        name: bookName.slice(0, 300),
      },
    }),
  );
  const edition = book.editions[0]?.id;
  if (!edition) throw new Error('The new Book has no Edition to place the Chapters in.');
  const chapters: string[] = [];
  for (const doc of docs) chapters.push(await makeChapter(tenant, doc));
  const outline = await unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}', {
      params: { path: { tenant_id: tenant, id: edition } },
    }),
  );
  await unwrap(
    await client.PUT('/tenants/{tenant_id}/writing/entries/{id}/composition', {
      params: { path: { tenant_id: tenant, id: edition }, header: { 'if-match': outline.version } },
      body: { elements: [...outline.elements.map((element) => element.id), ...chapters] },
    }),
  );
  return { entry: edition, name: bookName, chapters: chapters.length, links };
}

const MARKDOWN = /\.(md|markdown|txt)$/i;

/** The files a Markdown import can read, in name order; the rest are named so they can be said. */
export function sortFiles(files: File[]): { readable: File[]; skipped: string[] } {
  const path = (file: File) => file.webkitRelativePath || file.name;
  const sorted = [...files].sort((a, b) =>
    path(a).localeCompare(path(b), undefined, { numeric: true, sensitivity: 'base' }),
  );
  return {
    readable: sorted.filter((file) => MARKDOWN.test(file.name)),
    skipped: sorted.filter((file) => !MARKDOWN.test(file.name)).map((file) => file.name),
  };
}

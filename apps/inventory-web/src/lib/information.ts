// An entity's information, read and written (ADR 0101, 0109) for the item
// page and Manage items (ADR 0112): its descriptions, notes, and the rest.
import { client, type components, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { viewerLocales } from './me';

export type Information = components['schemas']['InformationOut'];
type Payload = Information['payloads'][number];
export type TextPayload = Extract<Payload, { kind: 'description' }>;

/** What a form edits: the information's title, type and visibility, and its text. */
export type InformationDraft = { title: string; type: string; isPublic: boolean; content: string };

/** If-Match for a row read from a response body: its JSON `updated_at` (ADR 0108). */
const ifMatch = (row: { updated_at: string }) => ({ 'if-match': `W/"${row.updated_at}"` });

/** The first text payload, the one an editor changes; ADR 0101 has no route to add another. */
export const textOf = (info: Information): TextPayload | undefined =>
  info.payloads.find((p): p is TextPayload => p.kind === 'description');

/** Every piece of the entity's information the viewer may see, in order (ADR 0109). */
export async function listInformation(tenantId: string, entityId: string): Promise<Information[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: {
          path: { tenant_id: tenantId, entity_id: entityId },
          query: { page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}

/** The entity's description, the one of type `description`, if the viewer may see it. */
export async function getDescription(
  tenantId: string,
  entityId: string,
): Promise<Information | null> {
  const [description] = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: {
        path: { tenant_id: tenantId, entity_id: entityId },
        query: { type: ['description'], size: 1 },
      },
    }),
  ).then((page) => page.items);
  return description ?? null;
}

/** A new piece of information with one text payload, in the viewer's first language. */
export async function createInformation(
  tenantId: string,
  entityId: string,
  draft: InformationDraft,
): Promise<void> {
  const [locale = 'en-US'] = await viewerLocales();
  await unwrap(
    await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
      body: {
        title: draft.title,
        type: draft.type,
        is_public: draft.isPublic,
        content: draft.content,
        locale,
      },
    }),
  );
}

/**
 * Saves what changed: the text on its payload, then the title, type and visibility on the
 * information, each with If-Match. Two writes at most; if the second fails, the error says
 * the first went through.
 */
export async function updateInformation(
  tenantId: string,
  info: Information,
  draft: InformationDraft,
): Promise<void> {
  const text = textOf(info);
  const textChanged = draft.content !== (text?.content ?? '');
  if (textChanged && !text) throw new Error('This information has no text to change.');
  if (text && textChanged) {
    await unwrap(
      await client.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
        params: { path: { tenant_id: tenantId, payload_id: text.id }, header: ifMatch(text) },
        body: { content: draft.content },
      }),
    );
  }
  const body = {
    ...(draft.title !== info.title && { title: draft.title }),
    ...(draft.type !== info.type && { type: draft.type }),
    ...(draft.isPublic !== info.is_public && { is_public: draft.isPublic }),
  };
  if (Object.keys(body).length === 0) return;
  try {
    await unwrap(
      await client.PATCH('/tenants/{tenant_id}/information/{information_id}', {
        params: { path: { tenant_id: tenantId, information_id: info.id }, header: ifMatch(info) },
        body,
      }),
    );
  } catch (e) {
    if (!textChanged) throw e;
    const reason = e instanceof Error ? e.message : String(e);
    throw new Error(`The text was saved, but the rest wasn't: ${reason}`);
  }
}

/** Deletes a piece of information and its payloads, unless someone changed it since it was read. */
export async function deleteInformation(tenantId: string, info: Information): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/information/{information_id}', {
      params: { path: { tenant_id: tenantId, information_id: info.id }, header: ifMatch(info) },
    }),
  );
}

/**
 * What a description editor starts with: the description the item has, or a new one titled
 * with the item's name (ADR 0112). The title is the item's displayed name too (ADR 0019).
 */
export function descriptionDraft(info: Information | null, name: string): InformationDraft {
  if (!info) return { title: name, type: 'description', isPublic: true, content: '' };
  const content = textOf(info)?.content ?? '';
  return { title: info.title, type: 'description', isPublic: info.is_public, content };
}

/**
 * Saves a description draft: a change to the one there is, or a new one if it says anything:
 * some text, or a display title other than the name (an empty one shows the name, ADR 0067).
 */
export async function saveDescription(
  tenantId: string,
  entityId: string,
  info: Information | null,
  draft: InformationDraft,
  name: string,
): Promise<void> {
  if (info) return updateInformation(tenantId, info, draft);
  const titled = draft.title !== '' && draft.title !== name;
  if (draft.content.trim() || titled) await createInformation(tenantId, entityId, draft);
}

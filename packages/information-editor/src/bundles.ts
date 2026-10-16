import { LorenzoApiError, type LorenzoClient, type Schema, unwrap } from '@lorenzo/api-client';

export type Information = Schema<'InformationOut'>;
export type Payload = Information['payloads'][number];
export type DraftPayload = Payload & { file?: File };
export const INITIAL_TEXT = 'initial-text';
export type BundleReceipt = {
  id: string;
  information?: Information;
  initialPayloadId?: string | undefined;
};
export type BundleFields = { payloads: DraftPayload[]; receipt: BundleReceipt };
type Metadata = { title: string; type: string; isPublic: boolean };

export function initialText(content: string): DraftPayload {
  return { id: INITIAL_TEXT, kind: 'description', content, locale: '', order: 0, updated_at: '' };
}

const version = (row: { updated_at: string }) => ({ 'if-match': `W/"${row.updated_at}"` });
const conflict = () =>
  new LorenzoApiError(
    'This information changed while it was being saved. Your draft is still here; review the current information before trying again.',
    412,
  );

/** Compare contents while allowing the bundle version to advance through our own structural write. */
export function sameBundle(
  a: Information,
  b: Information,
  ignorePayloadVersions: readonly string[] = [],
): boolean {
  const plain = (info: Information) => ({
    ...info,
    updated_at: '',
    payloads: info.payloads.map((p) => ({
      ...p,
      ...(ignorePayloadVersions.includes(p.id) ? { updated_at: '' } : {}),
    })),
  });
  const canonical = (value: unknown): unknown =>
    Array.isArray(value)
      ? value.map(canonical)
      : value !== null && typeof value === 'object'
        ? Object.fromEntries(
            Object.entries(value)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, v]) => [key, canonical(v)]),
          )
        : value;
  return JSON.stringify(canonical(plain(a))) === JSON.stringify(canonical(plain(b)));
}

function informationVersion(response: Response): string {
  const value = response.headers.get('etag')?.replace(/^W\//, '');
  if (!value) throw new Error('The information version is missing. Your draft has been kept.');
  const stamp: unknown = JSON.parse(value);
  if (typeof stamp !== 'string') throw new Error('The information version could not be read.');
  return stamp;
}

/** Save an ordered bundle without replacing unknown payloads or broadening its audience.
 * The receipt survives a failed Save in the form; stable ids make retrying uploads harmless.
 */
export async function saveInformationBundle(options: {
  client: LorenzoClient;
  tenantId: string;
  entityId?: string;
  original?: Information;
  draft: Metadata & BundleFields;
  locale?: string;
}): Promise<Information> {
  const { client, tenantId, draft } = options;
  const receipt = draft.receipt;
  let info = receipt.information ?? options.original;
  if (!info) {
    if (!options.entityId) throw new Error('Choose the entry this information belongs to.');
    const first = draft.payloads.find((p) => p.id === INITIAL_TEXT);
    info = await unwrap(
      await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path: { tenant_id: tenantId, entity_id: options.entityId } },
        body: {
          id: receipt.id,
          title: draft.title,
          type: draft.type,
          is_public: false,
          content: first?.kind === 'description' ? first.content : '',
          locale: options.locale ?? 'en-US',
        },
      }),
    );
    receipt.initialPayloadId = info.payloads.find((p) => p.kind === 'description')?.id;
  }
  receipt.information = info;
  const path = { tenant_id: tenantId, information_id: info.id };
  const remember = (next: Information) => {
    info = next;
    receipt.information = next;
    return next;
  };
  const current = () => receipt.information as Information;
  const read = async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/information/{information_id}/editor', {
        params: { path },
      }),
    );
  const readBack = async (expected: Information, ignore: readonly string[] = []) => {
    const actual = await read();
    if (!sameBundle(actual, expected, ignore)) throw conflict();
    return remember(actual);
  };
  const recover = async (error: unknown, expected: Information, ignore: readonly string[] = []) => {
    if (!(error instanceof LorenzoApiError) || ![404, 412].includes(error.status)) throw error;
    return readBack(expected, ignore);
  };
  const wanted = draft.payloads.map((p) => ({
    ...p,
    id: p.id === INITIAL_TEXT ? (receipt.initialPayloadId ?? p.id) : p.id,
  }));
  const locale =
    options.locale ?? current().payloads.find((p) => p.kind === 'description')?.locale ?? 'en-US';
  for (const payload of wanted) {
    const old = current().payloads.find((p) => p.id === payload.id);
    if (old) {
      if (
        old.kind === 'description' &&
        payload.kind === 'description' &&
        (old.content !== payload.content || (payload.locale && old.locale !== payload.locale))
      ) {
        const expected = {
          ...current(),
          payloads: current().payloads.map((p) =>
            p.id === old.id
              ? { ...old, content: payload.content, locale: payload.locale || old.locale }
              : p,
          ),
        };
        try {
          const saved = await unwrap(
            await client.PATCH('/tenants/{tenant_id}/payloads/{payload_id}', {
              params: { path: { tenant_id: tenantId, payload_id: old.id }, header: version(old) },
              body: { content: payload.content, locale: payload.locale || old.locale },
            }),
          );
          remember({
            ...current(),
            payloads: current().payloads.map((p) => (p.id === saved.id ? saved : p)),
          });
        } catch (error) {
          await recover(error, expected, [old.id]);
        }
      }
      continue;
    }
    let saved: Payload;
    let response: Response;
    if (payload.kind === 'description') {
      const result = await client.POST('/tenants/{tenant_id}/information/{information_id}/texts', {
        params: { path, header: version(current()) },
        body: { id: payload.id, content: payload.content, locale: payload.locale || locale },
      });
      saved = await unwrap(result);
      response = result.response;
    } else if (payload.kind === 'picture' && payload.file) {
      const file = payload.file;
      const result = await client.POST(
        '/tenants/{tenant_id}/information/{information_id}/payloads',
        {
          params: { path, header: version(current()) },
          body: { file: file.name, payload_id: payload.id },
          bodySerializer: () => {
            const data = new FormData();
            data.append('file', file);
            data.append('payload_id', payload.id);
            return data;
          },
        },
      );
      saved = await unwrap(result);
      response = result.response;
    } else throw new Error('This payload cannot be added by this editor.');
    const expected = {
      ...current(),
      updated_at: informationVersion(response),
      payloads: [...current().payloads, saved].sort((a, b) => a.order - b.order),
    };
    // A replay may have followed a lost response. Verify its surrounding bundle before using
    // the current version; never adopt somebody else's intervening structural change silently.
    if (response.status === 200) await readBack(expected);
    else remember(expected);
  }
  const ids = wanted.map((p) => p.id);
  for (const payload of [...current().payloads]) {
    if (ids.includes(payload.id)) continue;
    if (!['description', 'picture'].includes(payload.kind))
      throw new Error('Keep the payloads this editor cannot change.');
    const expected = {
      ...current(),
      payloads: current().payloads.filter((p) => p.id !== payload.id),
    };
    try {
      await unwrap(
        await client.DELETE('/tenants/{tenant_id}/payloads/{payload_id}', {
          params: {
            path: { tenant_id: tenantId, payload_id: payload.id },
            header: version(payload),
          },
        }),
      );
      await readBack(expected);
    } catch (error) {
      await recover(error, expected);
    }
  }
  if (JSON.stringify(current().payloads.map((p) => p.id)) !== JSON.stringify(ids)) {
    const expected = {
      ...current(),
      payloads: ids.map((id, index) => ({
        ...(current().payloads.find((p) => p.id === id) as Payload),
        order: current().payloads[index]?.order ?? index,
      })),
    };
    try {
      remember(
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/information/{information_id}/payloads/order', {
            params: { path, header: version(current()) },
            body: { payload_ids: ids },
          }),
        ),
      );
    } catch (error) {
      // Reordering also versions each moved payload; contents must still match our base.
      await recover(error, expected, ids);
    }
  }
  const body = {
    ...(draft.title !== current().title && { title: draft.title }),
    ...(draft.type !== current().type && { type: draft.type }),
    ...(draft.isPublic !== current().is_public && { is_public: draft.isPublic }),
  };
  if (Object.keys(body).length) {
    const expected = { ...current(), ...body };
    try {
      remember(
        await unwrap(
          await client.PATCH('/tenants/{tenant_id}/information/{information_id}', {
            params: { path, header: version(current()) },
            body,
          }),
        ),
      );
    } catch (error) {
      await recover(error, expected);
    }
  }
  return readBack(current());
}

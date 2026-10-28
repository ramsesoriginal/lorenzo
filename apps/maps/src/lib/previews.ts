// The card an entry opens when a mark or a row of the places list is pointed at (ADR 0349, 0350):
// what the API's preview route gives, asked once per entry for the page.
import { LorenzoApiError } from '@lorenzo/api-client';
import { createCardCache } from '@lorenzo/entry-preview';
import { client, loadFile, unwrap } from './api';

export const loadCard = createCardCache(
  async (tenant, id) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/preview', {
        params: { path: { tenant_id: tenant, entity_id: id } },
      }),
    ),
  (error) => error instanceof LorenzoApiError && error.status === 404,
);

export const loadPicture = (url: string) => loadFile({ url });

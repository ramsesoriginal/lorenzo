// The cards of this page, asked of the API (ADR 0264); the cache is packages/entry-preview's.
import { LorenzoApiError } from '@lorenzo/api-client';
import { createCardCache } from '@lorenzo/entry-preview';
import { client, unwrap } from './api';

export const loadCard = createCardCache(
  async (tenant, id) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/preview', {
        params: { path: { tenant_id: tenant, entity_id: id } },
      }),
    ),
  (error) => error instanceof LorenzoApiError && error.status === 404,
);

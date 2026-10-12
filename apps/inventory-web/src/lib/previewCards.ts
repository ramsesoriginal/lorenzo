// The cards of this page, asked of the API (ADR 0264); the pure parts are linkPreview.ts's.
import { client, unwrap } from './api';
import { createCardCache } from './linkPreview';

export const loadCard = createCardCache(async (tenant, id) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/preview', {
      params: { path: { tenant_id: tenant, entity_id: id } },
    }),
  ),
);

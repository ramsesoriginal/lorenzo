import { client, unwrap } from './api';
import { cached } from './cache';

// What an entity (an item, a character, a group) is called, for putting beside its id: its slug,
// else its name. Null when it can't be read, such as one that has been deleted, since a name is a
// convenience and never the reason something fails.
export async function getEntityLabel(tenantId: string, entityId: string): Promise<string | null> {
  try {
    const entity = await cached(`entity:${tenantId}:${entityId}`, async () =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: entityId } },
        }),
      ),
    );

    return entity.slug ?? entity.name;
  } catch {
    return null;
  }
}

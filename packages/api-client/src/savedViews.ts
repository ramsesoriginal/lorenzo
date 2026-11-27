import type { LorenzoClient } from './index';

/**
 * A person's saved views of one list in one library (ADR 0532): the three calls the web shell's
 * saved-views control needs, for `app` and `list` (`'social'`, `'relationships'`).
 */
export function savedViewStore(client: LorenzoClient, tenantId: string, app: string, list: string) {
  const path = { tenant_id: tenantId };

  return {
    async list() {
      const got = await client.GET('/tenants/{tenant_id}/saved-views', {
        params: { path, query: { app, list } },
      });

      return (got.data ?? []).map((view) => ({ id: view.id, name: view.name, query: view.query }));
    },
    async save(name: string, query: Record<string, unknown>) {
      const made = await client.POST('/tenants/{tenant_id}/saved-views', {
        params: { path },
        body: { app, list, name, query },
      });

      if (!made.data) throw new Error('The view was not saved.');

      return { id: made.data.id, name: made.data.name, query: made.data.query };
    },
    async remove(id: string) {
      await client.DELETE('/tenants/{tenant_id}/saved-views/{view_id}', {
        params: { path: { ...path, view_id: id } },
      });
    },
  };
}

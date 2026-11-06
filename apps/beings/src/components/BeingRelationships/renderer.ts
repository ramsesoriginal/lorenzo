import { createGraphView, type GraphViewHandle } from '@lorenzo/graph-renderer';
import { client, unwrap } from '../../lib/api';
import { BRANDING_CSS_URL } from '../../lib/config';
import { errorMessage } from '../../lib/errorMessage';
import { relationshipSentence } from '../../lib/relationshipWords';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Being relationships');

/** The most relationships the section reads: a being has a few, and the rest are in Social. */
const READ = 40;

export function renderBeingRelationships(root: HTMLElement) {
  const status = required<HTMLElement>(root, '[data-relationship-status]');
  const host = required<HTMLElement>(root, '[data-relationship-graph]');
  const list = required<HTMLUListElement>(root, '[data-relationship-list]');
  let generation = 0;
  let drawing: GraphViewHandle | null = null;
  return {
    async load(tenantId: string, beingId: string, beingName: string) {
      const turn = ++generation;
      drawing?.destroy();
      drawing = null;
      root.hidden = true;
      host.hidden = true;
      list.replaceChildren();
      status.textContent = '';
      try {
        const page = await unwrap(
          await client.GET('/tenants/{tenant_id}/relationships', {
            params: { path: { tenant_id: tenantId }, query: { end: beingId, size: READ } },
            cache: 'no-cache',
          }),
        );
        if (turn !== generation || !root.isConnected) return;
        // A being with no relationship you may see shows nothing: no empty section.
        if (page.items.length === 0) return;
        root.hidden = false;
        const names = new Map<string, string>([[beingId, beingName]]);
        for (const row of page.items) {
          names.set(row.end_a.id, row.end_a.name);
          names.set(row.end_b.id, row.end_b.name);
          const item = document.createElement('li');
          item.textContent = relationshipSentence(row);
          list.append(item);
        }
        host.hidden = false;
        drawing = createGraphView(host, {
          title: `Relationships of ${beingName}`,
          iconBase: `${BRANDING_CSS_URL}/icons.svg`,
          model: {
            nodes: [...names].map(([id, name]) => ({ id, name })),
            edges: page.items.map((row) => ({
              id: row.id,
              a: row.end_a.id,
              b: row.end_b.id,
              directed: row.one_way,
              label: row.name,
              status: 'direct' as const,
            })),
          },
          view: { layout: 'radial', focus: beingId, seed: 1, labels: true },
        });
        status.textContent =
          page.total > page.items.length
            ? `Showing ${page.items.length} of ${page.total}: open Lorenzo Social for the rest.`
            : '';
      } catch (error) {
        if (turn !== generation) return;
        root.hidden = true;
        status.textContent = `Could not load relationships. ${errorMessage(error)}`;
      }
    },
  };
}

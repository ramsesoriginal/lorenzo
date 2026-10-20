import { client, unwrap } from '../../lib/api';
import { calendarUrl, loadAppLinks } from '../../lib/appLinks';
import { errorMessage } from '../../lib/errorMessage';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Being Events');

export function renderBeingEvents(root: HTMLElement) {
  const status = required<HTMLElement>(root, '[data-event-status]');
  const list = required<HTMLOListElement>(root, '[data-event-list]');
  const more = required<HTMLButtonElement>(root, '[data-more-events]');
  let generation = 0;
  return {
    async load(tenantId: string, tenantAddress: string, beingId: string) {
      const turn = ++generation;
      root.hidden = true;
      list.replaceChildren();
      more.hidden = true;
      let page = 1;
      async function read() {
        more.disabled = true;
        try {
          const access = await unwrap(
            await client.GET('/tenants/{tenant_id}/events/access', {
              params: { path: { tenant_id: tenantId } },
            }),
          );
          if (turn !== generation) return;
          if (!access.can_order) {
            list.replaceChildren();
            root.hidden = true;
            return;
          }
          await loadAppLinks();
          const events = await unwrap(
            await client.GET('/tenants/{tenant_id}/events', {
              params: {
                path: { tenant_id: tenantId },
                query: { being_id: beingId, sort: 'order', page, size: 30 },
              },
            }),
          );
          if (turn !== generation || !root.isConnected) return;
          root.hidden = false;
          for (const event of events.items) {
            const row = document.createElement('li');
            const href = calendarUrl(tenantAddress, { ...event, kinds: ['event'] });
            const title = document.createElement(href ? 'a' : 'span');
            title.textContent = event.name;
            if (title instanceof HTMLAnchorElement && href) title.href = href;
            row.append(title);
            if (event.order_basis) {
              const basis = document.createElement('span');
              basis.className = 'caption';
              basis.textContent = ` · ${{ causal: 'Causal', ruled: 'Recorded order', linearized: 'Linearized' }[event.order_basis]}`;
              row.append(basis);
            }
            list.append(row);
          }
          status.textContent = events.total ? '' : 'No participating Events recorded.';
          more.hidden = page >= (events.pages ?? 0);
          more.onclick = () => {
            page++;
            void read();
          };
        } catch (error) {
          if (turn !== generation) return;
          list.replaceChildren();
          more.hidden = true;
          status.textContent = `Could not load Events. ${errorMessage(error)}`;
          // A denial must remove names and order previously shown by this section.
          root.hidden = true;
        } finally {
          more.disabled = false;
        }
      }
      await read();
    },
  };
}

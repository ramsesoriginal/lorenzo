import { client, unwrap } from './api';
import { button, el, feedback, field, message } from './dom';

export function entryPicker(
  tenantId: string,
  label: string,
  kind: 'being' | 'event' | undefined,
  chosen: (entry: { id: string; name: string; slug?: string | null }) => void,
): HTMLElement {
  const host = el('div', '', 'stack-tight');
  const query = field(label);
  const results = el('div', '', 'row');
  const status = feedback();
  let request = 0;
  host.append(
    query.label,
    button(
      `Search ${kind === 'being' ? 'beings' : kind === 'event' ? 'Events' : 'entries'}`,
      async () => {
        const turn = ++request;
        status.busy('Searching…');
        try {
          const page = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: {
                path: { tenant_id: tenantId },
                query: { q: query.input.value, kind: kind ? [kind] : undefined, size: 30 },
              },
            }),
          );
          if (turn !== request) return;
          results.replaceChildren();
          for (const entry of page.items)
            results.append(button(entry.name, () => chosen(entry), true));
          status.say(page.items.length ? 'Choose an entry.' : 'No matching entries.');
        } catch (error) {
          if (turn === request) status.fail(message(error));
        }
      },
      true,
      'search',
    ),
    results,
    status.node,
  );
  return host;
}

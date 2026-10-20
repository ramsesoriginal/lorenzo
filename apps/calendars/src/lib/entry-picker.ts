import { client, unwrap } from './api';
import { button, el, field, message } from './dom';
export function entryPicker(
  tenantId: string,
  label: string,
  kind: 'being' | 'event',
  chosen: (entry: { id: string; name: string; slug?: string | null }) => void,
): HTMLElement {
  const host = el('div', '', 'stack-tight');
  const query = field(label);
  const results = el('div', '', 'stack-tight');
  const status = el('p');
  status.setAttribute('role', 'status');
  let request = 0;
  host.append(
    query.label,
    button(
      `Search ${kind === 'being' ? 'beings' : 'Events'}`,
      async () => {
        const turn = ++request;
        status.textContent = 'Searching…';
        try {
          const page = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: {
                path: { tenant_id: tenantId },
                query: { q: query.input.value, kind: [kind], size: 30 },
              },
            }),
          );
          if (turn !== request) return;
          results.replaceChildren();
          for (const entry of page.items)
            results.append(button(entry.name, () => chosen(entry), true));
          status.textContent = page.items.length ? 'Choose an entry.' : 'No matching entries.';
        } catch (error) {
          if (turn === request) status.textContent = message(error);
        }
      },
      true,
    ),
    results,
    status,
  );
  return host;
}

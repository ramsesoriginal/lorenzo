import { bindLinkIntent, createPrefetchQueue } from '@lorenzo/read-cache';
import { client, unwrap } from './api';
import { sessionReads } from './read-cache';

// Asking ahead (ADR 0325): when the pointer rests on a link to a Session, the keyboard arrives at it
// or it is touched, that Session is read, so the page it opens finds it held. A read only: it
// creates nothing, and nothing is read until a viewer is known.
const queue = createPrefetchQueue();
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
let bound = false;

export function bindSessionPrefetch() {
  if (bound || typeof document === 'undefined') return;

  bound = true;
  document.addEventListener('astro:before-swap', () => queue.reset());
  bindLinkIntent({
    onIntent(link) {
      if (!sessionReads.scoped()) return;

      const url = new URL(link.href);
      const tenant = url.searchParams.get('tenant');
      const id = url.searchParams.get('id');

      if (url.pathname !== '/session/' || !tenant || !id || !ID.test(tenant) || !ID.test(id))
        return;

      queue.enqueue(`session/${id}`, async () =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/sessions/{session_id}', {
            params: { path: { tenant_id: tenant, session_id: id } },
          }),
        ),
      );
    },
  });
}

import { client, unwrap } from './api';

let lastJoin: { parent: string; source: string; destination: string; operation: string } | null =
  null;

/** The join this page just made on `parent`, once: reading it forgets it. */
export function takeJoin(parent: string) {
  const join = lastJoin?.parent === parent ? lastJoin : null;
  lastJoin = null;
  return join;
}

/** Take back a join, while the destination is as `version` says (ADR 0518). */
export async function undoJoin(
  tenant: string,
  join: { source: string; destination: string; operation: string },
): Promise<void> {
  const destination = await unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}', {
      params: { path: { tenant_id: tenant, id: join.destination } },
    }),
  );
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/writing/entries/{id}/joins/{operation_id}', {
      params: {
        path: { tenant_id: tenant, id: join.source, operation_id: join.operation },
        header: { 'if-match': destination.version },
      },
    }),
  );
}

export function joinControls(
  tenant: string,
  parent: string,
  parentVersion: string,
  source: { id: string; name?: string | null },
  destination: { id: string; name?: string | null },
  done: () => Promise<void>,
  mode: 'previous' | 'parent' = 'previous',
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = mode === 'parent' ? 'Join into parent' : 'Join with previous';
  details.append(summary);
  let loaded = false;
  details.addEventListener('toggle', () => {
    if (!details.open || loaded) return;
    loaded = true;
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    details.append(status);
    void (async () => {
      const read = async (id: string) =>
        unwrap(
          await client.GET('/tenants/{tenant_id}/writing/entries/{id}', {
            params: { path: { tenant_id: tenant, id } },
          }),
        );
      const [from, to] = await Promise.all([read(source.id), read(destination.id)]);
      status.textContent = `Join “${from.name}” into “${to.name}”? ${mode === 'parent' ? 'Its contents will take its place in this outline, without its Chapter heading.' : 'Its writing will follow the earlier Chapter.'} Its name and notes will remain at the old address, with a link to the joined section.`;
      const confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.className = 'btn btn-secondary';
      confirm.textContent = 'Join chapters';
      const operation = crypto.randomUUID();
      confirm.addEventListener('click', () => {
        confirm.disabled = true;
        void (async () => {
          await unwrap(
            await client.POST('/tenants/{tenant_id}/writing/entries/{id}/joins/{operation_id}', {
              params: {
                path: { tenant_id: tenant, id: source.id, operation_id: operation },
                header: { 'if-match': from.version },
              },
              body: {
                mode,
                destination_id: destination.id,
                parent_id: parent,
                destination_version: to.version,
                parent_version: parentVersion,
              },
            }),
          );
          lastJoin = {
            parent,
            source: source.id,
            destination: destination.id,
            operation,
          };
          await done();
        })()
          .catch((error: unknown) => {
            status.textContent =
              error instanceof Error ? error.message : 'These Chapters could not be joined.';
          })
          .finally(() => {
            confirm.disabled = false;
          });
      });
      details.append(confirm);
    })().catch((error: unknown) => {
      status.textContent =
        error instanceof Error ? error.message : 'These Chapters could not be read.';
    });
  });
  return details;
}

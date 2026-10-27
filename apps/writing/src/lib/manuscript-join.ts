import { client, unwrap } from './api';

export function joinControls(
  tenant: string,
  parent: string,
  parentVersion: string,
  source: { id: string; name?: string | null },
  destination: { id: string; name?: string | null },
  done: () => Promise<void>,
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Join with previous';
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
      status.textContent = `Join “${from.name}” into “${to.name}”? Its writing will follow the earlier Chapter. Its name and notes will remain at the old address, with a link to the joined section.`;
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
                destination_id: destination.id,
                parent_id: parent,
                destination_version: to.version,
                parent_version: parentVersion,
              },
            }),
          );
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

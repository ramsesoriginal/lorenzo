import { client, unwrap } from './api';
import { button, disclosure, el, entryHref, feedback, field, link, message } from './dom';

export function groupFromParticipants(tenantId: string, eventId: string): HTMLElement {
  const host = disclosure('Create group from event participants');
  const name = field('Group name', 'Event participants');
  name.input.required = true;
  const preview = el('ul', '', 'stack-tight');
  const status = feedback();
  const id = crypto.randomUUID();
  let version = '';
  let loading = false;
  let submitted = false;
  const save = button('Create group', async () => {
    if (!version || !name.input.reportValidity() || submitted) return;
    save.disabled = true;
    submitted = true;
    status.busy('Creating group…');
    try {
      const group = await unwrap(
        await client.POST('/tenants/{tenant_id}/events/{event_id}/participant-groups', {
          params: {
            path: { tenant_id: tenantId, event_id: eventId },
            header: { 'if-match': version },
          },
          body: { id, name: name.input.value },
        }),
      );
      status.say('Group created.');
      status.node.append(link(group.name, entryHref(tenantId, group.id)));
      name.input.disabled = true;
      refresh.disabled = true;
    } catch (error) {
      status.fail(
        `${message(error)} Your draft and retry identity are kept. If participants changed, refresh the preview before retrying.`,
      );
      submitted = false;
      save.disabled = false;
    }
  });
  save.disabled = true;
  const refresh = button(
    'Refresh group preview',
    async () => {
      if (loading) return;
      loading = true;
      save.disabled = true;
      try {
        const result = await client.GET('/tenants/{tenant_id}/events/{event_id}/participants', {
          params: { path: { tenant_id: tenantId, event_id: eventId } },
          cache: 'no-store',
        });
        const rows = await unwrap(result);
        version = result.response.headers.get('etag') ?? '';
        preview.replaceChildren(...rows.map((being) => el('li', being.name)));
        status.say(
          rows.length
            ? `${rows.length} participating being(s) will be copied.`
            : 'There are no participating beings to copy.',
        );
        save.disabled = !version || !rows.length || submitted;
      } catch (error) {
        version = '';
        status.fail(message(error));
      } finally {
        loading = false;
      }
    },
    true,
    'refresh',
  );
  const actions = el('div', '', 'row');
  actions.append(refresh, save);
  host.body.append(
    name.label,
    el(
      'p',
      'Copies the beings shown below into an ordinary group, including NPCs. Later participant changes will not change the group. Groups and their members are readable by library participants. Creating this group shares the shown list, without opening the Event or its notes.',
      'caption',
    ),
    preview,
    actions,
    status.node,
  );
  host.root.addEventListener('toggle', () => {
    if (host.root.open && !version) refresh.click();
  });
  return host.root;
}

import { client, unwrap } from './api';
import { button, el, message, select } from './dom';

export function creationVisibility() {
  const control = select('Entry visibility', [
    ['restricted', 'Restricted'], ['participants', 'Participants'], ['library', 'Everyone in this library'],
  ], 'restricted');
  return {
    ...control,
    setEvent(isEvent: boolean) {
      const option = control.input.querySelector<HTMLOptionElement>('option[value="participants"]');
      if (option) option.disabled = !isEvent;
      if (!isEvent && control.input.value === 'participants') control.input.value = 'restricted';
    },
    value: () => control.input.value as 'restricted' | 'participants' | 'library',
  };
}

export async function eventVisibility(tenantId: string, entityId: string, refresh: () => void) {
  const path = { tenant_id: tenantId, entity_id: entityId };
  const saved = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', { params: { path } });
  const audience = await unwrap(saved);
  const control = creationVisibility();
  control.input.value = audience.is_public ? 'library' : audience.shared_with_participants ? 'participants' : 'restricted';
  const host = el('section', '', 'panel stack-tight');
  const status = el('p'); status.setAttribute('role', 'status');
  const save = button('Save Event visibility', async () => {
    save.disabled = true;
    try {
      await unwrap(await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
        params: { path, header: { 'if-match': saved.response.headers.get('etag') ?? '' } },
        body: { ...audience, is_public: control.value() === 'library', shared_with_participants: control.value() === 'participants' },
      }));
      refresh();
    } catch (error) { status.textContent = `${message(error)} Your selection is kept. Reload the saved audience before retrying.`; }
    finally { save.disabled = false; }
  });
  host.append(el('h2', 'Event visibility'), control.label,
    el('p', 'Participants means players through their currently participating beings. Each note has its own audience. Individual grants below continue to apply.', 'caption'), save, status);
  return host;
}

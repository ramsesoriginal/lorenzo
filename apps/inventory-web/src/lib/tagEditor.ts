// Three-state tag editing on the item page (ADR 0103, 0112): each bool stat
// in the tenant's `tags` group is inherited, on, or explicitly off.
import { ApiError, client, type components, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { getEntityDetail } from './items';
import { statLabel } from './itemView';
import type { EntityDetail } from './types';

type Definition = components['schemas']['StatDefinitionOut'];
type State = 'inherited' | 'on' | 'off';

const STATES: [State, string][] = [
  ['inherited', 'Inherited'],
  ['on', 'On'],
  ['off', 'Off'],
];

/**
 * A tag's state from the entity's effective stat (ADR 0111's `own`), and what inheriting
 * gives when that's what it does now; a value of its own hides what it would inherit.
 */
export function tagState(stat: EntityDetail['stats'][number] | undefined): {
  state: State;
  hint: string;
} {
  if (stat?.own) return { state: stat.value === true ? 'on' : 'off', hint: '' };
  const effective = !stat ? 'not set' : stat.value === true ? 'on' : 'off';
  return { state: 'inherited', hint: ` (${effective})` };
}

/** The tenant's tags: every bool definition in its `tags` group, by name. */
async function tagDefinitions(tenantId: string): Promise<Definition[]> {
  const path = { tenant_id: tenantId };
  const query = (page: number) => ({ page, size: MAX_PAGE_SIZE });
  const [groups, definitions] = await Promise.all([
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/stat-groups', {
          params: { path, query: query(page) },
        }),
      ),
    ),
    fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/stat-definitions', {
          params: { path, query: query(page) },
        }),
      ),
    ),
  ]);
  const tags = groups.find((group) => group.name === 'tags');
  return definitions.filter((d) => d.stat_group_id === tags?.id && d.value_type === 'bool');
}

/** Sets a tag: PUT is on, PATCH explicitly off, DELETE back to inherited (ADR 0103). */
async function setTag(
  tenantId: string,
  entityId: string,
  definitionId: string,
  state: State,
): Promise<EntityDetail> {
  const params = {
    path: { tenant_id: tenantId, entity_id: entityId, stat_definition_id: definitionId },
  };
  const path = '/tenants/{tenant_id}/entities/{entity_id}/tags/{stat_definition_id}';
  if (state === 'on') return unwrap(await client.PUT(path, { params }));
  if (state === 'off') return unwrap(await client.PATCH(path, { params }));
  return unwrap(await client.DELETE(path, { params }));
}

const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text = '') =>
  Object.assign(document.createElement(tag), { className, textContent: text });

/**
 * Renders the editor into `container`. `onChanged` runs after every change, so the page
 * can show the tags readers now see.
 */
export async function renderTagEditor(
  container: HTMLElement,
  options: { tenantId: string; entityId: string; onChanged: () => void },
): Promise<void> {
  const { tenantId, entityId } = options;
  container.replaceChildren(make('p', 'status-text', 'Loading tags…'));
  let definitions: Definition[];
  let entity: EntityDetail;
  try {
    [definitions, entity] = await Promise.all([
      tagDefinitions(tenantId),
      getEntityDetail(tenantId, entityId),
    ]);
  } catch (e) {
    // Listing definitions needs tenant membership, unlike writing a tag (ADR 0112).
    const member = !(e instanceof ApiError && (e.status === 403 || e.status === 404));
    const reason = e instanceof Error ? e.message : String(e);
    container.replaceChildren(
      make(
        'p',
        'status-text',
        member ? `Couldn't load tags: ${reason}` : 'Only tenant members can see the list of tags.',
      ),
    );
    return;
  }
  if (definitions.length === 0) {
    container.replaceChildren(make('p', 'status-text', 'This tenant has no tags yet.'));
    return;
  }

  const status = make('p', 'status-text');
  status.setAttribute('role', 'status');
  const list = make('div', 'tag-editor');

  const draw = () => {
    const stats = new Map(entity.stats.map((stat) => [stat.name, stat]));
    list.replaceChildren(
      ...definitions.map((definition) => {
        const { state, hint } = tagState(stats.get(definition.name));
        const group = make('fieldset', 'tag-editor-tag');
        group.append(make('legend', '', statLabel(definition.name)));
        for (const [value, label] of STATES) {
          const choice = make('label', 'field-row');
          const radio = Object.assign(document.createElement('input'), {
            type: 'radio',
            name: `tag-${definition.id}`,
            value,
            checked: value === state,
          });
          radio.addEventListener('change', async () => {
            list.querySelectorAll('input').forEach((input) => {
              input.disabled = true;
            });
            status.classList.remove('error-text');
            status.textContent = 'Saving…';
            try {
              entity = await setTag(tenantId, entityId, definition.id, value);
              status.textContent = '';
              options.onChanged();
            } catch (e) {
              status.classList.add('error-text');
              status.textContent = e instanceof Error ? e.message : String(e);
            }
            draw();
          });
          choice.append(radio, value === 'inherited' ? label + hint : label);
          group.append(choice);
        }
        return group;
      }),
    );
  };
  draw();
  container.replaceChildren(list, status);
}

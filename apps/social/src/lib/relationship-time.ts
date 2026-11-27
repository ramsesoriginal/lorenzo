import { actions, button, card, el, empty, icon, link, relationshipHref } from './dom';
import { entryPicker } from './pickers';
import {
  listRelationships,
  type readRelationship,
  readThrough,
  replaceRelationship,
  writeThrough,
} from './social-api';
import { websNaming } from './web-api';

type Relationship = Awaited<ReturnType<typeof readRelationship>>['relationship'];

/**
 * When a relationship holds, and what it holds through (ADR 0405, ADR 0402): optional, so a relationship
 * with neither behaves as if time did not exist. Those who may write set them, and a refusal (an end
 * before a start, an Event they may not see) is shown as the API gave it, next to the control.
 */
export async function timeAndChain(
  tenant: string,
  id: string,
  version: string,
  relationship: Relationship,
  canEdit: boolean,
  redraw: () => Promise<void>,
): Promise<HTMLElement[]> {
  const sections: HTMLElement[] = [];
  const keep = {
    end_a: relationship.end_a.id,
    end_b: relationship.end_b.id,
    one_way: relationship.one_way,
  };
  const limits = (change: { starts_at?: string | null; ends_at?: string | null }) => ({
    ...keep,
    starts_at: relationship.starts_at?.id ?? null,
    ends_at: relationship.ends_at?.id ?? null,
    ...change,
  });

  // When it holds.
  const when = card();
  when.body.append(el('h2', 'When it holds', 'group-title'));
  const said = [
    relationship.starts_at ? `Since ${relationship.starts_at.name}` : '',
    relationship.ends_at ? `until ${relationship.ends_at.name}` : '',
  ].filter(Boolean);
  when.body.append(
    el(
      'p',
      said.length
        ? `${said.join(', ').replace(/^./, (c) => c.toUpperCase())}.`
        : 'It is not tied to any Event.',
      'status-text',
    ),
  );
  if (canEdit) {
    const since = entryPicker(tenant, 'Since this Event', { kind: 'event' });
    const until = entryPicker(tenant, 'Until this Event', { kind: 'event' });
    const set = (which: 'starts_at' | 'ends_at', picker: typeof since) => async () => {
      const picked = picker.value();
      if (!picked) throw new Error('Choose an Event first.');
      await replaceRelationship(tenant, id, version, limits({ [which]: picked }));
      await redraw();
    };
    const clear = (which: 'starts_at' | 'ends_at') => async () => {
      await replaceRelationship(tenant, id, version, limits({ [which]: null }));
      await redraw();
    };
    when.body.append(
      since.label,
      actions(
        button('Set since', set('starts_at', since)),
        ...(relationship.starts_at ? [button('Clear since', clear('starts_at'))] : []),
      ),
      until.label,
      actions(
        button('Set until', set('ends_at', until)),
        ...(relationship.ends_at ? [button('Clear until', clear('ends_at'))] : []),
      ),
    );
  }
  sections.push(when.root);

  // What it holds through: only the steps the reader may see, in order, with no gap where one is hidden.
  const chain = await readThrough(tenant, id).catch(() => null);
  if (chain && (chain.via.length > 0 || canEdit)) {
    const through = card();
    through.body.append(el('h2', 'It holds through', 'group-title'));
    const steps = chain.via.map((step) => step.id);
    if (chain.via.length) {
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'The chain it holds through');
      for (const step of chain.via) {
        const row = el('li');
        row.append(link(step.name, relationshipHref(tenant, step.id)));
        if (canEdit) {
          row.append(
            button(`Take out ${step.name}`, async () => {
              await writeThrough(
                tenant,
                id,
                chain.version,
                steps.filter((x) => x !== step.id),
              );
              await redraw();
            }),
          );
        }
        list.append(row);
      }
      through.body.append(list);
    } else {
      through.body.append(empty('It is not stated to hold through any other relationship.'));
    }
    if (canEdit) {
      const next = entryPicker(tenant, 'Add a step', {
        find: async (t, q) =>
          (await listRelationships(t, { page: 1, q })).items
            .filter((r) => r.id !== id)
            .map((r) => ({ id: r.id, name: r.name, kinds: [] })),
        nothing: 'No relationship by that name.',
      });
      through.body.append(
        next.label,
        actions(
          button('Add it to the chain', async () => {
            const picked = next.value();
            if (!picked) throw new Error('Choose a relationship first.');
            await writeThrough(tenant, id, chain.version, [...steps, picked]);
            await redraw();
          }),
        ),
      );
    }
    sections.push(through.root);
  }

  // The webs that name it: both of its ends are members (SO3).
  const webs = await websNaming(tenant, id).catch(() => null);
  if (webs) {
    const named = card();
    named.body.append(el('h2', 'The webs that name it', 'group-title'));
    if (webs.items.length) {
      const list = el('ul', '', 'list');
      list.setAttribute('aria-label', 'The webs that name it');
      for (const web of webs.items) {
        const row = el('li');
        row.append(
          icon('kind-social-web'),
          link(web.name, `/web/?${new URLSearchParams({ tenant, id: web.id })}`),
        );
        list.append(row);
      }
      named.body.append(list);
    } else {
      named.body.append(empty('No web you can see has both of its ends.'));
    }
    sections.push(named.root);
  }
  return sections;
}

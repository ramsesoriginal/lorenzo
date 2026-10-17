import { type LorenzoClient, unwrap } from '@lorenzo/api-client';
import {
  type Audience,
  audienceWithRecipients,
  renderAudienceControl,
} from '@lorenzo/information-editor';
import type { Bench } from '../core/bench';
import type { EntryFieldTarget, FieldSnapshot } from '../core/transport';

export type EntryControls = {
  audience(entryId: string, informationId?: string): HTMLElement;
  about(entryId: string, go: (id: string) => void): HTMLElement;
};
const encoded = (value: Audience) =>
  JSON.stringify(audienceWithRecipients(value, value.entity_ids ?? [], value.player_ids ?? []));

export function createEntryControls(
  bench: Bench,
  client: LorenzoClient,
  tenantId: string,
): EntryControls {
  async function change(
    entryId: string,
    target: EntryFieldTarget,
    base: FieldSnapshot,
    mine: string | boolean,
  ) {
    const command = bench.setField(entryId, target, base, mine);
    await bench.run();
    if (command && command.state !== 'synced')
      throw new Error(
        command.state === 'conflict'
          ? 'Someone changed this too. Review the conflict in the entry before continuing.'
          : (command.error ?? 'This change is waiting for a connection.'),
      );
  }
  return {
    audience(entryId, informationId) {
      const target: EntryFieldTarget = informationId
        ? { kind: 'information-audience', id: informationId }
        : { kind: 'entry-audience', id: entryId };
      const details = renderAudienceControl({
        client,
        tenantId,
        ...(informationId ? { informationId } : { entityId: entryId }),
        replace: async (next, previous, version) => {
          await change(entryId, target, { value: encoded(previous), version }, encoded(next));
          if (!bench.transport.readField) throw new Error('This audience is unavailable here.');
          const saved = await bench.transport.readField(target);
          return { audience: JSON.parse(String(saved.value)) as Audience, version: saved.version };
        },
      });
      details.classList.add('entry-audience');
      details.dataset.key = `audience:${informationId ?? entryId}`;
      return details;
    },
    about(entryId, go) {
      const details = document.createElement('details');
      details.dataset.key = `about:${entryId}`;
      const summary = document.createElement('summary');
      summary.textContent = 'About';
      const body = document.createElement('div');
      details.append(summary, body);
      let loaded = false;
      details.addEventListener('toggle', async () => {
        if (!details.open || loaded) return;
        loaded = true;
        body.textContent = 'Reading subjects…';
        try {
          const subjects = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities/{entity_id}/about', {
              params: { path: { tenant_id: tenantId, entity_id: entryId } },
            }),
          );
          body.replaceChildren();
          const list = document.createElement('ul');
          const status = document.createElement('p');
          status.className = 'muted';
          status.setAttribute('role', 'status');
          const write = async (subjectId: string, before: boolean, after: boolean) => {
            try {
              await change(
                entryId,
                { kind: 'fact-about', id: entryId, subjectId },
                { value: before, version: null },
                after,
              );
              loaded = false;
              details.open = false;
            } catch (error) {
              status.textContent =
                error instanceof Error ? error.message : 'The subject could not be changed.';
            }
          };
          for (const subject of subjects) {
            const row = document.createElement('li');
            const link = document.createElement('button');
            link.type = 'button';
            link.className = 'lnk';
            link.textContent = subject.name;
            link.addEventListener('click', () => go(subject.id));
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn quiet';
            remove.textContent = 'Remove';
            remove.setAttribute('aria-label', `Remove subject: ${subject.name}`);
            remove.addEventListener('click', () => void write(subject.id, true, false));
            row.append(link, remove);
            list.append(row);
          }
          const select = document.createElement('select');
          select.setAttribute('aria-label', 'What is this fact about?');
          const empty = document.createElement('option');
          empty.value = '';
          empty.textContent = 'Choose an entry…';
          select.append(empty);
          for (const entry of bench
            .listing()
            .filter((entry) => entry.id !== entryId && !subjects.some((s) => s.id === entry.id))
            .sort((a, b) => a.name.localeCompare(b.name))) {
            const option = document.createElement('option');
            option.value = entry.id;
            option.textContent = entry.name;
            select.append(option);
          }
          const add = document.createElement('button');
          add.type = 'button';
          add.className = 'btn quiet';
          add.textContent = 'Add subject';
          add.addEventListener('click', () => {
            if (select.value) void write(select.value, false, true);
          });
          if (!subjects.length) {
            const hint = document.createElement('p');
            hint.className = 'muted';
            hint.textContent = 'This fact stands on its own. Subjects are optional.';
            body.append(hint);
          }
          body.append(list, select, add, status);
        } catch (error) {
          loaded = false;
          body.textContent =
            error instanceof Error ? error.message : 'The subjects could not be read.';
        }
      });
      return details;
    },
  };
}

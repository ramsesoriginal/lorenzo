import type { Editor } from '@lorenzo/lorenzoscript-editor';
import { client, unwrap } from './api';
import { nameKey } from './mentioned-names';
import { reviewedLink } from './reviewed-link';

export function linkReview(tenant: string, text: HTMLTextAreaElement, editor: Editor) {
  const panel = document.createElement('details');
  panel.hidden = true;
  const summary = document.createElement('summary');
  summary.textContent = 'Link a name';
  const controls = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = 'Selected name';
  const find = document.createElement('button');
  find.type = 'button';
  find.className = 'btn btn-secondary';
  find.textContent = 'Find matching entries';
  const choices = document.createElement('div');
  choices.className = 'stack-tight';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  controls.append(legend, find, choices);
  panel.append(summary, controls, status);
  const path = { tenant_id: tenant };
  const details = async (id: string) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
        params: { path: { ...path, entity_id: id } },
      }),
    );
  async function run(action: () => Promise<void>) {
    if (controls.disabled) return;
    controls.disabled = true;
    try {
      await action();
    } catch (error) {
      choices.replaceChildren();
      status.textContent =
        error instanceof Error ? error.message : 'The entry could not be checked.';
    } finally {
      controls.disabled = false;
    }
  }
  async function lookup() {
    choices.replaceChildren();
    const source = text.value;
    const start = text.selectionStart;
    const end = text.selectionEnd;
    const selected = source.slice(start, end);
    const current = () => {
      if (
        !panel.isConnected ||
        !panel.open ||
        text.hidden ||
        text.value !== source ||
        text.selectionStart !== start ||
        text.selectionEnd !== end
      )
        throw new Error('The selection changed. Select the name and search again.');
    };
    current();
    if (!reviewedLink(source, start, end, 'review-name'))
      throw new Error('Select one complete name in plain manuscript text.');
    status.textContent = 'Finding matching entries…';
    const selectedKey = nameKey(selected);
    const matches = new Map<string, string>();
    for (let page = 1; ; page++) {
      const found = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities', {
          params: { path, query: { q: selected, page, size: 100 } },
        }),
      );
      current();
      for (const entry of found.items)
        if (nameKey(entry.name) === selectedKey) matches.set(entry.id, entry.name);
      if (page >= found.pages) break;
    }
    let count = 0;
    for (const [id, name] of matches) {
      const entry = await details(id);
      current();
      if (!entry.slug || entry.name !== name) continue;
      const slug = entry.slug;
      const choose = document.createElement('button');
      choose.type = 'button';
      choose.className = 'btn btn-secondary';
      choose.textContent = `${name} (${slug})`;
      choose.addEventListener(
        'click',
        () =>
          void run(async () => {
            current();
            status.textContent = 'Checking the entry…';
            const updated = await details(id);
            current();
            if (updated.name !== name || updated.slug !== slug)
              throw new Error('The entry changed. Find matching entries again.');
            const markup = reviewedLink(source, start, end, slug);
            if (!markup) throw new Error('This selection cannot hold that link.');
            editor.replaceSelection(markup);
            choices.replaceChildren();
            status.textContent = 'Link added.';
            panel.open = false;
          }),
      );
      choices.append(choose);
      count++;
    }
    status.textContent = count
      ? 'Choose the entry to link.'
      : 'No matching entry with a link name was found.';
  }
  find.addEventListener('click', () => void run(lookup));
  panel.addEventListener('toggle', () => {
    if (!panel.open) panel.hidden = true;
  });
  return {
    element: panel,
    open() {
      panel.hidden = false;
      panel.open = true;
      summary.focus();
      void run(lookup);
    },
  };
}

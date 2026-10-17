import { renderInformationPayloads } from '@lorenzo/information-editor';
import { blobUrl, client, LorenzoApiError, unwrap } from '../../lib/api';
import { type Renderer, showDescriptions } from '../../lib/descriptions';

export async function renderFactPage(
  root: HTMLElement,
  tenantId: string,
  id: string,
  renderer: Renderer,
): Promise<void> {
  const fact = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: id } },
    }),
  );
  if (!fact.kinds.includes('fact')) throw new LorenzoApiError('This fact is not available.', 404);
  const subjects = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}/about', {
      params: { path: { tenant_id: tenantId, entity_id: id } },
    }),
  );
  const heading = document.createElement('h1');
  heading.textContent = fact.name;
  root.replaceChildren(heading);
  if (subjects.length) {
    const about = document.createElement('p');
    about.className = 'caption';
    about.textContent = `About ${subjects.map((subject) => subject.name).join(', ')}`;
    root.append(about);
  }
  for (const info of fact.information) {
    const section = document.createElement('section');
    section.className = 'stack-tight';
    const title = document.createElement('h2');
    title.textContent = info.title || 'Information';
    const content = document.createElement('div');
    content.className = 'ls-content';
    section.append(title, content);
    root.append(section);
    renderInformationPayloads(content, {
      information: info,
      loadFile: (payload) => blobUrl(payload.url),
      renderText: (host, text) => showDescriptions(host, renderer, [{ text, home: id }]),
    });
    if (info.created_by_name) {
      const author = document.createElement('p');
      author.className = 'caption';
      author.textContent = info.created_by_name;
      section.append(author);
    }
  }
  if (!fact.information.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No information has been shared with you.';
    root.append(empty);
  }
  root.hidden = false;
}

import { parse, render } from '@lorenzo/lorenzoscript';
import { createEditor, type Editor } from '@lorenzo/lorenzoscript-editor';
import { client, loadFile, unwrap } from './api';
import { contentsNavigation } from './contents';
import { numberedTitle } from './numbering';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};
const action = (label: string, run: () => Promise<void>) => {
  const b = node('button', label);
  b.type = 'button';
  b.className = 'btn btn-secondary';
  b.addEventListener('click', () => {
    b.disabled = true;
    void run().finally(() => {
      b.disabled = false;
    });
  });
  return b;
};
export const reviewAddress = (tenant: string, edition: string) =>
  `/?${new URLSearchParams({ tenant, review: edition })}`;

export async function reviewScreen(
  host: HTMLElement,
  tenant: string,
  edition: string,
  account: string,
) {
  const path = { tenant_id: tenant, edition_id: edition };
  const read = async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/writing/reviews/{edition_id}', { params: { path } }),
    );
  let editor: Editor | undefined;
  let reviewerDetails: HTMLDetailsElement | undefined;
  let reviewersOpen = false;
  let input: HTMLTextAreaElement | undefined;
  let select: HTMLSelectElement | undefined;
  let draft = {
    id: crypto.randomUUID() as string,
    entry: edition,
    content: '',
    version: undefined as number | undefined,
  };
  let fingerprint = '';
  let generation = 0;
  let stopped = false;
  let loading = false;
  const urls = new Set<string>();
  const remember = () => {
    if (reviewerDetails) reviewersOpen = reviewerDetails.open;
    if (input) draft.content = input.value;
    if (select) draft.entry = select.value;
  };
  const clear = () => {
    generation++;
    editor?.destroy();
    editor = undefined;
    input = undefined;
    select = undefined;
    for (const url of urls) URL.revokeObjectURL(url);
    urls.clear();
    host.replaceChildren();
    fingerprint = '';
  };
  const fail = (error: unknown) => {
    clear();
    draft = { id: crypto.randomUUID(), entry: edition, content: '', version: undefined };
    const message = node(
      'p',
      error instanceof Error ? error.message : 'This review is no longer available.',
    );
    message.setAttribute('role', 'alert');
    host.append(message);
  };
  const refresh = async () => {
    if (stopped || document.hidden || loading) return;
    loading = true;
    const started = generation;
    try {
      const data = await read();
      if (stopped || document.hidden || started !== generation) return;
      const next = JSON.stringify(data);
      if (next === fingerprint) return;
      remember();
      clear();
      const drawing = generation;
      fingerprint = next;
      const byId = new Map(data.entries.map((e) => [e.id, e]));
      if (!byId.has(draft.entry))
        draft = { id: crypto.randomUUID(), entry: edition, content: '', version: undefined };
      host.append(node('h1', data.book_name), node('p', 'Review — manuscript and private notes'));
      const article = node('article');
      article.className = 'ls-content';
      host.append(article);
      const pending: (
        | { kind: 'entry'; id: string }
        | { kind: 'text' | 'picture'; content?: string | null; url?: string | null }
      )[] = [{ kind: 'entry', id: edition }];
      while (pending.length) {
        const part = pending.pop();
        if (!part) continue;
        if (part.kind === 'entry') {
          const entry = byId.get(part.id);
          if (!entry) continue;
          if (entry.id !== edition) {
            const title = node('h2', numberedTitle(entry.name, entry.number));
            title.id = `review-entry-${entry.id}`;
            article.append(title);
          }
          if (entry.contents)
            article.append(
              contentsNavigation(
                entry.contents,
                (id) => `#review-entry-${id}`,
                entry.id === edition,
              ),
            );
          for (const el of [...entry.elements].reverse()) pending.push(el);
        } else if (part.kind === 'text') {
          const section = node('section');
          section.innerHTML = render(parse(part.content ?? ''), { externalImages: false });
          article.append(section);
        } else if (part.url) {
          const image = node('img');
          image.alt = 'Manuscript illustration';
          article.append(image);
          const url = await loadFile({ url: part.url });
          if (drawing !== generation || stopped || document.hidden) {
            URL.revokeObjectURL(url);
            return;
          }
          urls.add(url);
          image.src = url;
        }
      }
      const status = node('p');
      status.setAttribute('role', 'status');
      status.setAttribute('aria-label', 'Review status');
      host.append(
        node('h2', 'Review notes'),
        node(
          'p',
          'Your notes are visible to you and the authors. Save a note before leaving this page.',
        ),
        status,
      );
      for (const note of data.notes) {
        const section = node('section');
        section.className = 'stack-tight';
        section.append(node('h3', byId.get(note.entry_id)?.name ?? 'Detached writing'));
        section.append(node('p', note.author_name ?? 'Reviewer'));
        const text = node('div');
        text.className = 'ls-content';
        text.innerHTML = render(parse(note.content), { externalImages: false });
        section.append(text);
        if (note.author_id === account && byId.has(note.entry_id))
          section.append(
            action('Edit your note', async () => {
              draft = {
                id: note.id,
                entry: note.entry_id,
                content: note.content,
                version: note.version,
              };
              if (input && select) {
                input.value = draft.content;
                select.value = draft.entry;
                await editor?.refresh();
                input.focus();
              }
            }),
          );
        host.append(section);
      }
      select = node('select');
      select.setAttribute('aria-label', 'Note on');
      for (const entry of data.entries) {
        const option = node('option', entry.name);
        option.value = entry.id;
        select.append(option);
      }
      select.value = draft.entry;
      host.append(select);
      input = node('textarea');
      input.setAttribute('aria-label', 'Review note');
      input.value = draft.content;
      host.append(input);
      editor = createEditor({
        textarea: input,
        layout: 'tabs',
        toolbar: ['bold', 'italic', 'bullets', 'undo', 'redo'],
        render: (source) => render(parse(source), { externalImages: false }),
      });
      host.append(
        action('Save note', async () => {
          remember();
          status.textContent = 'Saving';
          try {
            if (!draft.content.trim()) {
              status.textContent = 'Write a note first.';
              return;
            }
            await unwrap(
              await client.PUT(
                '/tenants/{tenant_id}/writing/reviews/{edition_id}/notes/{note_id}',
                {
                  params: {
                    path: { ...path, note_id: draft.id },
                    header:
                      draft.version === undefined ? {} : { 'if-match': String(draft.version) },
                  },
                  body: { entry_id: draft.entry, content: draft.content },
                },
              ),
            );
            draft = { id: crypto.randomUUID(), entry: edition, content: '', version: undefined };
            if (input) input.value = '';
            if (select) select.value = edition;
            fingerprint = '';
            await refresh();
          } catch (error) {
            // Revalidate after a failed write so revocation cannot leave private content visible.
            try {
              await read();
              status.textContent =
                error instanceof Error ? error.message : 'The note could not be saved.';
            } catch (accessError) {
              fail(accessError);
            }
          }
        }),
      );
      if (data.can_manage) {
        const details = node('details');
        details.open = reviewersOpen;
        reviewerDetails = details;
        details.append(node('summary', 'Reviewers'));
        const body = node('div');
        body.className = 'stack-tight';
        details.append(body);
        host.append(details);
        const people = await unwrap(
          await client.GET('/tenants/{tenant_id}/writing/reviews/{edition_id}/reviewers', {
            params: { path },
          }),
        );
        if (drawing !== generation || stopped || document.hidden) return;
        body.append(node('p', 'This Edition only. Other Editions stay private.'));
        const address = node('a', 'Review address');
        address.href = reviewAddress(tenant, edition);
        body.append(address);
        for (const person of people) {
          const row = node('p', `${person.name} `);
          row.append(
            action('Revoke review access', async () => {
              try {
                await unwrap(
                  await client.DELETE(
                    '/tenants/{tenant_id}/writing/reviews/{edition_id}/reviewers/{reviewer_id}',
                    { params: { path: { ...path, reviewer_id: person.user_id } } },
                  ),
                );
                fingerprint = '';
                await refresh();
              } catch (error) {
                status.textContent = String(error);
              }
            }),
          );
          body.append(row);
        }
        const email = node('input');
        email.type = 'email';
        email.className = 'text-input';
        email.setAttribute('aria-label', 'Reviewer email');
        body.append(email);
        body.append(
          action('Add reviewer', async () => {
            try {
              const person = await unwrap(
                await client.GET('/users/by-email/{email}', {
                  params: { path: { email: email.value.trim() } },
                }),
              );
              await unwrap(
                await client.PUT(
                  '/tenants/{tenant_id}/writing/reviews/{edition_id}/reviewers/{reviewer_id}',
                  { params: { path: { ...path, reviewer_id: person.id } } },
                ),
              );
              fingerprint = '';
              await refresh();
            } catch (error) {
              status.textContent =
                error instanceof Error ? error.message : 'The reviewer could not be added.';
            }
          }),
        );
      }
    } catch (error) {
      if (started === generation || fingerprint) fail(error);
    } finally {
      loading = false;
    }
  };
  const visibility = () => {
    if (document.hidden) {
      remember();
      clear();
    } else void refresh();
  };
  const stop = () => {
    stopped = true;
    clear();
    draft.content = '';
    clearInterval(timer);
    document.removeEventListener('visibilitychange', visibility);
  };
  const timer = setInterval(() => void refresh(), 30000);
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('lorenzo:sign-out', stop, { once: true });
  window.addEventListener('pagehide', stop, { once: true });
  await refresh();
}

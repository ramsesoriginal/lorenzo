import { getAppLinks } from '@lorenzo/api-client';
import { bindShell } from '@lorenzo/app-shell';
import {
  type BundleReceipt,
  type DraftPayload,
  type Information,
  renderAudienceControl,
  renderBundleEditor,
  sameBundle,
  saveInformationBundle,
} from '@lorenzo/information-editor';
import { parse, render } from '@lorenzo/lorenzoscript';
import { createEditor } from '@lorenzo/lorenzoscript-editor';
import { client, fetchAllPages, LorenzoApiError, loadFile, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { compositionScreen, outlineOf, writingAddress } from './composition';
import { API_BASE_URL } from './config';
import {
  draftKey,
  forgetDrafts,
  readDraft,
  readDrafts,
  removeDraft,
  selectDraft,
  writeDraft,
} from './drafts';
import { reviewAddress, reviewScreen } from './review';
import { writingDetails } from './writing-details';

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'This could not be completed.';

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text = '', className = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

function button(label: string, action: () => void) {
  const node = element('button', label, 'btn btn-secondary');
  node.type = 'button';

  node.addEventListener('click', action);
  return node;
}

const address = (tenant: string, entry?: string) =>
  `/?${new URLSearchParams({ tenant, ...(entry ? { entry } : {}) })}`;

const fingerprint = (payloads: DraftPayload[]) =>
  JSON.stringify(
    payloads.map((p) => {
      const { updated_at: _version, ...value } = p;
      return value;
    }),
  );

export async function start() {
  const host = document.querySelector<HTMLElement>('#writing');
  if (!host) return;

  const shell = bindShell({
    themeKey: 'lorenzo:writing:theme',

    onLogin: () => {
      sessionStorage.setItem('lorenzo:writing:return', location.pathname + location.search);
      void login();
    },

    onLogout: () => {
      void logout();
    },
  });

  void getAppLinks(API_BASE_URL)
    .then((registry) => shell?.accountLink(registry.apps.account_hub.url))
    .catch(() => {});
  try {
    if (!isAuthConfigured() || !(await isAuthenticated())) {
      shell?.account({ state: 'signed-out' });
      shell?.status('Log in to begin writing.');
      return;
    }

    const me = await unwrap(await client.GET('/me'));

    const reviewParams = new URLSearchParams(location.search);
    const reviewTenant = reviewParams.get('tenant');
    const reviewEdition = reviewParams.get('review');
    if (reviewTenant && reviewEdition) {
      shell?.account({ state: 'signed-in', label: me.email ?? undefined });
      shell?.reveal();
      await reviewScreen(host, reviewTenant, reviewEdition, me.id);
      return;
    }

    const libraries = (
      await fetchAllPages(async (page) =>
        unwrap(
          await client.GET('/tenants', {
            params: { query: { page, size: 100 } },
          }),
        ),
      )
    ).filter((t) => ['owner', 'orga', 'author'].includes(t.role));

    shell?.account({ state: 'signed-in', label: me.email ?? undefined });
    shell?.reveal();

    const params = new URLSearchParams(location.search);

    const tenant = params.get('tenant') ?? libraries[0]?.id;

    shell?.libraries(libraries, tenant ?? '', (id) => location.assign(address(id)));

    if (!tenant) {
      host.textContent = 'Choose an author role in a library or repository to begin writing.';
      return;
    }

    const entry = params.get('entry');

    if (entry) {
      try {
        const view = params.get('view');
        if (view === 'outline' || view === 'read')
          await compositionScreen(host, tenant, entry, view === 'read');
        else await manuscript(host, me.id, tenant, entry);
      } catch (error) {
        if (error instanceof LorenzoApiError && [401, 403, 404].includes(error.status))
          await forgetDrafts(draftKey(API_BASE_URL, me.id, tenant, entry)).catch(() => {});
        throw error;
      }
      return;
    }

    const heading = element('h1', 'Your writing');

    const name = element('input', '', 'text-input');
    name.placeholder = 'Untitled';
    name.maxLength = 300;

    name.setAttribute('aria-label', 'New draft title');

    const status = element('p', '', 'caption');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-label', 'Save status');

    const kind = element('select');
    kind.setAttribute('aria-label', 'Start with');
    for (const [value, label] of [
      ['scene', 'Scene draft'],
      ['book', 'Book'],
      ['chapter', 'Chapter draft'],
      ['biography', 'Character biography'],
    ]) {
      const option = element('option', label);
      option.value = value;
      kind.append(option);
    }
    const creationId = crypto.randomUUID();
    const firstEditionId = crypto.randomUUID();
    const create = button('Start writing', () => {
      create.disabled = true;

      void (async () => {
        try {
          if (kind.value !== 'scene') {
            const route =
              kind.value === 'book'
                ? '/tenants/{tenant_id}/writing/books'
                : kind.value === 'biography'
                  ? '/tenants/{tenant_id}/writing/biographies'
                  : '/tenants/{tenant_id}/writing/chapters';
            const made = await unwrap(
              await client.POST(route, {
                params: { path: { tenant_id: tenant } },
                body: {
                  id: creationId,
                  first_edition_id: firstEditionId,
                  name: name.value.trim() || 'Untitled',
                },
              }),
            );
            location.assign(address(tenant, made.kind === 'book' ? made.editions[0]?.id : made.id));
            return;
          }
          const scene = await unwrap(
            await client.POST('/tenants/{tenant_id}/scenes', {
              params: { path: { tenant_id: tenant } },
              body: {
                id: creationId,
                name: name.value.trim() || 'Untitled',
                is_public: false,
              },
            }),
          );

          location.assign(address(tenant, scene.id));
        } catch (error) {
          status.textContent = message(error);
          create.disabled = false;
        }
      })();
    });

    const row = element('div', '', 'row');
    row.append(kind, name, create);

    host.replaceChildren(heading, row, status);

    const scenes = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities', {
          params: {
            path: { tenant_id: tenant },
            query: { page, size: 100, kind: ['scene', 'book', 'chapter', 'scene_telling'] },
          },
        }),
      ),
    );

    const list = element('ul', '', 'list');

    const biographies = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/writing/biographies', {
          params: { path: { tenant_id: tenant }, query: { page, size: 100 } },
        }),
      ),
    );
    for (const scene of [...scenes, ...biographies]) {
      const item = element('li');
      const link = element('a', scene.name);
      link.href = address(tenant, scene.id);
      item.append(link);
      list.append(item);
    }

    host.append(list);
  } catch (error) {
    host.textContent = message(error);
    shell?.status(message(error), 'error');
  }
}

async function manuscript(host: HTMLElement, account: string, tenant: string, entry: string) {
  const path = { tenant_id: tenant, entity_id: entry };

  const entityResult = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
  });
  const entity = await unwrap(entityResult);
  const writingEntry = await outlineOf(tenant, entry);
  const structured = ['book', 'edition', 'chapter'].includes(writingEntry.kind);
  if (writingEntry.uses_scene_manuscript) {
    await compositionScreen(host, tenant, entry, true);
    const explanation = element('p', "This telling uses the Scene's shared manuscript.");
    const action = button('Make independent', () => {
      action.disabled = true;
      void (async () => {
        try {
          await unwrap(
            await client.POST('/tenants/{tenant_id}/writing/tellings/{id}/independent', {
              params: {
                path: { tenant_id: tenant, id: entry },
                header: { 'if-match': writingEntry.version },
              },
            }),
          );
          location.reload();
        } catch (error) {
          explanation.textContent = message(error);
          action.disabled = false;
        }
      })();
    });
    host.append(explanation, action);
    if (writingEntry.scene_id) {
      const source = element('a', 'Edit shared Scene');
      source.href = address(tenant, writingEntry.scene_id);
      host.append(source);
    }
    const details = element('details');
    details.append(element('summary', 'Details'));
    const content = element('div', '', 'stack-tight');
    details.append(content);
    details.addEventListener('toggle', () => {
      if (details.open && !content.children.length)
        void writingDetails(content, tenant, entry, (version) => {
          writingEntry.version = version;
        }).catch((error) => {
          content.textContent = message(error);
        });
    });
    host.append(details);
    return;
  }
  if (entity.kinds.includes('book')) {
    const book = await outlineOf(tenant, entry);
    const first = book.editions[0];
    if (!first) throw new Error('This Book has no Edition to open.');
    location.replace(address(tenant, first.id));
    return;
  }
  if (writingEntry.kind === 'scene') {
    const scene = await unwrap(
      await client.GET('/tenants/{tenant_id}/scenes/{scene_id}', {
        params: { path: { tenant_id: tenant, scene_id: entry } },
      }),
    );
    if (!scene.can_manage)
      throw new LorenzoApiError('This manuscript is not available for editing.', 403);
  }
  const scene = entity;

  let info = entity.information.find((i) => i.type === 'manuscript');

  if (!info)
    info = await unwrap(
      await client.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
        params: { path },
        body: {
          id: crypto.randomUUID(),
          title: 'Manuscript',
          type: 'manuscript',
          is_public: false,
          content: '',
          locale: 'en-US',
        },
      }),
    );

  const informationId = info.id;

  const infoPath = { tenant_id: tenant, information_id: informationId };

  const key = draftKey(API_BASE_URL, account, tenant, entry);

  const read = async () =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/information/{information_id}/editor', {
        params: { path: infoPath },
      }),
    );

  // Authorization precedes every local draft read, including reload and account changes.

  try {
    info = await read();
  } catch (error) {
    if (error instanceof LorenzoApiError && [401, 403, 404].includes(error.status))
      await forgetDrafts(key);

    throw error;
  }

  let original: Information = info;

  let receipt: BundleReceipt = { id: info.id, information: info };

  let initial: DraftPayload[] = info.payloads;

  let localWarning = '';

  let recovered = false;

  let blocked = false;

  try {
    const draft = await readDraft(key);

    if (draft) {
      initial = draft.payloads;
      original = draft.original;
      receipt = draft.receipt;
      recovered = true;

      blocked = !sameBundle(receipt.information ?? original, info);
    }
  } catch {
    localWarning =
      'Browser recovery is unavailable. Keep this tab open until your changes are saved.';
  }

  const back = element('a', 'Your writing');
  back.href = address(tenant);

  const heading = element('h1', scene.name);

  const status = element(
    'p',
    recovered ? 'Recovered your unsent draft from this browser.' : 'Saved',
    'caption',
  );

  status.setAttribute('role', 'status');
  status.setAttribute('aria-label', 'Save status');

  const warning = element('p', localWarning, 'caption');
  warning.setAttribute('role', 'alert');

  const conflicts = element('div', '', 'stack-tight');

  const area = element('div', '', 'stack');

  const details = element('details');
  details.append(element('summary', 'Details'));
  const worldDetails = element('div', '', 'stack-tight');
  details.append(worldDetails);
  if (writingEntry.kind === 'edition') {
    const review = element('a', 'Review and reviewers');
    review.href = reviewAddress(tenant, entry);
    details.append(review);
  }
  details.addEventListener('toggle', () => {
    if (details.open && !worldDetails.children.length)
      void writingDetails(worldDetails, tenant, entry).catch((error) => {
        worldDetails.textContent = message(error);
      });
  });

  const title = element('input', '', 'text-input');
  title.value = scene.name;
  title.maxLength = 300;
  title.setAttribute('aria-label', 'Draft title');

  let sceneVersion = entityResult.response.headers.get('etag') ?? '';

  const rename = button('Save title', () => {
    void (async () => {
      try {
        const result = await client.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
          params: {
            path: { tenant_id: tenant, entity_id: entry },
            header: { 'if-match': sceneVersion },
          },
          body: { name: title.value.trim() || 'Untitled' },
        });

        const saved = await unwrap(result);
        sceneVersion = result.response.headers.get('etag') ?? '';
        heading.textContent = saved.name;
      } catch (error) {
        warning.textContent = message(error);
      }
    })();
  });

  details.append(
    title,
    rename,
    element(
      'p',
      'Unsent drafts stay in this browser for this account. Sign out on shared devices. Saved revisions contain text and pictures, not earlier sharing settings.',
      'caption',
    ),

    renderAudienceControl({ client, tenantId: tenant, informationId }),
  );

  const history = element('details');
  history.append(element('summary', 'Saved revisions'));

  const historyBody = element('div', '', 'stack-tight');
  history.append(historyBody);

  const focus = button('Focus', () => {
    const active = focus.getAttribute('aria-pressed') !== 'true';
    focus.setAttribute('aria-pressed', String(active));

    for (const node of document.querySelectorAll<HTMLElement>('[data-site-header], footer'))
      node.hidden = active;

    back.hidden = active;
    details.hidden = active;
    history.hidden = active;
    focus.textContent = active ? 'Leave focus' : 'Focus';
  });
  focus.setAttribute('aria-pressed', 'false');

  const actions = element('div', '', 'row');

  const saveButton = button('Save now', () => {
    void save();
  });
  actions.append(focus, saveButton);
  if (structured)
    for (const [label, view] of [
      ['Outline', 'outline'],
      ['Read', 'read'],
    ]) {
      const link = element('a', label);
      link.href = writingAddress(tenant, entry, view);
      link.addEventListener('click', (event) => {
        event.preventDefault();
        void (async () => {
          if (saving) {
            warning.textContent = 'Wait for this save before changing views.';
            return;
          }
          if (dirty) await save();
          if (!dirty) location.assign(link.href);
        })();
      });
      actions.append(link);
    }

  host.replaceChildren(back, heading, actions, status, warning, conflicts, area, details, history);

  let editor: ReturnType<typeof renderBundleEditor>;

  let timer: ReturnType<typeof setTimeout> | undefined;

  let dirty = recovered,
    saving = false,
    alive = true,
    persisted = !localWarning;

  let serial = Promise.resolve();

  let observed = fingerprint(initial);

  const persist = () => {
    persisted = false;

    const draft = structuredClone({ original, receipt, payloads: editor.read() });

    const captured = fingerprint(draft.payloads);
    serial = serial
      .then(async () => {
        await writeDraft(key, draft);
        persisted = captured === fingerprint(editor.read());
      })
      .catch(() => {
        persisted = false;
        warning.textContent =
          'Browser recovery is unavailable. Keep this tab open until your changes are saved.';
      });
    return serial;
  };

  function mount(payloads: DraftPayload[]) {
    editor?.destroy();

    editor = renderBundleEditor({
      initial: payloads,
      content: '',
      textLabel: 'Manuscript',
      loadFile,

      createTextEditor(container, label, content) {
        const text = element('textarea');
        text.value = content;
        text.id = crypto.randomUUID();
        text.rows = 20;

        const caption = element('label', label, 'field-label');
        caption.htmlFor = text.id;
        container.append(caption, text);

        const control = createEditor({
          textarea: text,
          layout: 'tabs',
          toolbar: ['bold', 'italic', 'heading', 'bullets', '|', 'link', 'entity', 'undo'],

          render: (source) => render(parse(source), { externalImages: false }),
        });

        return {
          value: () => text.value,
          focus: () => text.focus(),
          destroy: () => control.destroy(),
        };
      },
    });

    area.replaceChildren(editor.element);
    observed = fingerprint(editor.read());
  }

  function changed() {
    if (!alive) return;

    const next = fingerprint(editor.read());
    if (next === observed) return;
    observed = next;
    dirty = true;

    void persist();
    status.textContent = blocked
      ? 'Review the saved version before continuing.'
      : 'Unsaved changes';

    clearTimeout(timer);
    timer = setTimeout(() => void save(), 900);
  }

  const otherDrafts = await readDrafts(key).catch(() => []);
  mount(initial);
  if (otherDrafts.length > 1) {
    const alternatives = element('details');
    alternatives.append(element('summary', 'Other unsent drafts'));
    for (const saved of otherDrafts)
      alternatives.append(
        button(new Date(saved.savedAt).toLocaleString(), () => {
          if (saving) return;
          selectDraft(key, saved);
          mount(saved.draft.payloads);
          original = saved.draft.original;
          receipt = saved.draft.receipt;
          dirty = true;
          void persist();
          conflict();
        }),
      );
    details.append(alternatives);
  }

  for (const event of ['input', 'change', 'click'])
    area.addEventListener(event, () => queueMicrotask(changed));

  function conflict() {
    blocked = true;
    status.textContent = 'This manuscript changed elsewhere. Your draft is kept in this browser.';

    conflicts.replaceChildren(
      element('p', 'Compare the saved manuscript before choosing how to continue.'),
    );

    const currentText = element('pre');
    conflicts.append(currentText);

    void read()
      .then((current) => {
        if (alive)
          currentText.textContent = current.payloads
            .filter((p) => p.kind === 'description')
            .map((p) => p.content)
            .join('\n\n');
      })
      .catch((error) => {
        if (alive) warning.textContent = message(error);
      });

    for (const [label, keep] of [
      ['Continue with my draft', true],
      ['Use saved manuscript', false],
    ] as const) {
      conflicts.append(
        button(label, () => {
          void (async () => {
            try {
              const current = await read();
              if (!alive) return;

              original = current;
              receipt = { id: current.id, information: current };

              if (!keep) {
                mount(current.payloads);
                dirty = false;
                await serial;
                await removeDraft(key);
              } else {
                dirty = true;
                await persist();
              }

              blocked = false;
              conflicts.replaceChildren();
              status.textContent = keep ? 'Your draft is ready to save.' : 'Saved';

              if (keep) await save();
            } catch (error) {
              warning.textContent = message(error);
            }
          })();
        }),
      );
    }
  }

  async function save() {
    if (!alive || saving || blocked || !dirty) return;

    saving = true;
    saveButton.disabled = true;
    const sent = fingerprint(editor.read());

    const draft = {
      title: original.title,
      type: 'manuscript',
      isPublic: original.is_public,
      payloads: editor.read(),
      receipt,
    };

    try {
      await editor.ready();
      await persist();
      status.textContent = 'Saving…';

      const saved = await saveInformationBundle({ client, tenantId: tenant, original, draft });

      if (!alive) return;

      original = saved;
      receipt = { id: saved.id, information: saved };

      await serial;
      if (fingerprint(editor.read()) === sent) {
        dirty = false;
        serial = serial
          .then(() => removeDraft(key))
          .catch(() => {
            warning.textContent = 'Saved on the server. Browser recovery could not be cleared.';
          });
        await serial;
        status.textContent = 'Saved';
      } else {
        await persist();
        status.textContent = 'Saving your latest changes…';
      }
    } catch (error) {
      if (!alive) return;

      if (error instanceof LorenzoApiError && [401, 403, 404].includes(error.status)) {
        alive = false;
        editor.destroy();
        await serial;
        await forgetDrafts(key);
        host.textContent = 'This manuscript is no longer available.';
      } else if (error instanceof LorenzoApiError && error.status === 412) conflict();
      else status.textContent = `${message(error)} Your draft is kept here. Use Save now to retry.`;
    } finally {
      saving = false;
      saveButton.disabled = false;
    }

    if (alive && dirty && !blocked && status.textContent === 'Saving your latest changes…')
      timer = setTimeout(() => void save(), 100);
  }

  if (blocked) conflict();
  else if (recovered) timer = setTimeout(() => void save(), 900);

  history.addEventListener('toggle', () => {
    if (!history.open) return;
    void (async () => {
      try {
        const list = await fetchAllPages(async (page) =>
          unwrap(
            await client.GET('/tenants/{tenant_id}/information/{information_id}/revisions', {
              params: { path: infoPath, query: { page, size: 25 } },
            }),
          ),
        );

        historyBody.replaceChildren();

        if (!list.length)
          historyBody.textContent = 'Saved revisions appear after you change this manuscript.';

        for (const revision of list)
          historyBody.append(
            button(new Date(revision.created_at).toLocaleString(), () => {
              void (async () => {
                try {
                  const saved = await unwrap(
                    await client.GET(
                      '/tenants/{tenant_id}/information/{information_id}/revisions/{revision_id}',
                      { params: { path: { ...infoPath, revision_id: revision.id } } },
                    ),
                  );

                  const snapshot = saved.snapshot as {
                    payloads: {
                      id: string;
                      order: number;
                      description?: { content: string; locale: string };
                      picture?: { data: string; file_type: string };
                    }[];
                  };

                  const payloads: DraftPayload[] = snapshot.payloads.flatMap<DraftPayload>((p) =>
                    p.description
                      ? [
                          {
                            id: p.id,
                            order: p.order,
                            kind: 'description' as const,
                            updated_at: '',
                            content: p.description.content,
                            locale: p.description.locale,
                          },
                        ]
                      : p.picture
                        ? [
                            {
                              id: crypto.randomUUID(),
                              order: p.order,
                              kind: 'picture' as const,
                              updated_at: '',
                              url: '',
                              file_type: p.picture.file_type,

                              file: new File(
                                [Uint8Array.from(atob(p.picture.data), (c) => c.charCodeAt(0))],
                                'recovered-picture',
                                { type: p.picture.file_type },
                              ),
                            },
                          ]
                        : [],
                  );

                  const preview = element(
                    'pre',
                    payloads
                      .filter((p) => p.kind === 'description')
                      .map((p) => p.content)
                      .join('\n\n'),
                  );

                  const restore = button('Load this revision as a draft', () => {
                    if (saving) return;
                    mount(payloads);
                    dirty = true;
                    void persist();
                    status.textContent = 'Revision loaded. Use Save now to keep it.';
                    history.open = false;
                  });
                  historyBody.replaceChildren(preview, restore);
                } catch (error) {
                  historyBody.textContent = message(error);
                }
              })();
            }),
          );
      } catch (error) {
        historyBody.textContent = message(error);
      }
    })();
  });

  window.addEventListener('beforeunload', (event) => {
    if (dirty && !persisted) {
      event.preventDefault();
    }
  });

  const stop = () => {
    alive = false;
    clearTimeout(timer);
    editor.destroy();
  };

  window.addEventListener('pagehide', stop, { once: true });
  window.addEventListener('lorenzo:sign-out', stop, { once: true });
}

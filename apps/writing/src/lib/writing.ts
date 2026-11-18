import { getAppLinks } from '@lorenzo/api-client';
import { bindShell, confirmDialog, openMenu } from '@lorenzo/app-shell';
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
import { modernAddress } from './addresses';
import { client, fetchAllPages, LorenzoApiError, loadFile, unwrap } from './api';
import { isAuthConfigured, isAuthenticated, login, logout } from './auth';
import { askTitle, extractParts, splitAtCaret } from './blocks';
import { compositionScreen, outlineOf, writingAddress } from './composition';
import { API_BASE_URL, BRANDING_CSS_URL } from './config';
import {
  draftKey,
  forgetDrafts,
  readDraft,
  readDrafts,
  removeDraft,
  selectDraft,
  writeDraft,
} from './drafts';
import { linkReview } from './link-review';
import { countSources } from './manuscript-count';
import { exportControls } from './manuscript-export';
import { reviewAddress, reviewScreen } from './review';
import { shelf } from './shelf';
import { rememberWork } from './shelf-list';
import { draftCount } from './word-count';
import { writingDetails } from './writing-details';
import { writingSession } from './writing-session';
import { writingTimer } from './writing-timer';

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
  `${entry ? '/write/' : '/'}?${new URLSearchParams({ tenant, ...(entry ? { entry } : {}) })}`;

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
  const modern = modernAddress(location);
  if (modern) {
    location.replace(modern);
    return;
  }

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

  // The palette, the keys and the apps sheet are the shell's (ADR 0494).
  shell?.palette();
  void getAppLinks(API_BASE_URL)
    .then((registry) => {
      shell?.accountLink(registry.apps.account_hub.url);
      shell?.apps(registry);
    })
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
      shell?.statusBar({ sync: 'synced', syncedAt: new Date() });
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
    shell?.statusBar({ sync: 'synced', syncedAt: new Date() });

    const params = new URLSearchParams(location.search);

    const tenant = params.get('tenant') ?? libraries[0]?.id;

    shell?.libraries(libraries, tenant ?? '', (id) => location.assign(address(id)));
    shell?.library(tenant ?? null);

    if (!tenant) {
      host.textContent = 'Choose an author role in a library or repository to begin writing.';
      return;
    }

    const entry = params.get('entry');

    if (entry) {
      rememberWork(tenant, entry);
      try {
        const view = params.get('view') ?? (location.pathname.startsWith('/read') ? 'read' : null);
        if (view === 'outline' || view === 'read')
          await compositionScreen(host, tenant, entry, view === 'read');
        else await manuscript(host, me.id, tenant, entry, shell);
      } catch (error) {
        if (error instanceof LorenzoApiError && [401, 403, 404].includes(error.status))
          await forgetDrafts(draftKey(API_BASE_URL, me.id, tenant, entry)).catch(() => {});
        throw error;
      }
      return;
    }

    await shelf(host, tenant);
  } catch (error) {
    host.textContent = message(error);
    shell?.status(message(error), 'error');
  }
}

async function manuscript(
  host: HTMLElement,
  account: string,
  tenant: string,
  entry: string,
  shell: ReturnType<typeof bindShell>,
) {
  const path = { tenant_id: tenant, entity_id: entry };

  const entityResult = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
    params: { path },
  });
  const entity = await unwrap(entityResult);
  const writingEntry = await outlineOf(tenant, entry);
  if (writingEntry.joined) {
    await compositionScreen(host, tenant, entry, true);
    const drafts = await readDrafts(draftKey(API_BASE_URL, account, tenant, entry)).catch(() => []);
    for (const saved of drafts) {
      const details = element('details');
      details.append(element('summary', 'Unsent draft before this join'));
      details.append(
        element(
          'p',
          'This local draft has not been applied to the joined manuscript. You can copy text from it.',
        ),
      );
      for (const payload of saved.draft.payloads) {
        if (payload.kind !== 'description') continue;
        const text = element('textarea');
        text.className = 'text-input';
        text.readOnly = true;
        text.value = payload.content;
        text.setAttribute('aria-label', 'Unsent draft text');
        details.append(text);
      }
      host.append(details);
    }
    return;
  }
  const structured = ['book', 'edition', 'chapter', 'carrier'].includes(writingEntry.kind);
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

  const exports = exportControls(tenant, entry);
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
      void writingDetails(
        worldDetails,
        tenant,
        entry,
        undefined,
        () =>
          editor
            .read()
            .flatMap((payload) => (payload.kind === 'description' ? [payload.content] : [])),
        applyRepositoryUpdate,
      ).catch((error) => {
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
    drawer.hidden = active;
    sideToggle.hidden = active;
    details.hidden = active;
    history.hidden = active;
    exports.hidden = active;
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

  const count = draftCount(
    () => editor.read().flatMap((p) => (p.kind === 'description' ? [p.content] : [])),
    { tenant, id: entry, scope: 'direct' },
  );
  const sessionGoal = writingSession(API_BASE_URL, account, tenant, () =>
    editor.read().flatMap((p) => (p.kind === 'description' ? [p.content] : [])),
  );
  count.element.append(sessionGoal.element);
  count.element.append(writingTimer(API_BASE_URL, account, tenant));
  // The page head: the way back, the title, the mode and the actions (ADR 0494, W2). The side
  // views are one drawer, docked from 1100px and a sheet below it, in place of closed panels.
  const head = element('header', '', 'page-head');
  const headTitle = element('div', '', 'stack-tight');
  headTitle.append(back, heading);
  const drawer = element('aside', '', 'side-drawer');
  drawer.id = 'side-views';
  drawer.setAttribute('aria-label', 'Side views');
  const sideToggle = button('Side views', () => {
    const open = drawer.dataset.open !== 'true';
    drawer.dataset.open = String(open);
    sideToggle.setAttribute('aria-expanded', String(open));
  });
  sideToggle.classList.add('side-toggle');
  sideToggle.setAttribute('aria-controls', 'side-views');
  sideToggle.setAttribute('aria-expanded', 'false');
  const sideClose = button('Close side views', () => {
    drawer.dataset.open = 'false';
    sideToggle.setAttribute('aria-expanded', 'false');
  });
  sideClose.classList.add('side-close');
  drawer.dataset.open = 'false';
  drawer.append(sideClose, count.element, details, exports, history);
  const wide = window.matchMedia('(min-width: 1100px)');
  const dock = () => {
    drawer.dataset.docked = String(wide.matches);
  };
  dock();
  wide.addEventListener('change', dock);
  actions.append(sideToggle);
  head.append(headTitle, actions);
  const main = element('div', '', 'stack');
  main.append(status, warning, conflicts, area);
  const frame = element('div', '', 'work-frame');
  frame.append(main, drawer);
  host.replaceChildren(head, frame);

  // What the status bar says of the save and of the length.
  const syncOf = (text: string) =>
    text.includes('changed elsewhere')
      ? 'conflict'
      : text.includes('Your draft is kept')
        ? 'offline'
        : text === 'Saved' || text.startsWith('Recovered')
          ? 'synced'
          : 'waiting';
  const tell = () =>
    shell?.statusBar({
      sync: syncOf(status.textContent ?? ''),
      ...(syncOf(status.textContent ?? '') === 'synced' ? { syncedAt: new Date() } : {}),
    });
  new MutationObserver(tell).observe(status, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  tell();
  let lengthTimer: ReturnType<typeof setTimeout> | undefined;
  const refreshCount = () => {
    count.refresh();
    clearTimeout(lengthTimer);
    lengthTimer = setTimeout(() => {
      const n = countSources(
        editor.read().flatMap((p) => (p.kind === 'description' ? [p.content] : [])),
      );
      shell?.statusBar({ meta: `${n} ${n === 1 ? 'word' : 'words'}` });
    }, 400);
  };

  // The page's parts act on saved text, so a change in the editor is saved first (ADR 0494, W3).
  let selected: string[] = [];
  const job = (run: () => Promise<void>) => {
    warning.textContent = '';
    void run().catch((error: unknown) => {
      warning.textContent = message(error);
    });
  };
  const settle = async () => {
    for (let wait = 0; wait < 40 && (saving || dirty) && !blocked; wait++) {
      if (saving) await new Promise((resolve) => setTimeout(resolve, 150));
      else await save();
    }
    if (dirty || blocked || saving)
      throw new Error('Save your changes first, and settle any conflict, then try again.');
  };
  const makeFrom = (ids: string[], kind: 'Chapter' | 'Scene') =>
    job(async () => {
      const title = await askTitle(`Name the new ${kind}`, `Make a ${kind}`);
      if (!title) return;
      await settle();
      await extractParts(tenant, entry, await outlineOf(tenant, entry), ids, kind, title);
      location.reload();
    });
  const selection = element('div', '', 'row');
  selection.setAttribute('role', 'region');
  selection.setAttribute('aria-label', 'Selected blocks');
  selection.hidden = true;
  const selectionCount = element('span');
  selection.append(
    selectionCount,
    button('Make a Chapter', () => makeFrom(selected, 'Chapter')),
    button('Make a Scene', () => makeFrom(selected, 'Scene')),
    button('Clear selection', () => editor.clearSelection()),
  );
  main.prepend(selection);

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
      blocks: {
        openMenu: (anchor, items) =>
          openMenu(
            anchor,
            items.filter((item) => !item.disabled),
            { label: 'Block options', sprite: `${BRANDING_CSS_URL}/icons.svg` },
          ),
        extraItems: (payload, caret) => [
          ...(payload.kind === 'description'
            ? [
                {
                  label: 'Split here',
                  run: () =>
                    job(async () => {
                      await settle();
                      await splitAtCaret(tenant, entry, payload.id, caret ?? 0);
                      location.reload();
                    }),
                },
              ]
            : []),
          { label: 'Make a Chapter', run: () => makeFrom([payload.id], 'Chapter') },
          { label: 'Make a Scene', run: () => makeFrom([payload.id], 'Scene') },
          {
            label: 'Copy link',
            run: () =>
              job(async () => {
                await navigator.clipboard.writeText(
                  `${location.origin}${writingAddress(tenant, entry, 'read')}#element-${payload.id}`,
                );
                warning.textContent = 'Link copied.';
              }),
          },
        ],
        onSelect: (ids) => {
          selection.hidden = ids.length === 0;
          selectionCount.textContent = `${ids.length} ${ids.length === 1 ? 'block' : 'blocks'} selected`;
          selected = ids;
        },
      },

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
          reviewEntitySelection: () => review.open(),
          layout: 'tabs',
          toolbar: ['bold', 'italic', 'heading', 'bullets', '|', 'link', 'entity', 'undo'],

          render: (source) => render(parse(source), { externalImages: false }),
        });

        const review = linkReview(tenant, text, control);
        container.append(review.element);

        return {
          value: () => text.value,
          focus: () => text.focus(),
          caret: () => text.selectionStart,
          destroy: () => control.destroy(),
        };
      },
    });

    area.replaceChildren(editor.element);
    sessionGoal.rebase();
    refreshCount();
    observed = fingerprint(editor.read());
  }

  function changed() {
    if (!alive) return;

    const next = fingerprint(editor.read());
    if (next === observed) return;
    observed = next;
    sessionGoal.changed();
    refreshCount();
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

  async function applyRepositoryUpdate(
    action: () => Promise<void>,
    options?: { composition: boolean },
  ) {
    if (!alive || dirty || saving || blocked) {
      throw new Error('Save your draft and resolve any conflicts before accepting an update.');
    }
    saving = true;
    area.inert = true;
    saveButton.disabled = true;
    try {
      await action();
      if (!alive) return;
      if (options?.composition) {
        blocked = true;
        location.reload();
        return;
      }
      // The server may have accepted an update even if the following read fails.
      // Keep the mounted draft protected until its current versions can be read.
      blocked = true;
      const current = await read();
      if (!alive) return;
      original = current;
      receipt = { id: current.id, information: current };
      mount(current.payloads);
      observed = fingerprint(current.payloads);
      await serial;
      try {
        await removeDraft(key);
      } catch {
        warning.textContent = 'Saved on the server. Browser recovery could not be cleared.';
      }
      dirty = false;
      blocked = false;
      status.textContent = 'Saved';
    } catch (error) {
      if (blocked)
        status.textContent = 'Update accepted. Reload to read the saved manuscript before editing.';
      throw error;
    } finally {
      saving = false;
      area.inert = blocked;
      saveButton.disabled = blocked;
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

  let leaving = false;
  window.addEventListener('beforeunload', (event) => {
    if (dirty && !persisted && !leaving) {
      event.preventDefault();
    }
  });

  // Leaving by a link with changes that were not kept anywhere asks first, in words (ADR 0494, W2).
  document.addEventListener(
    'click',
    (event) => {
      const link = (event.target as Element | null)?.closest?.(
        'a[href]',
      ) as HTMLAnchorElement | null;
      if (!link || !dirty || persisted || leaving) return;
      if (link.target === '_blank' || link.origin !== location.origin) return;
      if (link.pathname === location.pathname && link.search === location.search) return;
      event.preventDefault();
      event.stopPropagation();
      void confirmDialog({
        title: 'Leave without saving?',
        body: 'Your latest changes are not saved yet, and could not be kept in this browser.',
        confirm: 'Leave anyway',
        cancel: 'Stay',
        danger: true,
      }).then((go) => {
        if (!go) return;
        leaving = true;
        location.assign(link.href);
      });
    },
    true,
  );

  const stop = () => {
    alive = false;
    clearTimeout(timer);
    editor.destroy();
  };

  window.addEventListener('pagehide', stop, { once: true });
  window.addEventListener('lorenzo:sign-out', stop, { once: true });
}

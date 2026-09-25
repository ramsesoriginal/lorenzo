// Slugs in inventory-web (ADR 0107, 0113): suggesting one for an item or an
// instance, checking it, saving it, and finding what holds one.
import { slugify } from '@lorenzo/lorenzoscript';
import { ApiError, client, type components, unwrap } from './api';
import { getEntityDetail } from './items';

export type ResolvedSlug = components['schemas']['ResolvedSlugOut'];

/** ADR 0107's grammar, so every slug can be written in a link: `[text](slug)`. */
const GRAMMAR = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const MAX_LENGTH = 100;
/** How many candidates one resolve request checks (ADR 0113). */
const CANDIDATES = 20;

export type SlugKind = 'item' | 'instance';

/**
 * What a slug for something shown as `title` could be, best first. A catalog item takes the
 * title itself, the slug `[[Title]]` looks for, then `-2`, `-3`; an instance numbers from
 * `-1`, leaving the bare title to its item. None if the title has no letters or digits.
 */
export function slugCandidates(title: string, kind: SlugKind): string[] {
  const base = slugify(title);
  if (!base) return [];
  return Array.from({ length: CANDIDATES }, (_, i) => {
    const suffix = kind === 'item' && i === 0 ? '' : `-${i + 1}`;
    return base.slice(0, MAX_LENGTH - suffix.length).replace(/-+$/, '') + suffix;
  });
}

/** The entities holding any of `slugs`, in one request (ADR 0107). */
export async function resolveSlugs(tenantId: string, slugs: string[]): Promise<ResolvedSlug[]> {
  return unwrap(
    await client.GET('/tenants/{tenant_id}/entities/resolve', {
      params: { path: { tenant_id: tenantId }, query: { slug: slugs } },
    }),
  );
}

/** The first candidate nothing in the tenant holds, or '' if there's none to give. */
export async function suggestSlug(
  tenantId: string,
  title: string,
  kind: SlugKind,
): Promise<string> {
  const candidates = slugCandidates(title, kind);
  if (candidates.length === 0) return '';
  const taken = new Set((await resolveSlugs(tenantId, candidates)).map((found) => found.slug));
  return candidates.find((candidate) => !taken.has(candidate)) ?? '';
}

/** Why `value` can't be a slug, or null if it can. */
export function slugProblem(value: string): string | null {
  if (value.length > MAX_LENGTH) return `A slug has at most ${MAX_LENGTH} characters.`;
  if (!GRAMMAR.test(value)) {
    return 'A slug starts with a letter or digit, and has only letters, digits, - and _.';
  }
  return null;
}

/** Saves a slug field's value: nothing if it's unchanged, a clear if it's empty, else a set. */
export async function saveSlug(
  tenantId: string,
  entityId: string,
  current: string | null,
  value: string,
): Promise<void> {
  const wanted = value.trim();
  if (wanted === (current ?? '')) return;
  const params = { path: { tenant_id: tenantId, entity_id: entityId } };
  const path = '/tenants/{tenant_id}/entities/{entity_id}/slug';
  if (!wanted) {
    await unwrap(await client.DELETE(path, { params }));
    return;
  }
  const problem = slugProblem(wanted);
  if (problem) throw new Error(problem);
  try {
    await unwrap(await client.PUT(path, { params, body: { slug: wanted } }));
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      throw new Error(`Another entity already uses “${wanted}”.`);
    }
    throw e;
  }
}

export type SlugField = { element: HTMLElement; input: HTMLInputElement };

const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text = '') =>
  Object.assign(document.createElement(tag), { className, textContent: text });

let fields = 0;

/**
 * The Slug field, holding `initial`. With `follow`, it keeps a suggestion for whatever
 * `follow.title()` reads, updated as any of `follow.inputs` changes, until the GM edits it.
 */
export function slugField(
  initial: string,
  follow?: {
    inputs: HTMLInputElement[];
    title: () => string;
    suggest: (title: string) => Promise<string>;
  },
): SlugField {
  const input = Object.assign(make('input', 'text-input'), { type: 'text', value: initial });
  input.spellcheck = false;
  const label = make('label', 'field');
  label.append(make('span', 'field-label', 'Slug'), input);
  // Outside the label, so it describes the field rather than being part of its name.
  const note = make('p', 'field-note', 'How links name it, as in [text](slug). Empty for none.');
  note.id = `slug-note-${++fields}`;
  input.setAttribute('aria-describedby', note.id);
  const field = make('div', 'slug-field');
  field.append(label, note);
  if (follow) {
    let edited = false;
    let asked = 0;
    let debounce: ReturnType<typeof setTimeout> | undefined;
    input.addEventListener('input', () => {
      edited = true;
    });
    const update = () => {
      clearTimeout(debounce);
      debounce = setTimeout(async () => {
        const turn = ++asked;
        const suggestion = await follow.suggest(follow.title()).catch(() => '');
        if (!edited && turn === asked) input.value = suggestion;
      }, 250);
    };
    for (const source of follow.inputs) source.addEventListener('input', update);
  }
  return { element: field, input };
}

/**
 * The item page's slug editor for GMs (ADR 0113): the field, holding the entity's slug or a
 * suggestion, and Save. `onSaved` gets the slug it has now, or null.
 */
export async function renderSlugEditor(
  container: HTMLElement,
  options: {
    tenantId: string;
    entityId: string;
    title: string;
    kind: SlugKind;
    onSaved: (slug: string | null) => void;
  },
): Promise<void> {
  const { tenantId, entityId } = options;
  container.replaceChildren(make('p', 'status-text', 'Loading the slug…'));
  let current: string | null;
  let initial: string;
  try {
    current = (await getEntityDetail(tenantId, entityId)).slug;
    initial = current ?? (await suggestSlug(tenantId, options.title, options.kind));
  } catch (e) {
    const reason = e instanceof Error ? e.message : String(e);
    container.replaceChildren(make('p', 'status-text', `Couldn't load the slug: ${reason}`));
    return;
  }
  const { element, input } = slugField(initial);
  const save = Object.assign(make('button', '', 'Save slug'), { type: 'submit' });
  const status = make('p', 'status-text');
  status.setAttribute('role', 'status');
  const form = make('form', 'slug-form');
  form.append(element, save, status);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    save.disabled = true;
    status.classList.remove('error-text');
    status.textContent = 'Saving…';
    try {
      await saveSlug(tenantId, entityId, current, input.value);
      current = input.value.trim() || null;
      status.textContent = current ? 'Saved.' : 'Cleared.';
      options.onSaved(current);
    } catch (e) {
      status.classList.add('error-text');
      status.textContent = e instanceof Error ? e.message : String(e);
    } finally {
      save.disabled = false;
    }
  });
  container.replaceChildren(form);
}

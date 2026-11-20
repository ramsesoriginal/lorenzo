import { closeDialog, fadeOnDismiss, openDialog } from '@lorenzo/app-shell';
import { parse, render } from '@lorenzo/lorenzoscript';
import { client, unwrap } from './api';
import { BRANDING_CSS_URL } from './config';
import { contentsNavigation } from './contents';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};
const preview = async (tenant: string, id: string, review: boolean, version?: string) =>
  unwrap(
    await client.GET(
      review
        ? '/tenants/{tenant_id}/writing/reviews/{id}/export'
        : '/tenants/{tenant_id}/writing/entries/{id}/export',
      {
        params: { path: { tenant_id: tenant, id }, header: version ? { 'if-match': version } : {} },
      },
    ),
  );
export type ExportSnapshot = Awaited<ReturnType<typeof preview>>;

/** Every rendering occurrence owns its heading, footnote and local-link IDs. */
export function exportArticle(snapshot: ExportSnapshot) {
  const article = node('article');
  article.className = 'ls-content';
  const entries = new Map(snapshot.entries.map((entry) => [entry.id, entry]));
  const payloads = new Map((snapshot.payloads ?? []).map((payload) => [payload.id, payload]));
  const prefix = `export-${crypto.randomUUID()}`;
  let serial = 0;
  const first = new Map<string, string>();
  const contentsLinks: { link: HTMLAnchorElement; id: string; scope: Map<string, string> }[] = [];
  type Task = {
    kind: 'entry' | 'payload';
    id: string;
    parent: HTMLElement;
    selected?: string;
    scope: Map<string, string>;
    depth: number;
  };
  const pending: Task[] = [
    { kind: 'entry', id: snapshot.root_id, parent: article, scope: first, depth: 1 },
  ];
  while (pending.length) {
    const part = pending.pop();
    if (!part) break;
    const occurrence = `${prefix}-${serial++}`;
    if (part.kind === 'payload') {
      const payload = payloads.get(part.id);
      if (!payload) continue;
      if (payload.kind === 'picture') {
        const picture = node('img');
        picture.alt = 'Manuscript illustration';
        picture.src = `data:${payload.media_type};base64,${payload.data}`;
        part.parent.append(picture);
      } else {
        const prose = node('div');
        prose.innerHTML = render(parse(payload.content ?? ''), { externalImages: false });
        const ids = new Map<string, string>();
        for (const el of prose.querySelectorAll<HTMLElement>('[id]')) {
          const old = el.id;
          el.id = `${occurrence}-${old}`;
          ids.set(old, el.id);
        }
        for (const link of prose.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
          const original = link.getAttribute('href')?.slice(1) ?? '';
          link.setAttribute('href', `#${ids.get(original) ?? `${occurrence}-${original}`}`);
        }
        part.parent.append(prose);
      }
      continue;
    }
    const entry = entries.get(part.id);
    if (!entry) continue;
    const section = node('section');
    section.id = occurrence;
    part.scope.set(entry.id, part.scope.get(entry.id) ?? occurrence);
    section.append(
      node(
        `h${Math.min(part.depth, 6)}` as 'h1',
        `${entry.number ? `${entry.number} ` : ''}${entry.name}`,
      ),
    );
    part.parent.append(section);
    if (entry.joined) section.append(node('p', 'This section was joined to another section.'));
    if (entry.contents) {
      const rows = entry.contents.flatMap((row) =>
        typeof row.id === 'string' && typeof row.label === 'string' && typeof row.depth === 'number'
          ? [{ id: row.id, label: row.label, depth: row.depth }]
          : [],
      );
      const nav = contentsNavigation(rows, (id) => `#${id}`);
      for (const link of nav.querySelectorAll<HTMLAnchorElement>('a[href]')) {
        contentsLinks.push({
          link,
          id: link.getAttribute('href')?.slice(1) ?? '',
          scope: part.scope,
        });
      }
      section.append(nav);
    }
    for (const element of [...entry.elements].reverse()) {
      if (part.selected && element.id !== part.selected) continue;
      if (element.kind === 'payload')
        pending.push({
          kind: 'payload',
          id: element.id,
          parent: section,
          scope: part.scope,
          depth: part.depth,
        });
      else if (element.kind === 'coverage' && element.target_id)
        pending.push({
          kind: 'entry',
          id: element.target_id,
          selected: element.payload_id ?? undefined,
          parent: section,
          scope: new Map(),
          depth: part.depth + 1,
        });
      else if (element.kind === 'chapter' || element.kind === 'scene_telling')
        pending.push({
          kind: 'entry',
          id: element.id,
          parent: section,
          scope: part.scope,
          depth: part.depth + 1,
        });
    }
  }
  for (const { link, id, scope } of contentsLinks) {
    const target = scope.get(id);
    if (target) link.href = `#${target}`;
  }
  return article;
}

/** Isolated print layout: no application chrome or unsaved editor contents. */
export async function printExport(snapshot: ExportSnapshot, active = () => true) {
  const frame = node('iframe');
  frame.title = 'Printable manuscript';
  frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
  frame.style.cssText = 'position:fixed;left:-10000px;width:800px;height:600px;border:0';
  document.body.append(frame);
  try {
    const doc = frame.contentDocument;
    if (!doc || !frame.contentWindow) throw new Error('The print preview could not be opened.');
    doc.title =
      snapshot.entries.find((entry) => entry.id === snapshot.root_id)?.name ?? 'Manuscript';
    const fonts = doc.createElement('link');
    fonts.rel = 'stylesheet';
    fonts.href = new URL(`${BRANDING_CSS_URL}/fonts.css`, location.href).href;
    const loaded = new Promise<void>((resolve, reject) => {
      fonts.onload = () => resolve();
      fonts.onerror = () =>
        reject(new Error('The manuscript fonts could not be loaded. Try again.'));
    });
    doc.head.append(fonts);
    const style = doc.createElement('style');
    style.textContent = `@page { margin: 20mm; } body { color: #111; background: white;
      font: 12pt/1.5 "Newsreader Variable", serif; } h1,h2,h3,h4,h5,h6 { font-family: "Geist Variable", sans-serif;
      break-after: avoid; } p { orphans: 3; widows: 3; } img { max-width:100%; height:auto; }
      pre { white-space:pre-wrap; } pre,code { font-family: 'Geist Mono Variable', monospace; }
      table { border-collapse:collapse; max-width:100%; } td,th { border:1px solid #aaa; padding:4pt; }
      a { color:inherit; } blockquote { margin-left:1em; }`;
    doc.head.append(style);
    doc.body.append(doc.adoptNode(exportArticle(snapshot)));
    await loaded;
    await Promise.all([
      doc.fonts.load('12pt "Newsreader Variable"'),
      doc.fonts.load('bold 24pt "Geist Variable"'),
      doc.fonts.load('12pt "Geist Mono Variable"'),
    ]);
    await doc.fonts.ready;
    await Promise.all([...doc.images].map((image) => image.decode()));
    if (!active()) {
      frame.remove();
      return;
    }
    // Some browsers return before the dialog closes. Keep its document until afterprint.
    const cleanup = () => {
      window.removeEventListener('pagehide', cleanup);
      window.removeEventListener('lorenzo:sign-out', cleanup);
      frame.remove();
    };
    frame.contentWindow.addEventListener('afterprint', cleanup, { once: true });
    window.addEventListener('pagehide', cleanup, { once: true });
    window.addEventListener('lorenzo:sign-out', cleanup, { once: true });
    frame.contentWindow.focus();
    frame.contentWindow.print();
  } catch (error) {
    frame.remove();
    throw error;
  }
}

export function exportControls(tenant: string, id: string, review = false) {
  // Export is a dialog opened from a button (ADR 0494, W6); the panel inside is what it always was.
  const host = node('div');
  const open = node('button', 'Export');
  open.type = 'button';
  open.className = 'btn btn-secondary';
  open.setAttribute('aria-haspopup', 'dialog');
  const dialog = node('dialog');
  const heading = node('h2', 'Export');
  heading.id = `export-${crypto.randomUUID()}`;
  dialog.setAttribute('aria-labelledby', heading.id);
  const details = node('div');
  details.className = 'stack-tight';
  details.append(node('p', 'Export saved writing. Changes still in the editor are not included.'));
  const status = node('p');
  status.setAttribute('role', 'status');
  const actions = node('div');
  actions.className = 'row';
  const output = node('div');
  let snapshot: ExportSnapshot | undefined;
  const buttons: HTMLButtonElement[] = [];
  const action = (label: string, run: () => Promise<void>) => {
    const button = node('button', label);
    button.type = 'button';
    button.className = 'btn btn-secondary';
    buttons.push(button);
    button.addEventListener('click', () => {
      for (const item of buttons) item.disabled = true;
      status.textContent = 'Preparing saved writing…';
      void run()
        .then(() => {
          status.textContent = '';
        })
        .catch((error: unknown) => {
          snapshot = undefined;
          output.replaceChildren();
          status.textContent =
            error instanceof Error ? error.message : 'This export is not available.';
        })
        .finally(() => {
          for (const item of buttons) item.disabled = item !== refresh && !snapshot;
        });
    });
    actions.append(button);
    return button;
  };
  const refresh = action('Preview saved writing', async () => {
    const saved = await preview(tenant, id, review);
    if (!details.isConnected) return;
    snapshot = saved;
    output.replaceChildren(exportArticle(saved));
  });
  const source = action('Download LorenzoScript', async () => {
    if (!snapshot) return;
    const blob = await unwrap(
      await client.GET(
        review
          ? '/tenants/{tenant_id}/writing/reviews/{id}/export/source'
          : '/tenants/{tenant_id}/writing/entries/{id}/export/source',
        {
          params: { path: { tenant_id: tenant, id }, header: { 'if-match': snapshot.version } },
          parseAs: 'blob',
        },
      ),
    );
    if (!details.isConnected) return;
    const url = URL.createObjectURL(blob);
    const link = node('a');
    link.href = url;
    link.download = 'lorenzo-writing.zip';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  const print = action('Print / Save as PDF', async () => {
    if (!snapshot) return;
    const saved = await preview(tenant, id, review, snapshot.version);
    if (details.isConnected) await printExport(saved, () => details.isConnected);
  });
  source.disabled = print.disabled = true;
  details.append(
    actions,
    node(
      'p',
      'For PDF, choose Save as PDF in the print dialog. Turn off browser headers and footers for a clean manuscript.',
    ),
    status,
    output,
  );
  const close = node('button', 'Close');
  close.type = 'button';
  close.className = 'btn btn-secondary';
  close.addEventListener('click', () => closeDialog(dialog));
  dialog.append(heading, details, close);
  fadeOnDismiss(dialog);
  open.addEventListener('click', () => openDialog(dialog));
  host.append(open, dialog);
  return host;
}

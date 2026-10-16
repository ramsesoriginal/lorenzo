import type { DraftPayload, Information, Payload } from './bundles';
import { initialText } from './bundles';

type TextEditor = { value(): string; focus(): void; destroy(): void };
type LoadFile = (payload: Extract<Payload, { kind: 'picture' | 'document' }>) => Promise<string>;
const button = (label: string, action: () => void) => {
  const node = document.createElement('button');
  node.type = 'button';
  node.className = 'btn btn-secondary';
  node.textContent = label;
  node.addEventListener('click', action);
  return node;
};
const image = (alt: string) => {
  const node = document.createElement('img');
  node.alt = alt;
  node.style.maxWidth = '100%';
  node.style.maxHeight = '32rem';
  node.style.objectFit = 'contain';
  return node;
};

/** Read every payload in order; protected bytes use the app's existing authenticated loader. */
export function renderInformationPayloads(
  host: HTMLElement,
  options: {
    information: Information;
    renderText(host: HTMLElement, content: string): void | Promise<void>;
    loadFile: LoadFile;
  },
): void {
  host.replaceChildren();
  host.classList.add('stack-tight');
  for (const payload of options.information.payloads) {
    const row = document.createElement('div');
    host.append(row);
    if (payload.kind === 'description') {
      void options.renderText(row, payload.content);
      continue;
    }
    if (payload.kind === 'number') {
      row.textContent = String(payload.value);
      continue;
    }
    const link = document.createElement('a');
    link.target = '_blank';
    link.rel = 'noopener';
    if (payload.kind === 'picture')
      link.append(image(options.information.title || 'Attached image'));
    else {
      link.textContent = payload.filename;
      link.download = payload.filename;
    }
    row.append(link);
    void options
      .loadFile(payload)
      .then((url) => {
        link.href = url;
        const picture = link.querySelector('img');
        if (picture) picture.src = url;
      })
      .catch(() => {
        row.textContent =
          payload.kind === 'picture'
            ? 'This picture could not be loaded.'
            : 'This file could not be loaded.';
      });
  }
}

/** The existing LorenzoScript field, repeated only when a bundle has more than one text. */
export function renderBundleEditor(options: {
  initial?: readonly Payload[];
  content: string;
  textLabel: string;
  createTextEditor(host: HTMLElement, label: string, content: string): TextEditor;
  loadFile: LoadFile;
}): { element: HTMLElement; read(): DraftPayload[]; ready(): Promise<void>; destroy(): void } {
  type Row = {
    payload: DraftPayload;
    element: HTMLElement;
    editor?: TextEditor;
    revoke?: () => void;
    error?: string;
    validation?: Promise<void>;
    controls: HTMLElement;
  };
  let rows: Row[] = [];
  const root = document.createElement('div');
  root.className = 'stack-tight';
  const list = document.createElement('div');
  list.className = 'stack-tight';
  const actions = document.createElement('div');
  actions.className = 'row';
  const picker = document.createElement('input');
  picker.type = 'file';
  picker.multiple = true;
  picker.accept = 'image/png,image/jpeg,image/webp,image/gif';
  picker.hidden = true;
  root.append(list, actions, picker);
  let textNumber = 0;
  function paint() {
    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    for (const [index, row] of rows.entries()) {
      row.payload.order = index;
      row.controls.hidden = rows.length === 1 && row.payload.kind === 'description';
      const up = row.controls.querySelector<HTMLButtonElement>('[data-up]');
      const down = row.controls.querySelector<HTMLButtonElement>('[data-down]');
      if (up) up.disabled = index === 0;
      if (down) down.disabled = index === rows.length - 1;
    }
    list.append(...rows.map((r) => r.element));
    if (active?.isConnected) active.focus();
  }
  function add(payload: DraftPayload): Row {
    const row: Row = {
      payload,
      element: document.createElement('div'),
      controls: document.createElement('div'),
    };
    row.element.className = 'stack-tight';
    row.controls.className = 'row';
    const body = document.createElement('div');
    row.element.append(body, row.controls);
    if (payload.kind === 'description') {
      textNumber += 1;
      row.editor = options.createTextEditor(
        body,
        textNumber === 1 ? options.textLabel : `Text ${textNumber}`,
        payload.content,
      );
    } else if (payload.kind === 'picture' && payload.file) {
      const file = payload.file;
      const picture = image(file.name);
      const note = document.createElement('p');
      note.className = 'caption';
      note.setAttribute('role', 'status');
      body.append(picture, note);
      const url = URL.createObjectURL(file);
      row.revoke = () => URL.revokeObjectURL(url);
      row.validation = (async () => {
        try {
          if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type))
            throw new Error('Choose a PNG, JPEG, WebP or GIF image.');
          if (!file.size) throw new Error('This image is empty.');
          picture.src = url;
          await picture.decode();
          if (
            picture.naturalWidth * picture.naturalHeight > 100_000_000 ||
            Math.max(picture.naturalWidth, picture.naturalHeight) > 32768
          )
            throw new Error('This image is too large to display. Choose a smaller copy.');
        } catch (error) {
          row.error =
            error instanceof Error && error.name !== 'EncodingError'
              ? error.message
              : 'This file could not be read as an image.';
          note.textContent = row.error;
          picture.hidden = true;
        }
      })();
    } else {
      const information: Information = {
        id: '',
        title: 'Attachment',
        type: 'note',
        is_public: false,
        order: 0,
        updated_at: '',
        payloads: [payload],
      };
      renderInformationPayloads(body, {
        information,
        loadFile: options.loadFile,
        renderText: () => {},
      });
    }
    const move = (step: number) => {
      const index = rows.indexOf(row),
        to = index + step;
      if (to < 0 || to >= rows.length) return;
      rows.splice(index, 1);
      rows.splice(to, 0, row);
      paint();
    };
    const up = button('↑', () => move(-1));
    up.dataset.up = '';
    up.setAttribute('aria-label', 'Move this part up');
    up.title = 'Move up';
    const down = button('↓', () => move(1));
    down.dataset.down = '';
    down.setAttribute('aria-label', 'Move this part down');
    down.title = 'Move down';
    row.controls.append(up, down);
    if (['description', 'picture'].includes(payload.kind))
      row.controls.append(
        button(payload.kind === 'picture' ? 'Remove picture' : 'Remove text', () => {
          row.editor?.destroy();
          row.revoke?.();
          rows = rows.filter((r) => r !== row);
          row.element.remove();
          paint();
        }),
      );
    rows.push(row);
    paint();
    return row;
  }
  for (const payload of options.initial ?? [initialText(options.content)]) add({ ...payload });
  actions.append(
    button('Add picture', () => picker.click()),
    button('Add text', () => {
      const row = add({
        id: crypto.randomUUID(),
        kind: 'description',
        content: '',
        locale: '',
        order: rows.length,
        updated_at: '',
      });
      row.editor?.focus();
    }),
  );
  picker.addEventListener('change', () => {
    for (const selected of Array.from(picker.files ?? [])) {
      const fallback = (
        {
          png: 'image/png',
          jpg: 'image/jpeg',
          jpeg: 'image/jpeg',
          webp: 'image/webp',
          gif: 'image/gif',
        } as Record<string, string>
      )[selected.name.split('.').at(-1)?.toLowerCase() ?? ''];
      const file =
        selected.type || !fallback
          ? selected
          : new File([selected], selected.name, {
              type: fallback,
              lastModified: selected.lastModified,
            });
      add({
        id: crypto.randomUUID(),
        kind: 'picture',
        url: '',
        file_type: file.type,
        file,
        order: rows.length,
        updated_at: '',
      });
    }
    picker.value = '';
  });
  return {
    element: root,
    read: () =>
      rows.map((row) =>
        row.payload.kind === 'description'
          ? { ...row.payload, content: row.editor?.value() ?? row.payload.content }
          : { ...row.payload },
      ),
    ready: async () => {
      await Promise.all(rows.map((row) => row.validation));
      const error = rows.find((row) => row.error)?.error;
      if (error) throw new Error(error);
    },
    destroy: () => {
      for (const row of rows) {
        row.editor?.destroy();
        row.revoke?.();
      }
    },
  };
}

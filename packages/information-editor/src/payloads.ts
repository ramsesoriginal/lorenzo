import type { DraftPayload, Information, Payload } from './bundles';
import { initialText } from './bundles';

type TextEditor = {
  value(): string;
  focus(): void;
  destroy(): void;
  /** Where the caret is in the text, when the editor can say (blocks mode). */
  caret?(): number;
};

/** One entry of a block's menu. */
export type BlockItem = { label: string; run(): void; disabled?: boolean };

/** Opt-in block handling (ADR 0494, W3): a grip and a menu on each part, Alt with the arrow keys
 * to move it, a quiet plus between parts, and a selection of parts the app can act on. */
export type BlockOptions = {
  openMenu(anchor: HTMLElement, items: BlockItem[]): void;
  /** What the app adds to a part's menu, after Move, Select and Remove. */
  extraItems?(payload: DraftPayload, caret: number | null): BlockItem[];
  /** The selected parts, in reading order, whenever the selection changes. */
  onSelect?(ids: string[]): void;
};
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

/** Decode and bound acquired images before staging or sending their bytes. */
export async function validatePicture(file: File, preview?: HTMLImageElement): Promise<void> {
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type))
    throw new Error('Choose a PNG, JPEG, WebP or GIF image.');
  if (!file.size) throw new Error('This image is empty.');
  let bitmap: ImageBitmap | undefined;
  try {
    if (preview) await preview.decode();
    else bitmap = await createImageBitmap(file);
    const width = preview?.naturalWidth ?? bitmap?.width ?? 0;
    const height = preview?.naturalHeight ?? bitmap?.height ?? 0;
    if (width * height > 100_000_000 || Math.max(width, height) > 32768)
      throw new Error('This image is too large to display. Choose a smaller copy.');
  } catch (error) {
    if (error instanceof Error && ['EncodingError', 'InvalidStateError'].includes(error.name))
      throw new Error('This file could not be read as an image.');
    throw error;
  } finally {
    bitmap?.close();
  }
}

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
  blocks?: BlockOptions;
}): {
  element: HTMLElement;
  read(): DraftPayload[];
  ready(): Promise<void>;
  destroy(): void;
  selected(): string[];
  clearSelection(): void;
} {
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
  let insertAt: number | null = null;
  const blocks = options.blocks;
  const chosen = new Set<string>();
  const selectedIds = () => rows.filter((r) => chosen.has(r.payload.id)).map((r) => r.payload.id);
  const announce = () => {
    for (const row of rows) row.element.dataset.selected = String(chosen.has(row.payload.id));
    blocks?.onSelect?.(selectedIds());
  };
  // A change made from a menu is outside the page's own events; say so for its autosave.
  const touched = () => {
    if (blocks) root.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const gap = (at: number) => {
    const plus = button('+', () =>
      blocks?.openMenu(plus, [
        {
          label: 'Add text',
          run: () => addText(at),
        },
        {
          label: 'Add picture',
          run: () => {
            insertAt = at;
            picker.click();
          },
        },
      ]),
    );
    plus.setAttribute('aria-label', 'Add a block here');
    plus.title = 'Add a block here';
    plus.dataset.gap = '';
    return plus;
  };
  function paint() {
    const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    for (const [index, row] of rows.entries()) {
      row.payload.order = index;
      row.controls.hidden = !blocks && rows.length === 1 && row.payload.kind === 'description';
      const up = row.controls.querySelector<HTMLButtonElement>('[data-up]');
      const down = row.controls.querySelector<HTMLButtonElement>('[data-down]');
      if (up) up.disabled = index === 0;
      if (down) down.disabled = index === rows.length - 1;
    }
    if (blocks) {
      list.replaceChildren(...rows.flatMap((r, i) => [...(i === 0 ? [] : [gap(i)]), r.element]));
    } else list.append(...rows.map((r) => r.element));
    if (active?.isConnected) active.focus();
  }
  function add(payload: DraftPayload, at = rows.length): Row {
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
          picture.src = url;
          await validatePicture(file, picture);
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
      announce();
      touched();
    };
    const remove = () => {
      row.editor?.destroy();
      row.revoke?.();
      rows = rows.filter((r) => r !== row);
      chosen.delete(row.payload.id);
      row.element.remove();
      paint();
      announce();
      touched();
    };
    const up = button('↑', () => move(-1));
    up.dataset.up = '';
    up.setAttribute('aria-label', 'Move this part up');
    up.title = 'Move up';
    const down = button('↓', () => move(1));
    down.dataset.down = '';
    down.setAttribute('aria-label', 'Move this part down');
    down.title = 'Move down';
    const removable = ['description', 'picture'].includes(payload.kind);
    const removeButton = removable
      ? button(payload.kind === 'picture' ? 'Remove picture' : 'Remove text', remove)
      : null;
    if (blocks) {
      const grip = button('⋮⋮', () => {});
      grip.setAttribute('aria-label', 'Block options');
      grip.setAttribute('aria-haspopup', 'menu');
      grip.title = 'Block options';
      grip.dataset.grip = '';
      const items = (): BlockItem[] => {
        const index = rows.indexOf(row);
        return [
          { label: 'Move up', run: () => move(-1), disabled: index === 0 },
          { label: 'Move down', run: () => move(1), disabled: index === rows.length - 1 },
          {
            label: chosen.has(payload.id) ? 'Unselect this block' : 'Select this block',
            run: () => {
              if (chosen.has(payload.id)) chosen.delete(payload.id);
              else chosen.add(payload.id);
              announce();
            },
          },
          ...(blocks.extraItems?.(row.payload, row.editor?.caret?.() ?? null) ?? []),
          ...(removable
            ? [
                {
                  label: payload.kind === 'picture' ? 'Remove picture' : 'Remove text',
                  run: remove,
                },
              ]
            : []),
        ];
      };
      const open = () => blocks.openMenu(grip, items());
      grip.addEventListener('click', open);
      let press: ReturnType<typeof setTimeout> | undefined;
      grip.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'touch') press = setTimeout(open, 500);
      });
      for (const end of ['pointerup', 'pointercancel', 'pointerleave'])
        grip.addEventListener(end, () => clearTimeout(press));
      const wantsMenu = (event: KeyboardEvent) =>
        event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10');
      row.element.addEventListener('contextmenu', (event) => {
        if ((event.target as HTMLElement).closest('textarea,input')) return;
        event.preventDefault();
        open();
      });
      row.element.addEventListener('keydown', (event) => {
        if (event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
          event.preventDefault();
          move(event.key === 'ArrowUp' ? -1 : 1);
        } else if (wantsMenu(event)) {
          event.preventDefault();
          open();
        }
      });
      // The grip is the one control; Move and Remove live in its menu.
      row.controls.replaceChildren(grip);
      up.hidden = down.hidden = true;
    } else {
      row.controls.append(up, down);
      if (removeButton) row.controls.append(removeButton);
    }
    rows.splice(at, 0, row);
    paint();
    return row;
  }
  for (const payload of options.initial ?? [initialText(options.content)]) add({ ...payload });
  function addText(at = rows.length) {
    const row = add(
      {
        id: crypto.randomUUID(),
        kind: 'description',
        content: '',
        locale: '',
        order: at,
        updated_at: '',
      },
      at,
    );
    row.editor?.focus();
    touched();
  }
  actions.append(
    button('Add picture', () => {
      insertAt = null;
      picker.click();
    }),
    button('Add text', () => addText()),
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
      const at = insertAt === null ? rows.length : insertAt;
      add(
        {
          id: crypto.randomUUID(),
          kind: 'picture',
          url: '',
          file_type: file.type,
          file,
          order: at,
          updated_at: '',
        },
        at,
      );
      if (insertAt !== null) insertAt += 1;
    }
    insertAt = null;
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
    selected: selectedIds,
    clearSelection: () => {
      chosen.clear();
      announce();
    },
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

// The fields a piece of information is written with (ADR 0112): its title,
// type, who can read it, and its LorenzoScript text in the editor (ADR 0106),
// with notes on links readers won't be able to follow. Either embedded in a
// larger form (Manage items' create form and edit panel) or standing alone.
import { createEditor } from '@lorenzo/lorenzoscript-editor';
import { ApiError } from './api';
import type { Renderer } from './descriptions';
import type { InformationDraft } from './information';

export type FieldsOptions = {
  initial: InformationDraft;
  renderer: Renderer;
  /** "Title" unless given; a description's is "Display title", the item's shown name. */
  titleLabel?: string;
  textLabel?: string;
  showType?: boolean;
  showVisibility?: boolean;
  /** The public checkbox's label, "Players can read this" unless given. */
  visibilityLabel?: string;
  /** Said under the checkbox, such as who can read it otherwise. */
  visibilityNote?: string;
};

export type InfoFields = {
  element: HTMLElement;
  /** Exposed so a caller can keep it in step with a name until the author edits it. */
  title: HTMLInputElement;
  read(): InformationDraft;
  changed(): boolean;
  destroy(): void;
};

const STALE =
  'Someone changed this after you opened it. Copy your text, reload the page, and make your changes again.';

const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text = '') =>
  Object.assign(document.createElement(tag), { className, textContent: text });

function field(label: string, control: HTMLElement): HTMLElement {
  // A div, not a label: the text field holds the editor's toolbar buttons.
  const wrapper = make(control instanceof HTMLInputElement ? 'label' : 'div', 'field');
  wrapper.append(make('span', 'field-label', label), control);
  return wrapper;
}

let visibilityNotes = 0;

export function infoFields(options: FieldsOptions): InfoFields {
  const { initial, renderer } = options;
  const input = (value: string) =>
    Object.assign(make('input', 'text-input'), { type: 'text', value });
  const title = input(initial.title);
  const type = input(initial.type);
  const isPublic = Object.assign(document.createElement('input'), {
    type: 'checkbox',
    checked: initial.isPublic,
  });
  const textarea = Object.assign(document.createElement('textarea'), {
    rows: 10,
    value: initial.content,
  });
  textarea.setAttribute('aria-label', options.textLabel ?? 'Text');
  const notes = make('ul', 'description-notes status-text');
  const visibility = make('div', '');
  const checkbox = make('label', 'field-row');
  checkbox.append(isPublic, options.visibilityLabel ?? 'Players can read this');
  visibility.append(checkbox);
  if (options.visibilityNote) {
    const note = make('p', 'field-note', options.visibilityNote);
    note.id = `visibility-note-${++visibilityNotes}`;
    isPublic.setAttribute('aria-describedby', note.id);
    visibility.append(note);
  }

  const element = make('div', 'info-fields');
  element.append(
    field(options.titleLabel ?? 'Title', title),
    ...(options.showType ? [field('Type', type)] : []),
    field(options.textLabel ?? 'Text', textarea),
    notes,
    ...(options.showVisibility ? [visibility] : []),
  );
  const editor = createEditor({
    textarea,
    render: async (source) => {
      const [rendered] = await renderer([source]);
      notes.replaceChildren(...(rendered?.notes ?? []).map((note) => make('li', '', note)));
      return rendered?.html ?? '';
    },
  });

  const read = (): InformationDraft => ({
    title: title.value.trim(),
    type: type.value.trim() || initial.type,
    isPublic: isPublic.checked,
    content: textarea.value,
  });
  return {
    element,
    title,
    read,
    changed: () => JSON.stringify(read()) !== JSON.stringify(initial),
    destroy: () => editor.destroy(),
  };
}

/** What went wrong with a save, as the author should read it. */
export function saveError(e: unknown): string {
  if (e instanceof ApiError && e.status === 412) return STALE;
  return e instanceof Error ? e.message : String(e);
}

/** `infoFields` in a form of its own, with Save, Cancel, and a line saying what happened. */
export function infoForm(
  options: FieldsOptions & {
    onSubmit: (draft: InformationDraft) => Promise<void>;
    onClose: () => void;
  },
): HTMLFormElement {
  const fields = infoFields(options);
  const status = make('p', 'status-text');
  status.setAttribute('role', 'status');
  const save = make('button', '', 'Save');
  save.type = 'submit';
  const cancel = make('button', 'btn btn-secondary', 'Cancel');
  cancel.type = 'button';
  const buttons = make('div', 'field-row');
  buttons.append(save, cancel);

  const form = make('form', 'description-form');
  form.append(fields.element, buttons, status);
  const close = () => {
    fields.destroy();
    options.onClose();
  };
  cancel.addEventListener('click', () => {
    if (fields.changed() && !window.confirm('Discard your changes?')) return;
    close();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    save.disabled = true;
    status.classList.remove('error-text');
    status.textContent = 'Saving…';
    try {
      await options.onSubmit(fields.read());
      close();
    } catch (e) {
      status.classList.add('error-text');
      status.textContent = saveError(e);
    } finally {
      save.disabled = false;
    }
  });
  window.setTimeout(() => fields.title.focus(), 0);
  return form;
}

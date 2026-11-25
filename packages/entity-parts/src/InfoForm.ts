// The fields a piece of information is written with (ADR 0112): its title, type, who can read
// it, and its LorenzoScript text in the editor (ADR 0106), with notes on links readers won't be
// able to follow, in a form of its own with Save, Cancel and a line saying what happened.

import { LorenzoApiError } from '@lorenzo/api-client';
import { type BundleReceipt, renderBundleEditor } from '@lorenzo/information-editor';
import { renderDescriptionEditor } from './DescriptionEditor';
import type { Information, InformationDraft } from './information';
import { errorMessage } from './internal/errorMessage';
import { say } from './internal/statusLine';
import { cloneTemplate, requiredIn } from './internal/template';
import type { Renderer } from './text';

export type InfoFormOptions = {
  initial: InformationDraft;
  information?: Information;
  renderer: Renderer;
  // "Title" unless given; a description's is "Display title", the item's shown name.
  titleLabel?: string;
  textLabel?: string;
  showType?: boolean;
  showVisibility?: boolean;
  // The public checkbox's label, "Players can read this" unless given.
  visibilityLabel?: string;
  // Said under the checkbox, such as who can read it otherwise.
  visibilityNote?: string;
  // More fields under the text, such as a note's audience (ADR 0271).
  extra?: HTMLElement;
  onSubmit: (draft: InformationDraft) => Promise<void>;
  onClose: () => void;
};

export type InfoFormDeps = {
  // How a protected picture is read, with the app's token.
  blobUrl(url: string): Promise<string>;
};

const STALE =
  'Someone changed this after you opened it. Copy your text, reload the page, and make your changes again.';

let visibilityNotes = 0;

const required = requiredIn('Info form');

// What went wrong with a save, as the author should read it.
export function saveError(error: unknown): string {
  if (error instanceof LorenzoApiError && error.status === 412) return STALE;

  return errorMessage(error);
}

// `templates` is whatever contains <InfoForm />.
export function renderInfoForm(
  deps: InfoFormDeps,
  templates: ParentNode,
  options: InfoFormOptions,
): HTMLFormElement {
  const { initial } = options;
  const template = required<HTMLTemplateElement>(templates, '[data-info-form-template]');
  const form = cloneTemplate<HTMLFormElement>(template, 'form');

  const title = required<HTMLInputElement>(form, '[data-title]');
  const type = required<HTMLInputElement>(form, '[data-type]');
  const isPublic = required<HTMLInputElement>(form, '[data-public]');
  const status = required<HTMLElement>(form, '[data-status]');

  required<HTMLElement>(form, '[data-title-label]').textContent = options.titleLabel ?? 'Title';
  required<HTMLElement>(form, '[data-type-field]').hidden = !options.showType;
  required<HTMLElement>(form, '[data-visibility]').hidden = !options.showVisibility;
  const extra = required<HTMLElement>(form, '[data-extra]');

  extra.hidden = !options.extra;
  if (options.extra) extra.append(options.extra);
  required<HTMLElement>(form, '[data-visibility-label]').textContent =
    options.visibilityLabel ?? 'Players can read this';

  title.value = initial.title;
  type.value = initial.type;
  isPublic.checked = initial.isPublic;

  if (options.visibilityNote) {
    const note = required<HTMLElement>(form, '[data-visibility-note]');

    note.hidden = false;
    note.textContent = options.visibilityNote;
    note.id = `visibility-note-${++visibilityNotes}`;
    isPublic.setAttribute('aria-describedby', note.id);
  }

  const field = required<HTMLElement>(form, '[data-description-editor]');
  const prototype = field.cloneNode(true) as HTMLElement;
  const editor = renderBundleEditor({
    initial: options.information?.payloads,
    content: initial.content,
    textLabel: options.textLabel ?? 'Text',
    loadFile: (payload) => deps.blobUrl(payload.url),
    createTextEditor: (host, label, content) => {
      const mount = prototype.cloneNode(true) as HTMLElement;
      host.append(mount);
      return renderDescriptionEditor(mount, { renderer: options.renderer, label, content });
    },
  });
  field.replaceWith(editor.element);
  const receipt: BundleReceipt = {
    id: options.information?.id ?? crypto.randomUUID(),
    information: options.information,
  };

  const read = (): InformationDraft => ({
    title: title.value.trim(),
    type: type.value.trim() || initial.type,
    isPublic: isPublic.checked,
    content: editor.read().find((p) => p.kind === 'description')?.content ?? '',
    payloads: editor.read(),
    receipt,
  });

  const fingerprint = () => JSON.stringify({ ...read(), receipt: undefined });
  const started = fingerprint();

  function close() {
    editor.destroy();
    options.onClose();
  }

  required<HTMLButtonElement>(form, '[data-cancel]').addEventListener('click', () => {
    if (fingerprint() !== started && !window.confirm('Discard your changes?')) {
      return;
    }

    close();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const controls = Array.from(
      form.querySelectorAll<
        HTMLInputElement | HTMLTextAreaElement | HTMLButtonElement | HTMLSelectElement
      >('input, textarea, button, select'),
    );
    const disabled = controls.map((control) => control.disabled);
    for (const control of controls) control.disabled = true;
    say(status, 'Saving…');

    try {
      await editor.ready();
      await options.onSubmit(read());
      close();
    } catch (error) {
      say(status, saveError(error), true);
    } finally {
      controls.forEach((control, index) => {
        control.disabled = disabled[index] ?? false;
      });
    }
  });

  window.setTimeout(() => title.focus(), 0);

  return form;
}

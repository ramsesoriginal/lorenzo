// The fields a piece of information is written with (ADR 0112): its title, type, who can read
// it, and its LorenzoScript text in the editor (ADR 0106), with notes on links readers won't be
// able to follow, in a form of its own with Save, Cancel and a line saying what happened.

import { LorenzoApiError } from '../../lib/api';
import type { Renderer } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import type { InformationDraft } from '../../lib/information';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import { renderDescriptionEditor } from '../DescriptionEditor/renderer';

export type InfoFormOptions = {
  initial: InformationDraft;
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
  onSubmit: (draft: InformationDraft) => Promise<void>;
  onClose: () => void;
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
export function renderInfoForm(templates: ParentNode, options: InfoFormOptions): HTMLFormElement {
  const { initial } = options;
  const template = required<HTMLTemplateElement>(templates, '[data-info-form-template]');
  const form = cloneTemplate<HTMLFormElement>(template, 'form');

  const title = required<HTMLInputElement>(form, '[data-title]');
  const type = required<HTMLInputElement>(form, '[data-type]');
  const isPublic = required<HTMLInputElement>(form, '[data-public]');
  const save = required<HTMLButtonElement>(form, '[data-save]');
  const status = required<HTMLElement>(form, '[data-status]');

  required<HTMLElement>(form, '[data-title-label]').textContent = options.titleLabel ?? 'Title';
  required<HTMLElement>(form, '[data-type-field]').hidden = !options.showType;
  required<HTMLElement>(form, '[data-visibility]').hidden = !options.showVisibility;
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

  const editor = renderDescriptionEditor(form, {
    renderer: options.renderer,
    label: options.textLabel ?? 'Text',
    content: initial.content,
  });

  const read = (): InformationDraft => ({
    title: title.value.trim(),
    type: type.value.trim() || initial.type,
    isPublic: isPublic.checked,
    content: editor.value(),
  });

  function close() {
    editor.destroy();
    options.onClose();
  }

  required<HTMLButtonElement>(form, '[data-cancel]').addEventListener('click', () => {
    if (
      JSON.stringify(read()) !== JSON.stringify(initial) &&
      !window.confirm('Discard your changes?')
    ) {
      return;
    }

    close();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    save.disabled = true;
    say(status, 'Saving…');

    try {
      await options.onSubmit(read());
      close();
    } catch (error) {
      say(status, saveError(error), true);
    } finally {
      save.disabled = false;
    }
  });

  window.setTimeout(() => title.focus(), 0);

  return form;
}

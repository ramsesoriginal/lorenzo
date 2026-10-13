// LorenzoScript text (ADR 0106) in the editor, with notes on links readers won't be able to
// follow, under it.

import { createEditor } from '@lorenzo/lorenzoscript-editor';
import type { Renderer } from '../../lib/descriptions';
import { requiredIn } from '../../lib/template';

export type DescriptionEditorOptions = {
  renderer: Renderer;
  label: string;
  // What it starts as.
  content: string;
};

export type RenderedDescriptionEditor = {
  // What's been written so far.
  value(): string;
  focus(): void;
  destroy(): void;
};

const required = requiredIn('Description editor');

// `root` is the <DescriptionEditor /> field, or whatever contains one.
export function renderDescriptionEditor(
  root: HTMLElement,
  options: DescriptionEditorOptions,
): RenderedDescriptionEditor {
  const field = root.matches('[data-description-editor]')
    ? root
    : required<HTMLElement>(root, '[data-description-editor]');
  const text = required<HTMLTextAreaElement>(field, '[data-text]');
  const notes = required<HTMLUListElement>(field, '[data-notes]');

  required<HTMLElement>(field, '[data-label]').textContent = options.label;
  text.setAttribute('aria-label', options.label);
  text.value = options.content;

  const editor = createEditor({
    textarea: text,

    render: async (source) => {
      const [rendered] = await options.renderer([source]);

      notes.replaceChildren(
        ...(rendered?.notes ?? []).map((note) => {
          const item = document.createElement('li');

          item.textContent = note;

          return item;
        }),
      );

      return rendered?.html ?? '';
    },
  });

  return {
    value: () => text.value,
    focus: () => text.focus(),
    destroy: () => editor.destroy(),
  };
}

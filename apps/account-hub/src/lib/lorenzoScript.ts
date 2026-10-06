// A description in account-hub is LorenzoScript (RFC 0027): shown rendered, and written in the
// editor. A tenant's or a campaign's description has no entities of its own to link to, so both are
// done without an entity resolver.
import { parse, render } from '@lorenzo/lorenzoscript';
import { createEditor, DEFAULT_TOOLBAR, type Editor } from '@lorenzo/lorenzoscript-editor';

// Puts `text` in `element` (an `.ls-content`), rendered, or hides it when there is none. The HTML
// the renderer makes is safe by construction.
export function showLorenzoScript(element: HTMLElement, text: string): void {
  const written = text.trim() !== '';

  element.innerHTML = written ? render(parse(text)) : '';
  element.hidden = !written;
}

// The editor's whole toolbar without entity links and images, which have nothing to point at here.
const TOOLBAR = DEFAULT_TOOLBAR.filter((tool) => tool !== 'entity' && tool !== 'image');

// The editor on a description's textarea, whose value is already set so the preview starts from
// the text.
export function createDescriptionEditor(textarea: HTMLTextAreaElement): Editor {
  // A copy of a <template> belongs to an inert document until it is in the page, and the editor
  // keeps the document of its textarea (and undoes through it): bring it into this one first.
  if (!textarea.isConnected) document.adoptNode(textarea.getRootNode());

  return createEditor({ textarea, toolbar: TOOLBAR });
}

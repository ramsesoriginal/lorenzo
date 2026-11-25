// The parts of an entry's page that Beings and Inventory both draw (ADR 0526). What an app brings
// (its client) is given once, by createEntityParts; the Astro templates are exported beside this
// (`@lorenzo/entity-parts/TagEditor.astro`).
import type { LorenzoClient } from '@lorenzo/api-client';
import { renderTagEditor, type TagEditorOptions } from './TagEditor';

export {
  type DescriptionEditorOptions,
  type RenderedDescriptionEditor,
  renderDescriptionEditor,
} from './DescriptionEditor';
export type { RenderedTagEditor, TagEditorOptions } from './TagEditor';
export { type Definition, STATES, type State, setTag, tagDefinitions, tagState } from './tags';
export type { Rendered, Renderer } from './text';

/** What an app brings to the parts that read and write through the API. */
export type EntityPartsContext = {
  // The app's own client, so it keeps its token and base URL.
  client: LorenzoClient;
};

export function createEntityParts(context: EntityPartsContext) {
  const { client } = context;

  return {
    renderTagEditor: (options: TagEditorOptions) => renderTagEditor(client, options),
  };
}

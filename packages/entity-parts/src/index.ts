// The parts of an entry's page that Beings and Inventory both draw (ADR 0526). What an app brings
// (its client, how a protected picture is read, its languages and its words) is given once, by
// createEntityParts; the Astro templates are exported beside this
// (`@lorenzo/entity-parts/TagEditor.astro`).
import type { LorenzoClient } from '@lorenzo/api-client';
import {
  type DescriptionEditOptions,
  type RenderedDescriptionEdit,
  renderDescriptionEdit,
} from './DescriptionEdit';
import { type InfoFormOptions, renderInfoForm } from './InfoForm';
import { informationApi } from './information';
import { renderSlugEditor, type SlugEditorOptions } from './SlugEditor';
import { type SlugWords, slugsApi } from './slugs';
import { renderTagEditor, type TagEditorOptions } from './TagEditor';

export type {
  DescribedEntry,
  DescriptionEditOptions,
  RenderedDescriptionEdit,
} from './DescriptionEdit';
export {
  type DescriptionEditorOptions,
  type RenderedDescriptionEditor,
  renderDescriptionEditor,
} from './DescriptionEditor';
export { type InfoFormOptions, saveError } from './InfoForm';
export {
  descriptionDraft,
  type Information,
  type InformationDraft,
  type TextPayload,
  textOf,
} from './information';
export type { RenderedSlugEditor, SlugEditorOptions } from './SlugEditor';
export { type SlugKind, type SlugWords, slugCandidates } from './slugs';
export type { RenderedTagEditor, TagEditorOptions } from './TagEditor';
export { type Definition, STATES, type State, setTag, tagDefinitions, tagState } from './tags';
export { at, type Rendered, type Renderer } from './text';

/** What an app brings to the parts that read and write through the API. */
export type EntityPartsContext = {
  // The app's own client, so it keeps its token and base URL.
  client: LorenzoClient;
  // How a protected picture is read, with the app's token.
  blobUrl(url: string): Promise<string>;
  // The viewer's languages, for a new piece of information.
  locales(): Promise<string[]>;
  words: SlugWords & {
    // The label of a description's title: "Display title", "Heading".
    descriptionTitle: string;
  };
};

export function createEntityParts(context: EntityPartsContext) {
  const { client, blobUrl, locales, words } = context;
  const information = informationApi(client, locales);
  const slugs = slugsApi(client, words);

  return {
    // What the app imports for reading and writing, by the names it had.
    information,
    slugs,

    renderTagEditor: (options: TagEditorOptions) => renderTagEditor(client, options),
    renderSlugEditor: (options: SlugEditorOptions) =>
      renderSlugEditor({ client, slugs, noun: words.slug }, options),
    renderInfoForm: (templates: ParentNode, options: InfoFormOptions) =>
      renderInfoForm({ blobUrl }, templates, options),
    renderDescriptionEdit: (options: DescriptionEditOptions): RenderedDescriptionEdit =>
      renderDescriptionEdit(
        { client, information, blobUrl, titleLabel: words.descriptionTitle },
        options,
      ),
  };
}

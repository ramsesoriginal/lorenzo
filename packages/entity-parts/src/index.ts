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
import { type FactPageDeps, renderFactPage } from './FactPage';
import { type FactsDeps, renderFactsAbout } from './Facts';
import { type InfoFormOptions, renderInfoForm } from './InfoForm';
import { informationApi } from './information';
import { type LibraryListDeps, renderLibraryList } from './LibraryList';
import { renderSlugEditor, type SlugEditorOptions } from './SlugEditor';
import { type SlugWords, slugsApi } from './slugs';
import { renderTagEditor, type TagEditorOptions } from './TagEditor';
import type { Renderer } from './text';

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
export type { RenderedLibraryList } from './LibraryList';
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
  // Draws texts into a block with the app's own links (ADR 0240).
  showDescriptions: FactPageDeps['showDescriptions'];
  // Where a Fact's own page is.
  factPageHref: FactsDeps['factPageHref'];
  // Where "Where it appears" for a Fact is, for an app that has such a page.
  appearsHref?: FactPageDeps['appearsHref'];
  libraries: LibraryListDeps;
  words: SlugWords & {
    // The label of a description's title: "Display title", "Heading".
    descriptionTitle: string;
    // "Facts about this item", "Facts about this being".
    factsHeading: string;
  };
};

export function createEntityParts(context: EntityPartsContext) {
  const { client, blobUrl, locales, words, libraries } = context;
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
    renderFactsAbout: (host: HTMLElement, tenantId: string, entryId: string) =>
      renderFactsAbout(
        { client, factPageHref: context.factPageHref, heading: words.factsHeading },
        host,
        tenantId,
        entryId,
      ),
    renderFactPage: (root: HTMLElement, tenantId: string, id: string, renderer: Renderer) =>
      renderFactPage(
        {
          client,
          blobUrl,
          showDescriptions: context.showDescriptions,
          ...(context.appearsHref ? { appearsHref: context.appearsHref } : {}),
        },
        root,
        tenantId,
        id,
        renderer,
      ),
    renderLibraryList: (root: HTMLElement) => renderLibraryList(libraries, root),
    renderDescriptionEdit: (options: DescriptionEditOptions): RenderedDescriptionEdit =>
      renderDescriptionEdit(
        { client, information, blobUrl, titleLabel: words.descriptionTitle },
        options,
      ),
  };
}

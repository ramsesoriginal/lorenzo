// The parts of an entry's page that this app shares with the other apps that draw them
// (packages/entity-parts, ADR 0526), bound to this app's client, pictures, languages and words, so the
// rest of the app imports them from here.
import { createEntityParts } from '@lorenzo/entity-parts';
import { blobUrl, client } from './api';
import { viewerLocales } from './me';

export const {
  information,
  slugs,
  renderTagEditor,
  renderSlugEditor,
  renderInfoForm,
  renderDescriptionEdit,
} = createEntityParts({
  client,
  blobUrl,
  locales: viewerLocales,
  words: {
    slug: 'slug',
    slugTaken: (slug) => `Another entity already uses “${slug}”.`,
    descriptionTitle: 'Display title',
  },
});

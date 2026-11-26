// The parts of an entry's page that this app shares with the other apps that draw them
// (packages/entity-parts, ADR 0526), bound to this app's client, pictures, languages and words, so the
// rest of the app imports them from here.
import { createEntityParts } from '@lorenzo/entity-parts';
import { blobUrl, client } from './api';
import { showDescriptions } from './descriptions';
import { factPageHref } from './entityLinks';
import { rememberTenant } from './lastTenant';
import { viewerLocales } from './me';
import { listTenants } from './tenants';

export const {
  information,
  slugs,
  renderTagEditor,
  renderSlugEditor,
  renderInfoForm,
  renderDescriptionEdit,
  renderFactsAbout,
  renderFactPage,
  renderLibraryList,
} = createEntityParts({
  client,
  blobUrl,
  locales: viewerLocales,
  showDescriptions,
  factPageHref,
  appearsHref: (tenantId, id) =>
    `/appears/?tenant=${encodeURIComponent(new URLSearchParams(location.search).get('tenant') ?? tenantId)}&id=${id}`,
  libraries: {
    list: listTenants,
    remember: rememberTenant,
    href: (tenantId) => `/beings/?tenant=${tenantId}`,
  },
  words: {
    slug: 'link name',
    slugTaken: (slug) => `Another entry already uses the link name “${slug}”.`,
    factsHeading: 'Facts about this being',
    descriptionTitle: 'Heading',
  },
});

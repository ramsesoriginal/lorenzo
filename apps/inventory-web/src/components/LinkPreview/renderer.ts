// The card a link to an entity opens when it is hovered, focused or tapped (ADR 0264), for every
// `.ls-content` on the page: the package's card (ADR 0349), with the links of rendered texts as its
// triggers and the app's API client and picture loader behind it.
import { installEntryPreview } from '@lorenzo/entry-preview';
import { blobUrl } from '../../lib/api';
import { previewTarget } from '../../lib/linkPreview';
import { loadCard } from '../../lib/previewCards';

export function installLinkPreviews(): void {
  installEntryPreview({
    selector: '.ls-content a.ls-entity',
    targetOf: (link) => previewTarget(link.getAttribute('href')),
    loadCard,
    loadPicture: blobUrl,
  });
}

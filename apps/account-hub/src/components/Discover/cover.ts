// A repository's cover, or a quiet placeholder (a dashed frame saying "Cover") where it has none. The cover is
// fetched with the token and shown from a blob (lib/discoverApi.ts); the frame stays until the
// picture has arrived, and for good where it never does.

import { coverUrl } from '../../lib/discoverApi';

export function showCover(
  img: HTMLImageElement,
  placeholder: HTMLElement | null,
  repository: { id: string; name: string; has_cover: boolean },
  isCurrent: () => boolean,
): void {
  if (placeholder) {
    placeholder.textContent = 'Cover';
    placeholder.hidden = false;
  }

  img.hidden = true;

  if (!repository.has_cover) return;

  void coverUrl(repository.id)
    .then((url) => {
      if (!isCurrent()) return;

      img.src = url;
      img.hidden = false;
      if (placeholder) placeholder.hidden = true;
    })
    .catch(() => {
      // The placeholder stands.
    });
}

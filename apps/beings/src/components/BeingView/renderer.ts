// What a being's page says about it (ADR 0271): its picture, its description as LorenzoScript. Read-only;
// the editors are separate, and the numbers and tags are the stat band's (RFC 0043).

import { blobUrl } from '../../lib/api';
import { descriptionOf, pictureOf } from '../../lib/being';
import { type Renderer, showDescriptions } from '../../lib/descriptions';
import { requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

/** The letters standing in for a being with no picture: the first of its first two words. */
export const initialsOf = (name: string): string =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');

export type BeingViewOptions = { renderer: Renderer };

export type RenderedBeingView = {
  /** Shows `entity`, replacing what was shown. */
  show(entity: EntityDetail): void;
};

const required = requiredIn('Being view');

// `root` is the being's page, where the picture, the description and the tags are found.
export function renderBeingView(root: HTMLElement, options: BeingViewOptions): RenderedBeingView {
  const figure = required<HTMLElement>(root, '[data-picture-figure]');
  const picture = required<HTMLImageElement>(root, '[data-picture]');
  const portrait = required<HTMLElement>(root, '[data-portrait]');
  const description = required<HTMLElement>(root, '[data-description]');
  const nothing = required<HTMLElement>(root, '[data-nothing]');

  // The picture shown, so an unrelated change does not fetch it again.
  let pictureId: string | null = null;

  return {
    show(entity) {
      const text = descriptionOf(entity);
      const main = pictureOf(entity);

      if (main?.kind !== 'picture') {
        pictureId = null;
        figure.hidden = true;
        portrait.hidden = false;
      } else if (main.id !== pictureId || main.updated_at !== picture.dataset.version) {
        pictureId = main.id;
        picture.dataset.version = main.updated_at;
        blobUrl(
          `${main.url}${main.url.includes('?') ? '&' : '?'}v=${encodeURIComponent(main.updated_at)}`,
        ).then(
          (src) => {
            picture.src = src;
            figure.hidden = false;
            portrait.hidden = true;
          },
          () => {
            figure.hidden = true;
            portrait.hidden = false;
          },
        );
      }

      picture.alt = `Picture of ${entity.name}`;
      portrait.textContent = initialsOf(entity.name);

      void showDescriptions(description, options.renderer, text ? [{ text, home: entity.id }] : []);

      nothing.hidden = Boolean(text) || main !== undefined;
    },
  };
}

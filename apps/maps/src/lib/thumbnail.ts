// The small drawing on a card of the gallery (MP1): the renderer paints the Map as SVG from the
// placements this reader may read, so nothing hidden is in it (D24). It is decoration, so nothing in
// it can be focused or read out: the card's name and words carry the meaning.
import {
  DEFAULT_GROUPS,
  layout,
  type MapModel,
  paintSvg,
  sheetCentre,
  type Theme,
} from '@lorenzo/map-renderer';

export const THUMB = { width: 240, height: 150 } as const;

export function drawThumbnail(host: HTMLElement, model: MapModel, theme: Theme, iconBase: string) {
  const scene = layout(
    model,
    {
      viewport: THUMB,
      zoom: 1,
      centre: sheetCentre(model.system),
      groups: { ...DEFAULT_GROUPS, names: false, grid: false, layers: false },
      selection: null,
      iconBase,
    },
    theme,
  );
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  paintSvg(scene, svg, { role: 'group', idPrefix: 'thumb' });
  svg.removeAttribute('role');
  for (const mark of svg.querySelectorAll('.m-mark'))
    for (const name of ['tabindex', 'role', 'aria-label', 'aria-pressed'])
      mark.removeAttribute(name);
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  host.replaceChildren(svg);
}

/** Runs the jobs it is given a few at a time, so a long gallery does not ask for everything at once. */
export function queue(width = 3) {
  const waiting: (() => Promise<void>)[] = [];
  let running = 0;
  const next = () => {
    while (running < width && waiting.length > 0) {
      const job = waiting.shift();
      if (!job) return;
      running += 1;
      void job()
        .catch(() => {})
        .finally(() => {
          running -= 1;
          next();
        });
    }
  };

  return (job: () => Promise<void>) => {
    waiting.push(job);
    next();
  };
}

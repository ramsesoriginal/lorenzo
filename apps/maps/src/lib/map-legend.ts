// The legend of a Map (ADR 0352): what its roles look like in the theme it is drawn with. The
// renderer makes each swatch; this only paints them beside the role's name.
import { legend, type MapModel, paintSvg, SWATCH, type Theme } from '@lorenzo/map-renderer';
import { BRANDING_CSS_URL } from './config';
import { el } from './dom';

export function createLegend() {
  const root = el('details', '', 'map-legend');
  const summary = el('summary', 'Legend', 'map-legend-title');
  const list = el('ul', '', 'map-legend-list');
  root.append(summary, list);

  function update(model: MapModel, theme: Theme) {
    const items = legend(model, theme, { iconBase: BRANDING_CSS_URL });
    root.hidden = items.length === 0;
    list.replaceChildren(
      ...items.map((item) => {
        const row = el('li', '', 'map-legend-item');
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'm-svg map-swatch');
        svg.setAttribute('width', String(SWATCH.width));
        svg.setAttribute('height', String(SWATCH.height));
        paintSvg(item.swatch, svg, { role: 'group', idPrefix: `legend-${item.key}` });
        // The words beside it name the swatch; the picture is decoration.
        svg.setAttribute('aria-hidden', 'true');
        svg.removeAttribute('role');
        for (const mark of svg.querySelectorAll('[tabindex]')) {
          mark.removeAttribute('tabindex');
          mark.removeAttribute('role');
          mark.removeAttribute('aria-label');
          mark.removeAttribute('aria-pressed');
        }
        row.append(svg, el('span', item.label));
        return row;
      }),
    );
  }

  return { root, update };
}

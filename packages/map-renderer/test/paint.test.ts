import { describe, expect, it } from 'vitest';
import { DEFAULT_GROUPS, iconHref, layout, paintSvg, sceneToSvg, sceneTree } from '../src';
import { type FakeElement, fakeSvg, fakeToSvg } from './fakeDom';
import { model, place, system, view } from './fixtures';

const small = view({ viewport: { width: 500, height: 320 } });
const options = { title: 'Map of Hollowmere', description: 'Six places.', idPrefix: 'm1' };

function walk(el: FakeElement, visit: (e: FakeElement) => void): void {
  visit(el);

  for (const kid of el.kids) walk(kid, visit);
}

describe('sceneToSvg', () => {
  it('writes the small map as these exact bytes', () => {
    const svg = sceneToSvg(layout(model, small), { ...options, iconBase: '/brand' });

    expect(svg).toMatchInlineSnapshot(
      `"<svg xmlns="http://www.w3.org/2000/svg" class="m-svg" viewBox="0 0 500 320" data-theme="default" role="img" aria-labelledby="m1-title m1-desc"><title id="m1-title">Map of Hollowmere</title><desc id="m1-desc">Six places.</desc><rect class="m-land" x="0" y="0" width="500" height="320"/><g class="m-mark" tabindex="0" role="button" aria-label="The Rushwater, water" aria-pressed="false" data-entry="river"><path class="m-river-b" d="M 345 -60 L 365 30 L 395 135 L 360 320" stroke-width="23"/><path class="m-river" d="M 345 -60 L 365 30 L 395 135 L 360 320" stroke-width="20"/></g><g class="m-mark" tabindex="0" role="button" aria-label="Hollowmere, built-up area" aria-pressed="false" data-entry="town"><path class="m-region m-town" d="M 150 100 L 350 100 L 350 250 L 150 250 Z M 225 150 L 275 150 L 275 200 L 225 200 Z" stroke-width="2" stroke-dasharray="6 5" fill-rule="evenodd"/></g><g class="m-mark" tabindex="0" role="button" aria-label="The Mill Road, route" aria-pressed="false" data-entry="road"><path class="m-road-l m-round" d="M 50 50 L 200 150" stroke-width="3" stroke-dasharray="1 7"/></g><g class="m-mark" tabindex="0" role="button" aria-label="Shrine of the Lantern" aria-pressed="false" data-entry="shrine"><circle class="m-pinbg" cx="275" cy="225" r="15"/><use class="m-ico" href="/brand/icons.svg#icon-kind-location" x="265" y="215" width="20" height="20"/><text class="m-lbl" x="293" y="229.5">Shrine of the Lantern</text></g><g class="m-mark" tabindex="0" role="button" aria-label="The Gilded Stag" aria-pressed="false" data-entry="stag"><circle class="m-pinbg" cx="200" cy="150" r="15"/><use class="m-ico" href="/brand/icons.svg#icon-kind-location" x="190" y="140" width="20" height="20"/><text class="m-lbl" x="218" y="154.5">The Gilded Stag</text></g><g class="m-mark" tabindex="0" role="button" aria-label="Mara Quill, MQ, presence" aria-pressed="false" data-entry="mara"><circle class="m-ppl" cx="205" cy="165" r="12"/><text class="m-ppl-t" x="205" y="168.75" text-anchor="middle">MQ</text></g></svg>"`,
    );
  });

  it('writes a selected mark with its class and aria-pressed', () => {
    const svg = sceneToSvg(layout(model, { ...small, selection: 'stag' }));

    expect(svg).toContain(
      '<g class="m-mark" tabindex="0" role="button" aria-label="The Gilded Stag"',
    );
    expect(svg).toContain('aria-pressed="true" data-entry="stag"><circle class="m-pinbg m-on"');
    expect(svg).toContain('aria-pressed="false" data-entry="shrine">');
  });

  it('escapes what a person wrote, in text and in attributes', () => {
    const nasty = place(
      'x',
      '<img src=x onerror="alert(1)"> & co',
      [],
      [{ shape: 'point', at: [10, 10] }],
    );
    const svg = sceneToSvg(layout({ system, placements: [nasty] }, small), {
      title: 'A "quoted" <title>',
    });

    expect(svg).not.toContain('<img');
    expect(svg).toContain('aria-label="&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; co"');
    expect(svg).toContain('>&lt;img src=x onerror="alert(1)"&gt; &amp; co</text>');
    expect(svg).toContain('<title id="map-title">A "quoted" &lt;title&gt;</title>');
  });

  it('points an icon at the atlas, with a base or inline', () => {
    expect(iconHref('', 'kind-location')).toBe('#icon-kind-location');
    expect(iconHref('/brand', 'kind-location')).toBe('/brand/icons.svg#icon-kind-location');
    expect(sceneToSvg(layout(model, small), { iconBase: '/b' })).toContain(
      'href="/b/icons.svg#icon-kind-location"',
    );
    expect(sceneToSvg(layout(model, { ...small, iconBase: '/from-view' }))).toContain(
      'href="/from-view/icons.svg#icon-kind-location"',
    );
  });

  it('can name the drawing a group instead of an image', () => {
    const svg = sceneToSvg(layout(model, small), { role: 'group' });

    expect(svg).toContain('role="group"');
    expect(svg).not.toContain('role="img"');
  });
});

describe('paintSvg', () => {
  it('makes the same element tree sceneToSvg writes', () => {
    const scene = layout(model, small);
    const { svg, el } = fakeSvg();

    paintSvg(scene, svg, options);

    expect(fakeToSvg(el)).toBe(sceneToSvg(scene, options));
  });

  it('sets viewBox, role img, a title and a description, and a focusable button per placement', () => {
    const { svg, el } = fakeSvg();

    paintSvg(layout(model, small), svg, options);

    expect(el.getAttribute('viewBox')).toBe('0 0 500 320');
    expect(el.getAttribute('role')).toBe('img');
    expect(el.getAttribute('aria-labelledby')).toBe('m1-title m1-desc');
    expect(el.kids[0]?.tagName).toBe('title');
    expect(el.kids[0]?.textContent).toBe('Map of Hollowmere');
    expect(el.kids[1]?.textContent).toBe('Six places.');

    const buttons = el.kids.filter((k) => k.tagName === 'g');

    expect(buttons.map((g) => g.getAttribute('data-entry'))).toEqual([
      'river',
      'town',
      'road',
      'shrine',
      'stag',
      'mara',
    ]);

    for (const g of buttons) {
      expect(g.getAttribute('tabindex')).toBe('0');
      expect(g.getAttribute('role')).toBe('button');
      expect(g.getAttribute('aria-label')).toBeTruthy();
    }

    expect(buttons[0]?.getAttribute('aria-label')).toBe('The Rushwater, water');
    expect(buttons[5]?.getAttribute('aria-label')).toBe('Mara Quill, MQ, presence');
    expect(buttons[4]?.getAttribute('aria-label')).toBe('The Gilded Stag');
  });

  it('draws a pin with a use of the atlas icon', () => {
    const { svg, el } = fakeSvg();

    paintSvg(layout(model, small), svg, { ...options, iconBase: '/brand' });

    const uses: FakeElement[] = [];

    walk(el, (e) => {
      if (e.tagName === 'use') uses.push(e);
    });

    expect(uses).toHaveLength(2);
    expect(uses[0]?.getAttribute('href')).toBe('/brand/icons.svg#icon-kind-location');
    expect(uses[0]?.getAttribute('width')).toBe('20');
  });

  it('writes names only as text, never as markup', () => {
    const { svg, el } = fakeSvg();
    const nasty = place('x', '<script>alert(1)</script>', [], [{ shape: 'point', at: [10, 10] }]);

    // The fake throws if innerHTML is read or set, so this passing says it never was.
    paintSvg(layout({ system, placements: [nasty] }, small), svg, options);

    const texts: FakeElement[] = [];

    walk(el, (e) => {
      if (e.tagName === 'text') texts.push(e);
    });

    expect(texts.map((t) => t.textContent)).toEqual(['<script>alert(1)</script>']);
    expect(el.kids.some((k) => k.tagName === 'script')).toBe(false);
  });

  it('updates in place: a pan keeps the very same elements', () => {
    const { svg, el } = fakeSvg();

    paintSvg(layout(model, small), svg, options);

    const before = [...el.kids];
    const stag = el.kids.find((k) => k.getAttribute('data-entry') === 'stag');

    paintSvg(layout(model, { ...small, centre: [300, 200] }), svg, options);

    expect(el.kids).toHaveLength(before.length);
    expect(el.kids.every((k, i) => k === before[i])).toBe(true);
    expect(el.kids.find((k) => k.getAttribute('data-entry') === 'stag')).toBe(stag);
    expect(stag?.kids[0]?.getAttribute('cx')).toBe('300');
  });

  it('updates in place: a selection changes classes and aria-pressed and nothing else', () => {
    const { svg, el, doc } = fakeSvg();

    paintSvg(layout(model, small), svg, options);

    const created = doc.created;
    const stag = el.kids.find((k) => k.getAttribute('data-entry') === 'stag');

    paintSvg(layout(model, { ...small, selection: 'stag' }), svg, options);

    expect(doc.created).toBe(created);
    expect(stag?.getAttribute('aria-pressed')).toBe('true');
    expect(stag?.kids[0]?.getAttribute('class')).toBe('m-pinbg m-on');

    paintSvg(layout(model, small), svg, options);

    expect(stag?.getAttribute('aria-pressed')).toBe('false');
    expect(stag?.kids[0]?.getAttribute('class')).toBe('m-pinbg');
  });

  it('drops what a hidden group took, and brings it back', () => {
    const { svg, el } = fakeSvg();
    const scene = layout(model, small);

    paintSvg(scene, svg, options);
    paintSvg(
      layout(model, { ...small, groups: { ...DEFAULT_GROUPS, people: false } }),
      svg,
      options,
    );

    expect(el.kids.some((k) => k.getAttribute('data-entry') === 'mara')).toBe(false);

    paintSvg(scene, svg, options);

    expect(fakeToSvg(el)).toBe(sceneToSvg(scene, options));
  });

  it('keeps what the caller put on the root, and replaces a changed title', () => {
    const { svg, el } = fakeSvg();

    el.setAttribute('tabindex', '0');
    el.setAttribute('data-cursor', 'grab');
    paintSvg(layout(model, small), svg, options);
    paintSvg(layout(model, small), svg, { ...options, title: 'Another title' });

    expect(el.getAttribute('tabindex')).toBe('0');
    expect(el.getAttribute('data-cursor')).toBe('grab');
    expect(el.kids[0]?.textContent).toBe('Another title');
  });

  it('builds a tree without a document at all', () => {
    const tree = sceneTree(layout(model, small), options);

    expect(tree.tag).toBe('svg');
    expect(tree.children[0]?.tag).toBe('title');
  });
});

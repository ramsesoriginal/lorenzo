import { describe, expect, it } from 'vitest';
import { layout, paintSvg } from '../src';
import { type FakeElement, fakeSvg, fakeToSvg } from './fakeDom';
import { model, view } from './fixtures';

const options = { title: 'The family', iconBase: '/brand/icons.svg' };

function walk(el: FakeElement, visit: (e: FakeElement) => void): void {
  visit(el);
  for (const kid of el.kids) walk(kid, visit);
}

function find(el: FakeElement, id: string): FakeElement | undefined {
  let found: FakeElement | undefined;
  walk(el, (e) => {
    if (e.getAttribute('data-id') === id) found = e;
  });
  return found;
}

describe('paintSvg', () => {
  it('names the drawing and makes each node a labelled button', () => {
    const { svg, el } = fakeSvg();
    paintSvg(layout(model, view()), svg, options);
    expect(el.getAttribute('role')).toBe('group');
    expect(el.getAttribute('aria-label')).toBe('The family');
    expect(el.getAttribute('viewBox')).toBe('0 0 640 420');
    const buttons: FakeElement[] = [];
    walk(el, (e) => {
      if (e.getAttribute('role') === 'button') buttons.push(e);
    });
    expect(buttons.map((b) => b.getAttribute('aria-label')).sort()).toEqual(
      model.nodes.map((n) => n.name).sort(),
    );
    for (const b of buttons) expect(b.getAttribute('tabindex')).toBe('0');
  });

  it('writes an icon as a use of the atlas and never parses text', () => {
    const { svg, el } = fakeSvg();
    paintSvg(layout(model, view()), svg, options);
    const use = find(el, 'icon:tomas');
    expect(use?.getAttribute('href')).toBe('/brand/icons.svg#icon-kind-being');
    const evil = { nodes: [{ id: 'x', name: '<img src=x onerror=alert(1)>' }], edges: [] };
    const second = fakeSvg();
    paintSvg(layout(evil, view()), second.svg, options);
    expect(fakeToSvg(second.el)).toContain('&lt;img src=x onerror=alert(1)&gt;');
    expect(fakeToSvg(second.el)).not.toContain('<img');
  });

  it('draws edges with their dash and arrowheads, and marks the selection', () => {
    const { svg, el } = fakeSvg();
    paintSvg(layout(model, view({ selection: { kind: 'node', id: 'wren' } })), svg, options);
    expect(find(el, 'edge:e3')?.getAttribute('stroke-dasharray')).toBe('7 5');
    expect(find(el, 'edge:e1')?.getAttribute('stroke-dasharray')).toBeNull();
    expect(find(el, 'arrow:e1')?.getAttribute('class')).toContain('gr-arrow');
    expect(find(el, 'node:wren')?.getAttribute('class')).toContain('is-selected');
    expect(find(el, 'node:mara')?.getAttribute('class')).not.toContain('is-selected');
    const group = find(el, 'node-group:wren');
    expect(group?.getAttribute('aria-pressed')).toBe('true');
  });

  it('updates in place: the same elements stay, and what is gone is removed', () => {
    const { svg, el, doc } = fakeSvg();
    paintSvg(layout(model, view()), svg, options);
    const before = doc.created;
    const mara = find(el, 'node-group:mara');
    paintSvg(
      layout(model, view({ zoom: 1.5, selection: { kind: 'node', id: 'mara' } })),
      svg,
      options,
    );
    expect(doc.created).toBe(before);
    expect(find(el, 'node-group:mara')).toBe(mara);
    const fewer = { ...model, nodes: model.nodes.filter((n) => n.id !== 'loner') };
    paintSvg(layout(fewer, view()), svg, options);
    expect(find(el, 'node-group:loner')).toBeUndefined();
    expect(find(el, 'node:loner')).toBeUndefined();
  });

  it('writes the same markup twice for the same scene', () => {
    const one = fakeSvg();
    const two = fakeSvg();
    paintSvg(layout(model, view({ layout: 'stress' })), one.svg, options);
    paintSvg(layout(model, view({ layout: 'stress' })), two.svg, options);
    expect(fakeToSvg(one.el)).toBe(fakeToSvg(two.el));
  });
});

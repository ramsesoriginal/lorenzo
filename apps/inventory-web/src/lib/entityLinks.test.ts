import { describe, expect, it } from 'vitest';
import { entityHref, linkNote, type ResolvedSlug } from './entityLinks';

const entity = (kinds: ResolvedSlug['kinds'], name = 'Ashfang'): ResolvedSlug => ({
  slug: 'ashfang',
  entity_id: 'e1',
  name,
  kinds,
});
const link = (hint = '') => ({ kind: 'entity' as const, hint, slug: 'ashfang' });
const image = { kind: 'image' as const, hint: '', slug: 'ashfang' };

describe('entityHref', () => {
  it('opens items and item instances on the item page', () => {
    expect(entityHref('t1', entity(['item']), '')).toBe('/item/?tenant=t1&id=e1');
    expect(entityHref('t1', entity(['item_instance']), '')).toBe('/item/?tenant=t1&id=e1');
  });

  it('opens characters on the board', () => {
    expect(entityHref('t1', entity(['being', 'character']), '')).toBe(
      '/board/?tenant=t1&character=e1',
    );
  });

  it('follows a hint the entity matches', () => {
    // A sentient sword is both an item instance and a character.
    const sword = entity(['item_instance', 'being', 'character']);
    expect(entityHref('t1', sword, '')).toBe('/item/?tenant=t1&id=e1');
    expect(entityHref('t1', sword, 'character')).toBe('/board/?tenant=t1&character=e1');
  });

  it('falls back to the kinds when the hint does not match', () => {
    expect(entityHref('t1', entity(['item']), 'character')).toBe('/item/?tenant=t1&id=e1');
  });

  it('has no page for a plain being', () => {
    expect(entityHref('t1', entity(['being']), 'being')).toBeNull();
    expect(entityHref('t1', entity([]), '')).toBeNull();
  });

  it('routes a backlink, which has kinds but no slug or hint', () => {
    const backlink = { entity_id: 'e2', kinds: ['being' as const, 'character' as const] };
    expect(entityHref('t1', backlink)).toBe('/board/?tenant=t1&character=e2');
  });
});

describe('linkNote', () => {
  it('is silent about links that work', () => {
    expect(linkNote(link(), entity(['item']), false)).toBeNull();
    expect(linkNote(link('item'), entity(['item']), false)).toBeNull();
    expect(linkNote(image, entity(['item']), true)).toBeNull();
  });

  it('names slugs nothing holds', () => {
    expect(linkNote(link(), null, false)).toBe(
      'No entity has the slug “ashfang” yet, so readers see plain text.',
    );
    expect(linkNote(image, null, false)).toBe(
      'No entity has the slug “ashfang” yet, so readers see the alt text.',
    );
  });

  it('names hints the entity does not match, and where the link goes instead', () => {
    expect(linkNote(link('being'), entity(['item_instance']), false)).toBe(
      "Ashfang isn't a being; the link opens its item page instead.",
    );
    expect(linkNote(link('item_instance'), entity(['being', 'character']), false)).toBe(
      "Ashfang isn't an item instance; the link opens the board instead.",
    );
  });

  it('names entities with no page here', () => {
    expect(linkNote(link(), entity(['being']), false)).toBe(
      'Ashfang has no page here, so readers see plain text.',
    );
    expect(linkNote(link('place'), entity(['being']), false)).toBe(
      "Ashfang isn't a place and has no page here, so readers see plain text.",
    );
  });

  it('names entities without a picture', () => {
    expect(linkNote(image, entity(['item']), false)).toBe(
      'Ashfang has no picture, so readers see the alt text.',
    );
  });
});

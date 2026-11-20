import { expect, it } from 'vitest';
import { modernAddress } from './addresses';

const at = (search: string, hash = '', pathname = '/') => modernAddress({ pathname, search, hash });

it('sends an old entry address to Write and an old read view to Read', () => {
  expect(at('?tenant=t&entry=e')).toBe('/write/?tenant=t&entry=e');
  expect(at('?tenant=t&entry=e&view=outline')).toBe('/write/?tenant=t&entry=e&view=outline');
  expect(at('?tenant=t&entry=e&view=read', '#element-1')).toBe('/read/?tenant=t&entry=e#element-1');
});

it('never changes a review address, the shelf, or an address that is already new', () => {
  expect(at('?tenant=t&review=r')).toBeNull();
  expect(at('?tenant=t&entry=e&review=r')).toBeNull();
  expect(at('?tenant=t')).toBeNull();
  expect(at('?tenant=t&entry=e', '', '/write/')).toBeNull();
});

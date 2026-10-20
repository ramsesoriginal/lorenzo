import { describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('./api', () => ({
  client: { GET: get },
  unwrap: async (r: { data: unknown }) => r.data,
  blobUrl: vi.fn(),
}));

import { renderText } from './information';

describe('information references', () => {
  it('links only entries the API resolves for this reader and escapes titles', async () => {
    get.mockResolvedValue({
      data: [{ slug: 'visible', entity_id: 'entry-1', name: '<Secret & name>' }],
    });
    const html = await renderText(
      'library',
      '[[visible]] [[missing]] [[hidden]] <script>alert(1)</script>',
    );
    expect(get).toHaveBeenCalledWith('/tenants/{tenant_id}/entities/resolve', {
      params: { path: { tenant_id: 'library' }, query: { slug: ['visible', 'missing', 'hidden'] } },
    });
    expect(html).toContain('/entry/?tenant=library&amp;id=entry-1');
    expect(html).not.toContain('<script>');
    expect(html).not.toMatch(/href="[^"]*(missing|hidden)/);
    expect(html).toContain('missing');
    expect(html).toContain('hidden');
  });
  it('does not fetch calendar references as dates or external images', async () => {
    get.mockClear();
    const html = await renderText(
      'library',
      'A quiet day. ![outside](https://outside.example/image.png)',
    );
    expect(get).not.toHaveBeenCalled();
    expect(html).not.toContain('<img');
  });
});

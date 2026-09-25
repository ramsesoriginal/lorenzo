import { beforeEach, describe, expect, it, vi } from 'vitest';

// An in-memory API that records every write.
const api = vi.hoisted(() => ({
  PATCH: vi.fn(),
  POST: vi.fn(),
  failInformationPatch: false,
}));
vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));
vi.mock('./me', () => ({ viewerLocales: async () => ['en-GB'] }));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  client: { PATCH: api.PATCH, POST: api.POST },
}));

import {
  descriptionDraft,
  type Information,
  saveDescription,
  updateInformation,
} from './information';

const ok = { data: {}, response: new Response() };
beforeEach(() => {
  api.failInformationPatch = false;
  api.PATCH.mockReset().mockImplementation(async (path: string) =>
    path.includes('/information/') && api.failInformationPatch
      ? { error: { detail: 'Stale.' }, response: new Response(null, { status: 412 }) }
      : ok,
  );
  api.POST.mockReset().mockResolvedValue(ok);
});

const info: Information = {
  id: 'i1',
  title: 'Ashfang',
  type: 'description',
  is_public: true,
  order: 0,
  updated_at: '2026-09-25T10:00:00Z',
  payloads: [
    {
      kind: 'description',
      id: 'p1',
      order: 0,
      updated_at: '2026-09-25T09:00:00Z',
      content: 'It hums.',
      locale: 'en-GB',
    },
  ],
};
const writes = () =>
  api.PATCH.mock.calls.map(([path, { params, body }]) => [path, params.header['if-match'], body]);

describe('updateInformation', () => {
  it('writes only what changed, each with the If-Match of what it changes', async () => {
    await updateInformation('t1', info, { ...descriptionDraft(info, 'x'), content: 'It sings.' });
    await updateInformation('t1', info, { ...descriptionDraft(info, 'x'), title: 'The sword' });

    expect(writes()).toEqual([
      [
        '/tenants/{tenant_id}/payloads/{payload_id}',
        'W/"2026-09-25T09:00:00Z"',
        { content: 'It sings.' },
      ],
      [
        '/tenants/{tenant_id}/information/{information_id}',
        'W/"2026-09-25T10:00:00Z"',
        { title: 'The sword' },
      ],
    ]);
  });

  it('writes nothing when nothing changed', async () => {
    await updateInformation('t1', info, descriptionDraft(info, 'x'));
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it('says the text was saved when only the second write fails', async () => {
    api.failInformationPatch = true;
    const draft = { ...descriptionDraft(info, 'x'), content: 'New.', isPublic: false };

    await expect(updateInformation('t1', info, draft)).rejects.toThrow(
      "The text was saved, but the rest wasn't: Stale.",
    );
    expect(writes().map(([path]) => path)).toEqual([
      '/tenants/{tenant_id}/payloads/{payload_id}',
      '/tenants/{tenant_id}/information/{information_id}',
    ]);
  });

  it('refuses to change text that information without a text payload has none of', async () => {
    const picture = { ...info, payloads: [] };
    await expect(
      updateInformation('t1', picture, { ...descriptionDraft(picture, 'x'), content: 'Hi.' }),
    ).rejects.toThrow('This information has no text to change.');
  });
});

describe('descriptions', () => {
  it('start from the item name when there is none yet (ADR 0112)', () => {
    expect(descriptionDraft(null, 'Ashfang')).toEqual({
      title: 'Ashfang',
      type: 'description',
      isPublic: true,
      content: '',
    });
    expect(descriptionDraft(info, 'Ashfang').content).toBe('It hums.');
  });

  it('are only created when they say something', async () => {
    const blank = descriptionDraft(null, 'Ashfang');
    await saveDescription('t1', 'e1', null, blank, 'Ashfang');
    await saveDescription('t1', 'e1', null, { ...blank, title: '' }, 'Ashfang');
    expect(api.POST).not.toHaveBeenCalled();

    await saveDescription('t1', 'e1', null, { ...blank, content: 'It hums.' }, 'Ashfang');
    await saveDescription('t1', 'e1', null, { ...blank, title: 'The sword' }, 'Ashfang');
    expect(api.POST.mock.calls.map(([, { body }]) => body)).toEqual([
      {
        title: 'Ashfang',
        type: 'description',
        is_public: true,
        content: 'It hums.',
        locale: 'en-GB',
      },
      { title: 'The sword', type: 'description', is_public: true, content: '', locale: 'en-GB' },
    ]);
  });

  it('are updated in place when there is one', async () => {
    await saveDescription(
      't1',
      'e1',
      info,
      { ...descriptionDraft(info, 'x'), title: 'The sword' },
      'x',
    );
    expect(api.POST).not.toHaveBeenCalled();
    expect(writes()).toHaveLength(1);
  });
});

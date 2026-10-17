import { describe, expect, it } from 'vitest';
import { Bench } from './bench';
import { SampleTransport } from './sample';
import { RefusedError } from './transport';

class BundleServer extends SampleTransport {
  second = 'A second text.';
  stamp = 1;
  constructor() {
    super([{ id: 'a', name: 'Map', kinds: ['item'], parents: [], description: 'First text.' }]);
  }
  override async getEntry(id: string) {
    const entry = await super.getEntry(id);
    const doc = entry.description;
    if (doc)
      doc.information = {
        id: doc.id,
        title: doc.title,
        type: 'description',
        is_public: false,
        order: 0,
        updated_at: 'bundle',
        payloads: [
          {
            kind: 'description',
            id: doc.payloadId,
            content: doc.text,
            locale: 'en-US',
            order: 0,
            updated_at: 'first',
          },
          {
            kind: 'picture',
            id: 'map-image',
            url: '/protected',
            file_type: 'image/png',
            order: 1,
            updated_at: 'picture',
          },
          {
            kind: 'description',
            id: 'second-text',
            content: this.second,
            locale: 'en-US',
            order: 2,
            updated_at: String(this.stamp),
          },
        ],
      };
    return entry;
  }
  override async setText(id: string, text: string, version: string | null) {
    if (id !== 'second-text') return super.setText(id, text, version);
    if (version !== `W/"${this.stamp}"`) throw new RefusedError('Changed.', true);
    this.second = text;
    this.stamp++;
  }
}

describe('commands on a particular text in a bundle', () => {
  it('preserves another writer’s first text and the picture, including when undone', async () => {
    const server = new BundleServer();
    const bench = new Bench(server);
    await bench.loadEntries();
    await bench.open('a');
    server.editTextElsewhere('a', 'description', 'A newer first text.');
    bench.setDescription('a', 'A revised second text.', 'second-text');
    expect(bench.view('a')?.description?.information?.payloads[2]).toMatchObject({
      content: 'A revised second text.',
    });
    await bench.run();
    expect(server.second).toBe('A revised second text.');
    expect(bench.view('a')?.description?.text).toBe('A newer first text.');
    expect(bench.view('a')?.description?.information?.payloads[1]?.id).toBe('map-image');
    bench.undo('a');
    await bench.run();
    expect(server.second).toBe('A second text.');
    expect(bench.view('a')?.description?.text).toBe('A newer first text.');
  });
  it('reports a conflict on the addressed text and sends no overwrite', async () => {
    const server = new BundleServer();
    const bench = new Bench(server);
    await bench.loadEntries();
    await bench.open('a');
    server.second = 'Someone else’s second text.';
    server.stamp++;
    bench.setDescription('a', 'My second text.', 'second-text');
    await bench.run();
    expect(server.second).toBe('Someone else’s second text.');
    expect(bench.outbox[0]).toMatchObject({
      state: 'conflict',
      payloadId: 'second-text',
      theirs: 'Someone else’s second text.',
    });
  });
});

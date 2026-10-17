import { describe, expect, it } from 'vitest';
import { Bench } from './bench';
import { SampleTransport } from './sample';
import {
  type EntryFieldTarget,
  type FieldSnapshot,
  fieldKey,
  type NewText,
  OfflineError,
} from './transport';

class Server extends SampleTransport {
  fields = new Map<string, FieldSnapshot>();
  pictures = new Map<string, string[]>();
  createCalls: string[] = [];
  appendCalls: string[] = [];
  failCreate = false;
  loseUpload = false;
  constructor(description?: string) {
    super([
      {
        id: 'a',
        name: 'A fact',
        kinds: ['fact'],
        parents: [],
        ...(description !== undefined && { description }),
      },
    ]);
  }
  override async getEntry(id: string) {
    const entry = await super.getEntry(id);
    for (const doc of [entry.description, ...entry.notes]) {
      if (!doc) continue;
      doc.information = {
        id: doc.id,
        type: entry.description?.id === doc.id ? 'description' : 'note',
        title: doc.title,
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
            updated_at: 'text',
          },
          ...(this.pictures.get(doc.id) ?? []).map((id, order) => ({
            kind: 'picture' as const,
            id,
            url: '/content',
            file_type: 'image/png',
            order: order + 1,
            updated_at: 'picture',
          })),
        ],
      };
    }
    return entry;
  }
  override async createText(entryId: string, text: NewText) {
    this.createCalls.push(text.id);
    if (this.failCreate) {
      this.failCreate = false;
      throw new OfflineError();
    }
    return super.createText(entryId, text);
  }
  async appendPicture(informationId: string, payloadId: string) {
    this.appendCalls.push(payloadId);
    const ids = this.pictures.get(informationId) ?? [];
    if (!ids.includes(payloadId)) this.pictures.set(informationId, [...ids, payloadId]);
    if (this.loseUpload) {
      this.loseUpload = false;
      throw new OfflineError();
    }
  }
  async readField(target: EntryFieldTarget) {
    return this.fields.get(fieldKey(target)) ?? { value: false, version: '1' };
  }
  async writeField(entryId: string, target: EntryFieldTarget, value: string | boolean) {
    this.fields.set(fieldKey(target), { value, version: '2' });
    return this.getEntry(entryId);
  }
}
const file = () => new File(['picture bytes'], 'map.png', { type: 'image/png' });
const opened = async (server: Server) => {
  let n = 0;
  const bench = new Bench(server, () => `stable-${++n}`);
  await bench.loadEntries();
  await bench.open('a');
  return bench;
};

describe('online information pictures', () => {
  it('retries a failed information create using its allocated id', async () => {
    const server = new Server();
    const bench = await opened(server);
    server.failCreate = true;
    await bench.addInformationPicture('a', null, 'description', file());
    expect(bench.informationUpload('a', null, 'description')?.problem).toContain('connection');
    await bench.retryInformationPicture('a', null, 'description');
    expect(server.createCalls).toHaveLength(2);
    expect(new Set(server.createCalls).size).toBe(1);
    expect(bench.view('a')?.description?.information?.payloads.map((p) => p.kind)).toEqual([
      'description',
      'picture',
    ]);
  });
  it('recovers a lost upload response without duplicating the picture or overwriting newer text', async () => {
    const server = new Server('Original.');
    const bench = await opened(server);
    const id = bench.view('a')?.description?.id as string;
    server.loseUpload = true;
    await bench.addInformationPicture('a', id, 'description', file());
    server.editTextElsewhere('a', 'description', 'Newer text.');
    await bench.retryInformationPicture('a', id, 'description');
    expect(new Set(server.appendCalls).size).toBe(1);
    expect(server.pictures.get(id)).toHaveLength(1);
    expect(bench.view('a')?.description?.text).toBe('Newer text.');
    expect(bench.informationUpload('a', id, 'description')).toBeUndefined();
  });
  it('waits for an unresolved text conflict instead of uploading into it', async () => {
    const server = new Server('Original.');
    const bench = await opened(server);
    const id = bench.view('a')?.description?.id as string;
    server.editTextElsewhere('a', 'description', 'Someone else’s text.');
    bench.setDescription('a', 'My draft.');
    await bench.addInformationPicture('a', id, 'description', file());
    expect(server.appendCalls).toHaveLength(0);
    expect(bench.informationUpload('a', id, 'description')?.problem).toContain('resolve');
  });
});

describe('audience and About commands', () => {
  it('refuses a changed audience and leaves its explicit grants intact', async () => {
    const server = new Server();
    const bench = await opened(server);
    const target: EntryFieldTarget = { kind: 'entry-audience', id: 'a' };
    const old = JSON.stringify({ is_public: false, entity_ids: ['old'], player_ids: [] });
    const theirs = JSON.stringify({ is_public: false, entity_ids: ['new'], player_ids: ['seat'] });
    server.fields.set(fieldKey(target), { value: theirs, version: '2' });
    bench.setField(
      'a',
      target,
      { value: old, version: '1' },
      JSON.stringify({ is_public: true, entity_ids: [], player_ids: [] }),
    );
    await bench.run();
    expect(bench.outbox[0]).toMatchObject({ state: 'conflict', theirs });
    expect((await server.readField(target)).value).toBe(theirs);
  });
  it('adds and undoes one About edge while preserving another writer’s edge', async () => {
    const server = new Server();
    const bench = await opened(server);
    const target: EntryFieldTarget = { kind: 'fact-about', id: 'a', subjectId: 'lich' };
    const other: EntryFieldTarget = { kind: 'fact-about', id: 'a', subjectId: 'weapon' };
    server.fields.set(fieldKey(other), { value: true, version: null });
    bench.setField('a', target, { value: false, version: null }, true);
    await bench.run();
    bench.undo('a');
    await bench.run();
    expect((await server.readField(target)).value).toBe(false);
    expect((await server.readField(other)).value).toBe(true);
  });
});

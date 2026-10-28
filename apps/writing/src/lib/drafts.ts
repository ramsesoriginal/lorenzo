import type { BundleReceipt, DraftPayload, Information } from '@lorenzo/information-editor';
export type Draft = { original: Information; receipt: BundleReceipt; payloads: DraftPayload[] };
type Stored = { key: string; id: string; generation: string; draft: Draft; savedAt: number };
export const draftKey = (api: string, account: string, tenant: string, information: string) =>
  JSON.stringify([new URL(api).origin, account, tenant, information]);
const session = crypto.randomUUID();
const recovered = new Map<string, Stored>();
function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('lorenzo-writing-drafts', 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains('versions'))
        request.result
          .createObjectStore('versions', { keyPath: 'id' })
          .createIndex('manuscript', 'key');
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Draft storage is busy in another tab.'));
  });
}
async function transaction<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore, done: (value: T) => void) => void,
): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('versions', mode);
    let value: T;
    action(tx.objectStore('versions'), (result) => {
      value = result;
    });
    tx.oncomplete = () => {
      db.close();
      resolve(value);
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function readDrafts(key: string): Promise<Stored[]> {
  return transaction('readonly', (store, done) => {
    const request = store.index('manuscript').getAll(key);
    request.onsuccess = () =>
      done((request.result as Stored[]).sort((a, b) => b.savedAt - a.savedAt));
  });
}
export async function readDraft(key: string): Promise<Draft | undefined> {
  const [latest] = await readDrafts(key);
  if (latest) recovered.set(key, latest);
  return latest?.draft;
}
export function selectDraft(key: string, draft: Stored) {
  recovered.set(key, draft);
}
export async function writeDraft(key: string, draft: Draft): Promise<void> {
  return transaction('readwrite', (store, done) => {
    store.put({
      key,
      id: JSON.stringify([key, session]),
      generation: crypto.randomUUID(),
      draft,
      savedAt: Date.now(),
    } satisfies Stored);
    done(undefined);
  });
}
export async function removeDraft(key: string): Promise<void> {
  return transaction('readwrite', (store, done) => {
    store.delete(JSON.stringify([key, session]));
    const prior = recovered.get(key);
    if (prior) {
      const request = store.get(prior.id);
      request.onsuccess = () => {
        // Another open tab may have continued writing this draft. Never delete its newer work.
        if ((request.result as Stored | undefined)?.generation === prior.generation)
          store.delete(prior.id);
      };
      recovered.delete(key);
    }
    done(undefined);
  });
}
export async function forgetDrafts(key: string): Promise<void> {
  return transaction('readwrite', (store, done) => {
    const request = store.index('manuscript').openKeyCursor(key);
    request.onsuccess = () => {
      const cursor = request.result;
      if (cursor) {
        store.delete(cursor.primaryKey);
        cursor.continue();
      }
    };
    recovered.delete(key);
    done(undefined);
  });
}

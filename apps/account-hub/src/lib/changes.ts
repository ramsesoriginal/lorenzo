import { client, unwrap } from './api';
import type { EntityChange, Page } from './types';

// ADR 0099 - what happened to what the caller's characters hold, newest first, across every
// library. One page is all a summary needs.
export async function listMyChanges(size: number): Promise<Page<EntityChange>> {
  return unwrap(await client.GET('/me/changes', { params: { query: { page: 1, size } } }));
}

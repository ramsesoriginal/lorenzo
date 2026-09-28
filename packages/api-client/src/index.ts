import createClient, { type Client, type Middleware } from 'openapi-fetch';
import { z } from 'zod';
import type { components, paths } from './schema';

export type { components, paths } from './schema';

/** One of apps/api's response or request schemas, by name: `Schema<'ItemInstanceOut'>`. */
export type Schema<Name extends keyof components['schemas']> = components['schemas'][Name];

/** The typed client: `client.GET('/tenants/{tenant_id}/…', { params })`, checked against apps/api. */
export type LorenzoClient = Client<paths>;

/**
 * Any failed call to apps/api. `problem` is the whole RFC 9457 body the API sent, including
 * any fields of its own beyond `type`/`title`/`detail`, so a caller can show a refusal's
 * specifics without the client deciding anything.
 */
export class LorenzoApiError extends Error {
  readonly status: number;
  readonly problemType: string | undefined;
  readonly problem: Readonly<Record<string, unknown>>;

  constructor(
    message: string,
    status: number,
    problemType?: string,
    problem: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = 'LorenzoApiError';
    this.status = status;
    this.problemType = problemType;
    this.problem = problem;
  }
}

// RFC 9457 "Problem Details" - every apps/api error response is shaped this way
// (errors.py/exceptions.py, ADR 0020). Deliberately permissive (every field optional,
// unknown fields kept): a slightly different body should still give a readable error,
// not a second failure.
const problemSchema = z
  .object({
    type: z.string().optional(),
    title: z.string().optional(),
    detail: z.string().optional(),
  })
  .passthrough();

/** A failed response's body and status, as a `LorenzoApiError` with the API's own message. */
export function toLorenzoApiError(error: unknown, status: number): LorenzoApiError {
  const parsed = problemSchema.safeParse(error);
  const problem = parsed.success ? parsed.data : undefined;
  return new LorenzoApiError(
    problem?.detail ?? problem?.title ?? `Request failed (${status}).`,
    status,
    problem?.type,
    problem ?? {},
  );
}

/** An openapi-fetch result's data, or a thrown `LorenzoApiError`. */
export async function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): Promise<T> {
  if (result.error !== undefined) {
    throw toLorenzoApiError(result.error, result.response.status);
  }
  return result.data as T;
}

/** Where a client gets the caller's access token before each request. */
export type AccessTokenSource = () =>
  | string
  | null
  | undefined
  | Promise<string | null | undefined>;

export interface LorenzoClientOptions {
  baseUrl: string;
  /**
   * Given, every request carries this token, and a request without one is refused before it's
   * sent. Omitted, callers pass their own `Authorization` header per request - a bot acting
   * for many users does.
   */
  getAccessToken?: AccessTokenSource;
  /** A `fetch` to use instead of the global one, for tests. */
  fetch?: (input: Request) => Promise<Response>;
}

function bearerToken(getAccessToken: AccessTokenSource): Middleware {
  return {
    async onRequest({ request }) {
      const accessToken = await getAccessToken();
      if (!accessToken) {
        throw new LorenzoApiError('Not logged in.', 401);
      }
      request.headers.set('Authorization', `Bearer ${accessToken}`);
      return request;
    },
  };
}

/** A client for apps/api at `baseUrl`. */
export function createLorenzoClient(options: LorenzoClientOptions): LorenzoClient {
  const client = createClient<paths>({
    baseUrl: options.baseUrl,
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  if (options.getAccessToken) {
    client.use(bearerToken(options.getAccessToken));
  }
  return client;
}

/** One page of a paginated listing (ADR 0020). */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

/** The largest page size the API allows (ADR 0020) - fewest round trips. */
export const MAX_PAGE_SIZE = 100;

/**
 * Every item of a paginated listing: page 1, then every remaining page in parallel (the count
 * is known from the first response's `pages`). `getPage` is the typed call for one page, so
 * this doesn't care which endpoint it pages.
 */
export async function fetchAllPages<T>(getPage: (page: number) => Promise<Page<T>>): Promise<T[]> {
  const first = await getPage(1);
  if (first.pages <= 1) return first.items;
  const rest = await Promise.all(Array.from({ length: first.pages - 1 }, (_, i) => getPage(i + 2)));
  return [first.items, ...rest.map((page) => page.items)].flat();
}

/**
 * The `ETag` a response carried, to send back as `If-Match` on a later write to the same thing
 * (ADR 0042), or null if it carried none.
 */
export function etagOf(response: Response): string | null {
  return response.headers.get('etag');
}

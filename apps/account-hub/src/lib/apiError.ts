// Split out of api.ts so it can be imported (including from tests) without
// pulling in api.ts -> auth.ts -> @authgear/web's browser-only side effect
// on import - see format.ts's own comment on the same issue.
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

import { describe, expect, it } from 'vitest';
import { ApiError } from '../../src/lib/apiError';
import {
  describeError,
  isSessionExpired,
  SESSION_EXPIRED,
  SOMETHING_WENT_WRONG,
  UNREACHABLE,
} from '../../src/lib/describeError';

function problem(status: number, body: Record<string, unknown> = {}): ApiError {
  const { detail, title, type } = body;
  const message =
    (typeof detail === 'string' ? detail : undefined) ??
    (typeof title === 'string' ? title : undefined) ??
    `Request failed (${status}).`;
  return new ApiError(message, status, typeof type === 'string' ? type : undefined, body);
}

function validation(errors: { loc: (string | number)[]; msg: string; type?: string }[]): ApiError {
  return problem(422, {
    title: 'Request Validation Error',
    type: 'validation',
    status: 422,
    errors,
  });
}

describe('describeError: what the API said', () => {
  it("prefers the problem's detail", () => {
    const error = problem(409, { title: 'Slug already in use', detail: "Slug 'north' is taken" });
    expect(describeError(error)).toBe("Slug 'north' is taken");
  });

  it('falls back to the title when there is no detail', () => {
    expect(describeError(problem(403, { title: 'Forbidden' }))).toBe('Forbidden');
  });

  it('treats an empty or blank detail as missing', () => {
    expect(describeError(problem(404, { detail: '   ', title: 'Not found' }))).toBe('Not found');
  });

  it('never shows the title of a 422 in place of its fields', () => {
    const error = validation([{ loc: ['body', 'name'], msg: 'Field required' }]);
    expect(describeError(error)).not.toContain('Request Validation Error');
  });

  it("does not show the client's own bare 'Request failed (n).'", () => {
    expect(describeError(problem(500))).toBe(SOMETHING_WENT_WRONG);
  });

  it('keeps a message an ApiError was made with when the body held nothing', () => {
    expect(describeError(new ApiError('Tenant editing is closed.', 503))).toBe(
      'Tenant editing is closed.',
    );
  });

  it('never shows a body that is raw JSON', () => {
    const raw = new ApiError('{"type":"x","title":"y"}', 500, undefined, {
      detail: '{"nested":true}',
      title: '[1, 2]',
    });
    expect(describeError(raw)).toBe(SOMETHING_WENT_WRONG);
  });
});

describe('describeError: a 422', () => {
  it('names the field and what is wrong with it', () => {
    const error = validation([
      { loc: ['body', 'slug'], msg: "String should match pattern '^[a-z0-9]+$'" },
    ]);
    expect(describeError(error)).toBe(
      "Check what you entered: slug (string should match pattern '^[a-z0-9]+$').",
    );
  });

  it('turns underscores in a field name into spaces', () => {
    const error = validation([
      { loc: ['body', 'max_uses'], msg: 'Input should be greater than 0' },
    ]);
    expect(describeError(error)).toBe(
      'Check what you entered: max uses (input should be greater than 0).',
    );
  });

  it('uses the last named part of a nested location, and skips list positions', () => {
    const error = validation([{ loc: ['body', 0, 'user_id'], msg: 'Field required' }]);
    expect(describeError(error)).toBe('Check what you entered: user id (field required).');
  });

  it('leaves out the field when the location only says where in the request', () => {
    const error = validation([{ loc: ['body'], msg: 'Input should be a valid dictionary' }]);
    expect(describeError(error)).toBe(
      'Check what you entered: input should be a valid dictionary.',
    );
  });

  it("drops pydantic's 'Value error, ' prefix and a final full stop", () => {
    const error = validation([{ loc: ['body', 'expires_at'], msg: 'Value error, too far away.' }]);
    expect(describeError(error)).toBe('Check what you entered: expires at (too far away).');
  });

  it('keeps an acronym or name capitalised', () => {
    const error = validation([{ loc: ['body', 'url'], msg: 'URL scheme should be http' }]);
    expect(describeError(error)).toBe('Check what you entered: url (URL scheme should be http).');
  });

  it('shows three fields and counts the rest', () => {
    const error = validation(
      ['a', 'b', 'c', 'd', 'e'].map((name) => ({ loc: ['body', name], msg: 'Field required' })),
    );
    expect(describeError(error)).toBe(
      'Check what you entered: a (field required); b (field required); c (field required); and 2 more.',
    );
  });

  it('skips entries it cannot read, and falls back when none are left', () => {
    const odd = validation([{ loc: ['body', 'a'], msg: '' }, null as never, { loc: [] } as never]);
    expect(describeError(odd)).toBe('Request Validation Error');
  });

  it('is only for a 422', () => {
    const error = problem(400, {
      title: 'Bad Request',
      errors: [{ loc: ['body', 'x'], msg: 'no' }],
    });
    expect(describeError(error)).toBe('Bad Request');
  });
});

describe('describeError: a session that has ended', () => {
  it('says so for a 401 from the API, whatever the body held', () => {
    expect(describeError(problem(401, { detail: 'Token expired' }))).toBe(SESSION_EXPIRED);
  });

  it('says so when the client refused to send without a token', () => {
    expect(describeError(new ApiError('Not logged in.', 401))).toBe(SESSION_EXPIRED);
  });

  it("says so for Authgear's invalid_grant (a revoked or used-up refresh token)", () => {
    const oauth = Object.assign(new Error('invalid_grant: expired'), { error: 'invalid_grant' });
    expect(describeError(oauth)).toBe(SESSION_EXPIRED);
    const server = Object.assign(new Error('gone'), { reason: 'InvalidGrant' });
    expect(describeError(server)).toBe(SESSION_EXPIRED);
  });

  it('is not claimed for other refusals', () => {
    expect(describeError(problem(403, { title: 'Forbidden' }))).toBe('Forbidden');
    const other = Object.assign(new Error('nope'), { error: 'access_denied' });
    expect(describeError(other)).toBe('nope');
  });
});

describe('isSessionExpired', () => {
  it.each([
    [problem(401), true],
    [new ApiError('Not logged in.', 401), true],
    [Object.assign(new Error('x'), { error: 'invalid_grant' }), true],
    [Object.assign(new Error('x'), { reason: 'InvalidGrant' }), true],
    [problem(403), false],
    [problem(404), false],
    [new Error('401'), false],
    ['401', false],
    [null, false],
    [undefined, false],
  ])('%#', (error, expected) => {
    expect(isSessionExpired(error)).toBe(expected);
  });
});

describe('describeError: Lorenzo could not be reached', () => {
  it.each([
    'Failed to fetch',
    'Load failed',
    'NetworkError when attempting to fetch resource.',
    'Network request failed',
    'fetch failed',
  ])('%s', (message) => {
    expect(describeError(new TypeError(message))).toBe(UNREACHABLE);
  });

  it('is only for a failed fetch, not any TypeError', () => {
    expect(describeError(new TypeError("Cannot read properties of undefined (reading 'x')"))).toBe(
      "Cannot read properties of undefined (reading 'x')",
    );
  });
});

describe('describeError: anything else', () => {
  it('shows a plain sentence this app threw on purpose', () => {
    expect(
      describeError(new Error('Tenant editing is temporarily unavailable. Try again later.')),
    ).toBe('Tenant editing is temporarily unavailable. Try again later.');
  });

  it('shows a thrown string that reads as a sentence', () => {
    expect(describeError('Something specific happened.')).toBe('Something specific happened.');
  });

  it.each([
    ['an error with no message', new Error('')],
    ['an error holding a JSON body', new Error('{"detail":"x"}')],
    ['a string holding a JSON array', '[{"loc":[]}]'],
    ['null', null],
    ['undefined', undefined],
    ['a number', 404],
    ['an object', { status: 500 }],
  ])('falls back for %s', (_name, error) => {
    expect(describeError(error)).toBe(SOMETHING_WENT_WRONG);
  });
});

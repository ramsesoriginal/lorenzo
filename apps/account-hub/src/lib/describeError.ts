// What went wrong, as a sentence to show a person (ADR 0170). Pure and
// dependency-free like format.ts: it imports ./apiError (a re-export of
// LorenzoApiError) and nothing that reaches @authgear/web, so Vitest can
// load it. The structured data stays on the ApiError itself; this only reads
// it, and never rewrites what the API said.
import { ApiError } from './apiError';

export const SESSION_EXPIRED = 'Your session has expired. Log in again.';
export const UNREACHABLE = "Lorenzo couldn't be reached. Check your connection and try again.";
export const SOMETHING_WENT_WRONG = 'Something went wrong. Try again in a moment.';

// How browsers word a fetch() that never got an answer: Chromium, Firefox,
// Safari, and Node's own fetch.
const NETWORK_FAILURE =
  /failed to fetch|networkerror|load failed|network request failed|fetch failed/i;

// Where a field sits in the request, not which field: FastAPI's loc starts
// with one of these.
const LOCATION_PREFIXES = new Set(['body', 'query', 'path', 'header', 'cookie']);

const MAX_FIELDS_SHOWN = 3;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

// A body that starts with { or [ is raw JSON, which is never for a person.
function readable(text: unknown): string | null {
  if (typeof text !== 'string') return null;
  const trimmed = text.trim();
  if (trimmed === '' || trimmed.startsWith('{') || trimmed.startsWith('[')) return null;
  return trimmed;
}

// Authgear's SDK clears the session and then throws when a refresh token has
// been revoked or has run out: an OAuthError with error "invalid_grant", or a
// ServerError whose reason is "InvalidGrant". Either way, the same thing a
// 401 from the API means.
function isInvalidGrant(error: unknown): boolean {
  return isRecord(error) && (error.error === 'invalid_grant' || error.reason === 'InvalidGrant');
}

export function isSessionExpired(error: unknown): boolean {
  if (error instanceof ApiError) return error.status === 401;
  return isInvalidGrant(error);
}

function fieldName(loc: unknown): string | null {
  if (!Array.isArray(loc)) return null;
  const names = loc.filter(
    (part): part is string => typeof part === 'string' && !LOCATION_PREFIXES.has(part),
  );
  const last = names.at(-1);
  return last === undefined ? null : last.replace(/_/g, ' ');
}

// Pydantic's own wording, tidied for the middle of a sentence: no "Value
// error, " prefix, no final full stop, and a lower-case start unless the
// second letter is a capital too (an acronym, a name).
function tidyMessage(message: string): string {
  const withoutPrefix = message
    .trim()
    .replace(/^Value error,\s*/i, '')
    .replace(/\.$/, '');
  const [first = '', second = ''] = withoutPrefix;
  return first === first.toUpperCase() && second === second.toLowerCase()
    ? first.toLowerCase() + withoutPrefix.slice(1)
    : withoutPrefix;
}

// A 422's body is {title, type, status, errors: [{loc, msg, type}]} and has
// no detail, so it is the errors, not the title, that say what to fix.
function validationSummary(problem: Readonly<Record<string, unknown>>): string | null {
  if (!Array.isArray(problem.errors)) return null;
  const entries = problem.errors.flatMap((entry: unknown) => {
    if (!isRecord(entry) || typeof entry.msg !== 'string') return [];
    const message = tidyMessage(entry.msg);
    if (message === '') return [];
    const field = fieldName(entry.loc);
    return [field === null ? message : `${field} (${message})`];
  });
  if (entries.length === 0) return null;
  const shown = entries.slice(0, MAX_FIELDS_SHOWN).join('; ');
  const more = entries.length - MAX_FIELDS_SHOWN;
  return `Check what you entered: ${shown}${more > 0 ? `; and ${more} more` : ''}.`;
}

function describeApiError(error: ApiError): string {
  if (error.status === 422) {
    const summary = validationSummary(error.problem);
    if (summary !== null) return summary;
  }
  return (
    readable(error.problem.detail) ??
    readable(error.problem.title) ??
    // The client's own "Request failed (n)." says nothing a person can use.
    (/^Request failed \(\d+\)\.?$/.test(error.message) ? null : readable(error.message)) ??
    SOMETHING_WENT_WRONG
  );
}

export function describeError(error: unknown): string {
  if (isSessionExpired(error)) return SESSION_EXPIRED;
  if (error instanceof ApiError) return describeApiError(error);
  if (error instanceof TypeError && NETWORK_FAILURE.test(error.message)) return UNREACHABLE;
  // This app throws a few plain sentences on purpose ("Tenant editing is
  // temporarily unavailable..."); those are for a person. A thrown string too.
  if (error instanceof Error) return readable(error.message) ?? SOMETHING_WENT_WRONG;
  return readable(error) ?? SOMETHING_WENT_WRONG;
}

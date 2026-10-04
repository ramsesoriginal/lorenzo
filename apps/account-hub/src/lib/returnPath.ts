// Where to land after a login (ADR 0170): the page "Log in" was pressed on.
// Pure and dependency-free like format.ts. It holds a path on this origin,
// never a token or an identifier, and anything else becomes home.

export const RETURN_PATH_KEY = 'lorenzo.returnTo';

const HOME = '/';
// Resolving against a made-up origin tells a plain path from anything that
// would leave this one ("//evil.example", "https://evil.example", "/\\evil").
const PLACEHOLDER_ORIGIN = 'https://return-path.invalid';
const MAX_LENGTH = 512;

// pathname + search of a same-origin path, else "/". The login pages
// themselves are refused, so a login never returns to a login.
export function safeReturnPath(value: unknown): string {
  if (typeof value !== 'string' || value.length > MAX_LENGTH) return HOME;
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return HOME;
  let url: URL;
  try {
    url = new URL(value, PLACEHOLDER_ORIGIN);
  } catch {
    return HOME;
  }
  if (url.origin !== PLACEHOLDER_ORIGIN) return HOME;
  if (url.pathname.startsWith('/auth/')) return HOME;
  return `${url.pathname}${url.search}`;
}

// Even reading window.sessionStorage can throw (blocked site data, some
// private windows), and a login must not fail for that: the person just lands
// on the home page.
export function browserSessionStorage(): Storage | undefined {
  try {
    return window.sessionStorage;
  } catch {
    return undefined;
  }
}

export function rememberReturnPath(
  storage: Pick<Storage, 'setItem'> | undefined,
  path: string,
): void {
  try {
    storage?.setItem(RETURN_PATH_KEY, safeReturnPath(path));
  } catch {
    // Nothing to remember it in.
  }
}

export function takeReturnPath(
  storage: Pick<Storage, 'getItem' | 'removeItem'> | undefined,
): string {
  try {
    const value = storage?.getItem(RETURN_PATH_KEY);
    storage?.removeItem(RETURN_PATH_KEY);
    return safeReturnPath(value);
  } catch {
    return HOME;
  }
}

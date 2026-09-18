// Pure text<->value helpers for form fields - deliberately dependency-free
// (no api.ts/auth.ts import chain, which pulls in @authgear/web's
// browser-only side effects on import and would break these under a plain
// Vitest/Node environment for no real reason).

export function localesToText(locales: string[]): string {
  return locales.join(', ');
}

export function textToLocales(text: string): string[] {
  return text
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

// "" means the user cleared a nullable text field - ProfileUpdate needs an
// explicit null for that (an empty string would fail nickname's own
// min_length=1, and is meaningless for the others too).
export function textOrNull(value: string): string | null {
  return value.trim() === '' ? null : value;
}

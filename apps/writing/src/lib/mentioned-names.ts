export const nameKey = (text: string) =>
  text.normalize('NFC').trim().replace(/\s+/gu, ' ').toLowerCase();

export function mentioned(passages: readonly string[], name: string) {
  const key = nameKey(name);
  if (!key || !passages.some((passage) => passage.includes(key))) return false;
  const literal = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const word = '[\\p{L}\\p{M}\\p{N}\\p{Pc}]';
  const pattern = new RegExp(`(?<!${word})${literal}(?!${word})`, 'u');
  return passages.some((passage) => pattern.test(passage));
}

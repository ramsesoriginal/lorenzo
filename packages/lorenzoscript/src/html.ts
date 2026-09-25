// Escaping shared by the renderer and the math converter: every piece of text
// and every attribute value goes through here.

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };

export const escapeHtml = (s: string) => s.replace(/[&<>"]/g, (c) => ESCAPES[c] as string);

/** ` name="value"`, or nothing for an empty value. */
export const attr = (name: string, value: string) =>
  value ? ` ${name}="${escapeHtml(value)}"` : '';

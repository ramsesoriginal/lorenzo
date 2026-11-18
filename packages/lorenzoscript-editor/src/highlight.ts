// Quiet highlighting (ADR 0516): the markers of LorenzoScript shown in a softer colour behind the
// text, so a source reads at a glance. Colour only, never size or weight, so the text under the
// layer keeps its exact place. Opt-in: `highlight` on the editor.

export type Mark = 'mark' | 'code' | 'ref' | 'link' | 'quote';

const esc = (text: string) =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const span = (kind: Mark, text: string) => `<span class="ls-hl-${kind}">${esc(text)}</span>`;

// One line at a time, one pass, no backtracking over the whole text.
const INLINE =
  /(`[^`\n]+`)|(\[\[[^\]\n]*\]\])|(!?\[[^\]\n]*\]\([^)\n]*\))|(\*\*|~~|__|(?<![\w*])\*(?=\S)|(?<=\S)\*(?![\w*]))/g;

function inline(line: string): string {
  let out = '';
  let last = 0;
  for (const m of line.matchAll(INLINE)) {
    out += esc(line.slice(last, m.index));
    if (m[1]) out += span('code', m[1]);
    else if (m[2]) out += span('ref', m[2]);
    else if (m[3]) out += span('link', m[3]);
    else out += span('mark', m[4] as string);
    last = (m.index as number) + m[0].length;
  }
  return out + esc(line.slice(last));
}

/** The text as HTML in which only the markers are wrapped; escaped, and the same characters. */
export function highlightSource(source: string): string {
  let fenced = false;
  return source
    .split('\n')
    .map((line) => {
      if (/^ {0,3}(`{3,}|~{3,})/.test(line)) {
        fenced = !fenced;
        return span('code', line);
      }
      if (fenced) return span('code', line);
      const head = /^( {0,3}#{1,6})(\s.*)?$/.exec(line);
      if (head) return span('mark', head[1] as string) + inline(head[2] ?? '');
      const quote = /^( {0,3}(?:>\s?)+)(.*)$/.exec(line);
      if (quote) return span('quote', quote[1] as string) + inline(quote[2] ?? '');
      const list = /^(\s*(?:[-*+]|\d{1,9}[.)])\s+(?:\[[ xX]\]\s+)?)(.*)$/.exec(line);
      if (list) return span('mark', list[1] as string) + inline(list[2] ?? '');
      return inline(line);
    })
    .join('\n');
}

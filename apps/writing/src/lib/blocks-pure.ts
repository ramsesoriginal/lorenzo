// The part of the page's block actions that needs no page (ADR 0494, W3).
const SAFE_BOUNDARY = /\n[ \t]*\n(?:[ \t]*\n)*/g;

/** Where a split would fall for a caret: the start of the section after the last blank line
 * before it, or none. Pure, so the page and its tests share it. */
export function boundaryBefore(text: string, caret: number): number | null {
  let boundary: number | null = null;
  for (const gap of text.matchAll(SAFE_BOUNDARY)) {
    const end = gap.index + gap[0].length;
    if (end > caret) break;
    boundary = end;
  }
  return boundary;
}

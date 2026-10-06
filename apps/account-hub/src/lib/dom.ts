// Shared DOM builders reused across pages - see ADR 0080. These build real elements, so (unlike
// format.ts's pure helpers) there's no import-chain purity to protect here; they simply live
// alongside the other lib/*.ts modules.

export function createStatusSpan(): HTMLSpanElement {
  const span = document.createElement('span');
  span.className = 'status-text';
  span.setAttribute('role', 'status');
  return span;
}

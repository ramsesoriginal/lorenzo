// Whether someone is in the middle of typing in a block of the page: focus is in one of its fields,
// or a text field holds something it was not drawn with. A background refresh draws a block again,
// which would throw that away, so it leaves such a block as it is.
const TEXT_FIELDS = 'input:not([type]), input[type="text"], input[type="search"], textarea';

export function isEditingIn(block: Element): boolean {
  const focused = document.activeElement;

  if (focused && block.contains(focused) && focused.matches('input, textarea, select')) return true;

  return [...block.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(TEXT_FIELDS)].some(
    (field) => field.value !== field.defaultValue,
  );
}

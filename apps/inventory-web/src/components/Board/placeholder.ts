// A column with no cards says so, in its own words (Equipped: "Nothing equipped.", ADR 0123).
export function ensurePlaceholder(list: HTMLUListElement) {
  if (list.children.length === 0) {
    const empty = document.createElement('li');
    empty.className = 'column-empty';
    empty.textContent = list.dataset.empty ?? 'This container is empty.';
    list.append(empty);
  }
}

export function removePlaceholder(list: HTMLUListElement) {
  list.querySelector('.column-empty')?.remove();
}

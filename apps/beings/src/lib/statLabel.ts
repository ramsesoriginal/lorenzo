// A stat or tag name as readers see it: `is_magical` is "Magical", `max_hp` "Max HP". A word of
// one or two letters is an abbreviation, like HP or AC.
export function statLabel(name: string): string {
  const words = name
    .replace(/^is_/, '')
    .split('_')
    .map((word) => (word.length <= 2 ? word.toUpperCase() : word));
  const label = words.join(' ');

  return label.charAt(0).toUpperCase() + label.slice(1);
}

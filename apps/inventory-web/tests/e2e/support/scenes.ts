// Worlds several tests share (ADR 0114), built on top of buildWorld's.
import type { Player, World } from './world.ts';

export const DESCRIPTIONS = {
  book: 'Pages bound between two covers, holding *whatever someone once thought worth keeping*.',
  spellbook:
    "Its pages hold **spells**, written in the caster's own notation, and are all but unreadable to anyone else.",
  ornate:
    'Gilded edges, a silver clasp, and a ribbon that never frays. The spells are no better; the *price* is.',
  backpack:
    "Canvas and leather on two straps, for the bulk of a traveller's kit. What's needed *quickly* belongs in a [[Belt Pouch]].",
  pouch: 'A small pouch worn at the hip, for coins, keys, and anything worth keeping close.',
};

/** A small catalog: Book → Spellbook → Ornate Spellbook, containers, and arrows. */
export async function catalog(world: World) {
  // Each book is made once the one it's based on is, and the rest don't wait for any of them.
  const books = (async () => {
    const book = await world.item('Book', { description: DESCRIPTIONS.book, stats: { weight: 2 } });
    const spellbook = await world.item('Spellbook', {
      prototypes: [book],
      description: DESCRIPTIONS.spellbook,
      tags: ['is_magical'],
    });
    const ornate = await world.item('Ornate Spellbook', {
      prototypes: [spellbook],
      description: DESCRIPTIONS.ornate,
      stats: { price: 250 },
    });
    return { book, spellbook, ornate };
  })();
  const [{ book, spellbook, ornate }, backpack, pouch, arrow] = await Promise.all([
    books,
    world.item('Backpack', { description: DESCRIPTIONS.backpack, tags: ['is_container'] }),
    world.item('Belt Pouch', { description: DESCRIPTIONS.pouch, tags: ['is_container'] }),
    world.item('Arrow'),
  ]);
  return { book, spellbook, ornate, backpack, pouch, arrow };
}

/** `player`'s character carrying a backpack and a belt pouch, and things in the backpack. */
export async function packed(world: World, player: Player) {
  const items = await catalog(world);
  const owner = { owner: player };
  // Equipped: contained by the character itself (RFC 0031). Owned alone, they'd be Not carried.
  const equipped = { ...owner, container: player.character.entity_id };
  const [backpack, pouch] = await Promise.all([
    world.instance(items.backpack, equipped),
    world.instance(items.pouch, equipped),
  ]);
  // What goes in the backpack waits for it, and not for each other.
  const [spellbook, arrows] = await Promise.all([
    world.instance(items.ornate, { ...owner, container: backpack }),
    world.stack(items.arrow, 3, { ...owner, container: backpack }),
  ]);
  return { items, backpack, pouch, spellbook, arrows };
}

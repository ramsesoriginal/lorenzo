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
  const backpack = await world.item('Backpack', {
    description: DESCRIPTIONS.backpack,
    tags: ['is_container'],
  });
  const pouch = await world.item('Belt Pouch', {
    description: DESCRIPTIONS.pouch,
    tags: ['is_container'],
  });
  const arrow = await world.item('Arrow');
  return { book, spellbook, ornate, backpack, pouch, arrow };
}

/** `player`'s character with a backpack, a belt pouch, and things in them. */
export async function packed(world: World, player: Player) {
  const items = await catalog(world);
  const owner = { owner: player };
  const backpack = await world.instance(items.backpack, owner);
  const pouch = await world.instance(items.pouch, owner);
  const spellbook = await world.instance(items.ornate, { ...owner, container: backpack });
  const arrows = await world.stack(items.arrow, 3, { ...owner, container: backpack });
  return { items, backpack, pouch, spellbook, arrows };
}

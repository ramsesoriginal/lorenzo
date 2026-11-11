# 0056 - Dice as a stat value: `2d6`, `W20`, `4d6dl1`

Status: accepted (2026-11-11), decided with the maintainer, not built; slices D1 to D3, each its own ADR. It adds a value type to what
[ADR 0014](../adr/0014-stats.md) and [ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md) define, and two
formula kinds beside those of [RFC 0016](0016-stats-computed-values-and-crud-api.md) and RFC 0053. It changes nothing decided
about how a stat resolves ([ADR 0037](../adr/0037-effective-stat-resolution.md)).

## Purpose

Let one stat hold a dice expression, written the way tables write it, in English or German, instead of spreading it over
several integer stats; and let a formula use its minimum, maximum or average.

## Decided inputs

1. **A dice value is written `xDy`**, with `W` accepted for `D` (German: Würfel): `2d6`, `2W6`.
2. **A die without a count** is `Dy` or `Wy`: `d20`, `W6`, one die.
3. **Dropping dice:** `xDyDz` drops the `z` lowest results (as `xDyDLz`); `xDyDLz` drops the lowest `z`; `xDyDHz` drops the
   highest `z`. `4d6dl1` is four six-sided dice without the lowest.
4. **Data model and API only.** No app, frontend or command-line change is part of this RFC, and every existing request and
   response keeps working as it does now (see Compatibility).
5. **The drop marker is `D` alone;** only the die marker takes `W`: `4W6DL1`.
6. **An average with a drop is exact,** computed within the limits and memoised.
7. **One die is canonical `d20`,** not `1d20`.
8. **The read is canonical `d`,** and a client may show `W`.

## What it is like today

A dice expression is three stats by convention: the seed's `damage_dice_count` and `damage_die` (`int`) and `damage_type`
(`text`), with a versatile die as a fourth. The sheet draws them as three cells. Nothing says `4d6 drop the lowest`. The
hover card for an item reads a stat named `damage`, so a library that wants a damage line writes a `text` stat by hand.

## Hard invariants

- **Lorenzo states dice, it does not roll them.** No random number, no roll history: clients roll.
- **A dice value is not a number.** A numeric formula refuses it, as it refuses `text`; `dice_value` is how a formula reads
  its minimum, maximum or average.
- **Exact arithmetic.** An average is an exact fraction of the dice expression, never a simulation, then rounded as any
  formula result is rounded.
- **Stored as parts.** The value is a count, a number of sides and an optional drop, not text that is parsed on every read.
- **Tenant isolation is by RLS** (ADR 0002); a copy, an update and a release carry the new type as they carry the others.

## Design (proposed)

### 1. A value type `dice`

A stat definition may have `value_type: "dice"`, beside `int`, `float`, `text`, `bool` and `enum`. It takes no unit,
minimum, maximum or enum values (422 as for `text`). As always, a definition's type and group do not change.

An entry's value is stored in the columns of the stat table next to the other value columns, as a fifth alternative of the
"exactly one value set" rule of ADR 0014: `dice_count`, `dice_sides`, `dice_drop_mode` (`lowest`, `highest` or null) and
`dice_drop_count`, with a check constraint.

### 2. The notation

Accepted, case-insensitive, spaces around the whole value ignored:

```text
dice   = [count] die [drop]
die    = ("d" | "w") sides
drop   = "d" ["l" | "h"] number
count, sides, number = decimal integers
```

| Written | Means |
| --- | --- |
| `d20`, `W20` | one twenty-sided die |
| `2d6`, `2W6` | two six-sided dice |
| `4d6d1`, `4d6dl1`, `4W6DL1` | four six-sided dice, drop the lowest one |
| `4d6dh1`, `4W6DH1` | four six-sided dice, drop the highest one |

Limits: count 1 to 100, sides 2 to 1000, a drop of 1 up to count minus 1 (so at least one die is kept). Anything else is a
422 `invalid-dice`, naming the part that failed.

The **canonical form** is lowercase `d`, the count left out when it is 1, and an explicit `dl` or `dh` for a drop: `d20`,
`2d6`, `4d6dl1`, `4d6dh1`. A value written in any accepted form is read back in the canonical one.

### 3. Writing and reading

`PUT /tenants/{t}/entities/{e}/stats/{d}` takes either the notation, `{"value": "4W6DL1"}`, or the parts,
`{"value": {"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 1}}}`. The stat row of every read (the entity read,
the bulk read, the explanation) shows `value` as the canonical notation, a string; a row of this type also carries `dice`,
the parts. Inherited, own and computed stats behave as for any type.

### 4. Reading a dice value in a formula

`dice_value(source, as, round_mode)`: a numeric stat from a dice stat, where `as` is `min`, `max` or `average`.

| Dice | min | max | average |
| --- | --- | --- | --- |
| `d20` | 1 | 20 | 10.5 |
| `2d6` | 2 | 12 | 7 |
| `4d6dl1` | 3 | 18 | 12.2446 (15869/1296) |

The average of a drop is the exact expectation of the kept dice, computed from the order statistics of the dice and
memoised by value. An `int` target needs a round mode for `average` unless the average is whole. A stat with no value gives
no value.

### 5. Building a dice value from stats

`dice(count, sides)`: a dice-typed stat from a count and a number of sides, each a stat or a constant. A library that
holds `damage_dice_count` and `damage_die` keeps them and adds a `damage` dice stat computed from them on its weapon
prototype; nothing is migrated. A drop is not part of this kind: a computed stat is `count` and `sides`, and a drop is
written as a value.

### 6. Where else it shows

The link preview of an item or a being prints a dice stat's notation, and a `damage` dice stat gives the item preview its
damage line without a text stat. The `{name}` chip of [ADR 0252](../adr/0252-lorenzoscript-stats-in-text.md) prints the
notation. Both are API payloads.

## Compatibility

This RFC changes the data model and the API, and only those. Every existing request keeps its path, its body, its response
and its status. The additions are: one value (`dice`) in the list of value types, two formula kinds, new nullable columns on
the stat table, a `dice` field on the stat row of a dice stat, and a use of an existing field (`value`) for the new type.
A library with no dice stat reads and writes as it does now, the three-stat convention stays valid, and the seed is not
touched. The OpenAPI breaking-change check reports the new value in an enum and the new members of the formula union; the
slice records them in `openapi-breaking-accepted.txt` with this RFC as the reason.

## Delivery

Each slice is its own ADR.

1. **D1.** The `dice` value type: storage, the notation and its canonical form, the write and read shapes, the stat
   definition, copy, update and release.
2. **D2.** `dice_value`.
3. **D3.** `dice`, and the link preview and text chip.

## Not in scope

- Rolling, roll history, and a random number of any kind.
- A flat modifier inside the notation (`2d6+3`): a bonus is a stat of its own, added by a formula.
- Keep-highest or keep-lowest notation, exploding or rerolled dice, advantage, percentile `d%`, fudge dice and mixed dice
  (`2d6+1d4`): a drop says what keep says, and the rest is not asked for.
- A display setting that writes `W` instead of `d` back: the read is canonical, a client may show either letter.
- A command-line or seed change: the seed's `damage_dice_count` and `damage_die` stay, and a `damage` dice stat on top of
  them is future work for the CLI.
- Apps: drawing, editing or rolling a dice value.

## Open questions

None.

## Alternatives considered

- **Keep three stats.** Works, and cannot say a drop, shows as three cells, and gives a hover card no damage line.
- **A `text` stat holding the notation.** Nothing validates it, and a formula cannot read its average.
- **Parse the text on every read.** Cheap to build, and every reader repeats the parser; parts are stored and the text is
  produced.
- **A dice value as a number** (its average). Loses the notation, and hides that a result was rolled.
- **A flat modifier in the notation.** A bonus is already a stat, and a stat can come from a formula, a feature or an item.

## Consequences

- A weapon's damage is one stat that reads `1d8` or `4d6dl1`, in the notation people write.
- A sixth value type for every read, copy and release to carry, and one more case in the stat table's constraint.
- Two kinds more in the formula union, each a place a rule can be wrong.
- German tables can write `2W6` and read it back as `2d6`; a client that wants the letter back changes it.

# Modelling a game system

How to say a game's numbers with Lorenzo's stats: what each piece does, the recipes for what the formula kinds do not say directly, and the traps. Lorenzo assumes no game: the examples below use invented names, and a library may hold the stats of several systems at once.

Everything here is as the API behaves today. It was checked against a local API; where a recipe stops working, the section says where.

## The pieces

- A **stat group** holds **stat definitions**. A definition has a name (unique in a library), a value type (`int`, `float`, `text`, `bool` or `enum`), and optional display fields: a unit, a sign, "adjustable in play", a pin, hints and, for `int` and `float`, a minimum and a maximum ([ADR 0014](../adr/0014-stats.md), [ADR 0103](../adr/0103-stat-tags-enum-values-and-mandatory-groups.md), [ADR 0278](../adr/0278-stat-definition-display-fields-order-and-patch.md), [ADR 0403](../adr/0403-stat-scales.md)). A `bool` is a tag. A definition's type and group never change; its name, unit, bounds and hints can.
- An entry holds a **value** of a definition: its own, one **inherited** from a parent, or one **computed** by a formula ([ADR 0276](../adr/0276-where-a-stat-value-comes-from.md)).
- An entry's **parents** (a prototype chain) are ordered. The closest value wins; at equal distance the stat groups the parents have acquired decide, then parent order ([ADR 0037](../adr/0037-effective-stat-resolution.md), [ADR 0266](../adr/0266-stat-tie-break-by-parent-order.md)). Values never add up along the chain.
- A **formula** is one of four kinds, set on an entry for a stat, and evaluated for the entry that is read, so a formula on a prototype answers for every entry below it ([ADR 0104](../adr/0104-computed-stats.md), [ADR 0126](../adr/0126-sum-formulas.md), [ADR 0127](../adr/0127-contents-formulas.md)):

| Kind | Result |
| --- | --- |
| `linear` | `source x multiplier + offset`, with a round mode (`none`, `floor`, `ceil`, `round`, `truncate`) |
| `sum` | `coefficient x stat` over up to 20 stats, plus an offset, with a round mode |
| `comparison` | a stat against a stat or a constant: a `bool`, or one of two text or enum values |
| `contents` | the sum of a stat times the quantity over what the entry directly contains |

  Coefficients and multipliers are constants. An `int` result needs a round mode unless every input is an `int` stat and every constant is whole. A `float` stat takes a JSON number with a decimal point (`3.0`, not `3`).

A formula can use another formula's stat, so a longer rule is a chain of named intermediate stats. A preview shows a candidate formula's value with its inputs before it is saved, and an explanation shows a stored one.

## Names that let systems share a library

A library has one definition per name, whatever the system. Two systems that both define `speed` share it, with one type and one unit.

- Keep a system's own stats under a prefix: `dnd_armor_class`, not `armor_class`. Two systems then sit side by side on one entry, and each system's prototype chain brings its own stats and formulas.
- Names the API reads keep one type and one unit for the whole library: `weight`, `height`, `price`, `rarity`, `hp`, `armor`, `size`, `carry_capacity`, `containment_capacity`, `max_item_size`, `binding`, `is_container` ([well-known stats](../reference/well-known-stats.md), [ADR 0390](../adr/0390-renaming-a-stat-and-an-enum-value.md)). They cannot be renamed. Choose their unit once.
- A unit is a string on the definition. Lorenzo does not convert between units; the same measure in two units is two stats, the second a `linear` formula of the first (see below).
- Changing a type or group is not possible, and a stat in use cannot be deleted. In a repository that others copy, settle types, groups and units before the first release.
- Put the stats that a weapons table should show in one group, and name that group in the library's sheet settings ([ADR 0281](../adr/0281-sheet-settings-and-the-sheet-read.md)); the table draws one column per stat of that group.

## Recipes

### A value from several sources

Values do not add up along the chain, so a bonus from a source is a stat of its own, and the total is a `sum`.

1. A stat for each source of the value: `might_base`, `might_race`, `might_class`, `might_misc`, all `int`.
2. A stored default of 0 for the bonuses on the base prototype.
3. On the base prototype, `might = sum(might_base, might_race, might_class, might_misc)`.
4. Each race or class entry stores its own bonus stat. Every being below the prototype has the total.

One bonus stat shared by several sources is read from the closest one only: a feat that sets the same stat as the race hides the race's value.

### A rule that steps evenly

A modifier that goes up by one for every two points, rounded down, is `linear(source, 0.5, -5, floor)`: 17 gives 3, 9 gives -1. A bonus that rises one step every four levels is `linear(level, 0.25, 1.75, floor)`: level 1 gives 2, level 5 gives 3. A level below the domain gives a result outside the rule, so give the source a minimum.

### A table with steps

Several steps of one input stat are a staircase. The step at threshold `t`, over an input from 0 to `X`, is

```
linear(input, multiplier = 1/K, offset = 1 - t/K, round_mode = floor)
```

which is 0 below `t` and 1 from `t` up, as long as `K` is larger than both `t` and `X - t`. Choose a `K` with a short decimal form (8, 10 or 16). The result is the step, and a second `linear` or `sum` turns it into the values:

```
tier   = linear(models, 0.125, 0.375, floor)     # 1 from 5 models, input 0 to 10
points = sum(tier x 80, offset 90)
```

Two thresholds are two step stats and a `sum`. Keep the input's minimum and maximum tight, since a value outside them breaks the steps. A table of irregular values, or one that depends on two inputs, is not reachable: store the values.

### A flag that changes a formula

A `bool` cannot be a formula input, and a coefficient is a constant, so "add the bonus if proficient" is not a product. Make the flag an **entry that carries the formula**:

- The base prototype has `stealth = linear(grace_mod, 1)`.
- A trait entry, `Trained in stealth`, has `stealth = sum(grace_mod, prof_bonus)` and is a parent of the being. Twice the bonus and half the bonus are two more trait entries (`sum` with coefficient 2, or 0.5 with `floor`).

When a default on the base prototype and a trait sit at the same distance from the being, parent order decides, and the base can win. Make the trait win by having it acquire a stat group of higher priority than the base's: set its stat with `acquire_group` on, in a group whose priority is higher.

### A condition that changes a number

A condition as a `bool` tag is shown, and changes nothing. To change a number, make the condition an entry (a parent) that stores the value, such as an armor bonus of 1. Two conditions on one stat do not add; one of them is read.

### Current and maximum

A current value and its maximum are two stats. Give the current one a minimum of 0, "adjustable in play", and the maximum as its hint, which the sheet shows as "3 of 9". The hint is a clue: nothing keeps the current value at or under the maximum, and nothing refills it.

A resource that is spent and refilled is easier as **spent and left**: `slots_spent` (adjustable, minimum 0), `slots_max` (stored), and `slots_left = sum(slots_max, slots_spent x -1)`. A refill is one write of 0. Spent above the maximum gives a negative `slots_left`; it is not clamped.

### Counting only what is worn or held

`contents` adds up every directly contained entry that has the stat, so a spare item that is only carried counts. Put what counts into its own container, and read the container: a `Worn` item inside the being has `worn_total = contents(armor_bonus)`, and the being has `worn_bonus = contents(worn_total)`. A container has to be an entry that the being directly contains; two levels need two formulas.

### An item with several profiles

A weapon with two profiles is a base item with one child item per profile. Each child inherits the shared stats and overrides the difference; the being holds one instance of each. The sheet shows one row each, ordered by name, so name the profiles to sort (`Carbine 1 standard`, `Carbine 2 overcharge`) and add a `profile` enum stat as a column. Child items of a held item are not shown on the sheet. Suffixed stats (`attacks_1`, `attacks_2`) give one row with all the columns.

### A rule with a parameter

An `int` stat with the unit `+` shows as "5 +": `lethal = 5`. A rule that is also a text of its own is an entry that the weapon has as a parent; the entry stores the default and the weapon overrides it. A `bool` rule is a chip on a being and shows as "-" in a weapons table, so give it a stat value of 1 if it has to show there.

### A value that depends on a class or tier

Where a table maps a tier to values (an experience value for a challenge rating), make an entry for each tier that stores the values, and let the thing have its tier entry as a parent. Changing the tier is changing the parent. Two tier entries at the same distance tie by parent order.

### The same measure in two units

A twin stat holds the converted value: `weight_kg = linear(weight, 0.45359237, 0, none)`, a `float` stat with the unit `kg`. Conversion is a constant per twin; a table of non-linear values is not.

## Traps

- **An unset input leaves the result unset.** A `sum` with one term without a value has no value, and the explanation of it is not found. Store a 0 on the base prototype for every optional term.
- **A default at the same distance as a trait.** See above: parent order decides, silently.
- **A direct value shadows an inherited formula.** Writing a stat on a being that has a formula only on a prototype stores an own value, and the formula no longer shows.
- **A computed value is never held to a minimum or maximum.** Bounds check what is written.
- **Equal-distance parents tie by order.** Two parents that give the same stat at the same distance give the first one's value.
- **A very long chain.** Rules a few steps deep are fine; a chain of hundreds of formulas can fail on read.

## What the formulas do not say

No `min`, `max` or clamp; no product of two stats; no `bool`, `enum` or `text` as input to arithmetic; no condition that gives a number; no AND or OR of conditions; no lookup table; no dice. The recipes above cover stepped tables, flags and tiers. For the rest, store the value on the entry (a cap, a total that depends on two stats) and let the author keep it current.

## What the sheet draws

Per stat group of the being, one line of cells (a `bool` is a chip only in the group named `tags`); a weapons table of the held items with a stat in the weapon group; the abilities of the library's ability type. Labels come from the stat name, and every stat with a value is shown, including the intermediate ones a chain makes. See [RFC 0043](../rfcs/0043-the-being-sheet.md), [ADR 0296](../adr/0296-being-stat-group.md) and [ADR 0283](../adr/0283-beings-sheet-play-stats-and-undo.md).

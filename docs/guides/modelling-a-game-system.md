# Modelling a game system

How to say a game's numbers with Lorenzo's stats: what each piece does, the recipes for what the formula kinds do not say directly, and the traps. Lorenzo assumes no game: the examples below use invented names, and a library may hold the stats of several systems at once.

Everything here is as the API behaves today. It was checked against a local API; where a recipe stops working, the section says where.

[RFC 0053](../rfcs/0053-formula-kinds-min-max-product-ratio-select-and-held-aggregation.md) adds formula kinds in four slices. Built so far: `min` and `max`, and a `bool` or an `enum` as an input of `linear`, `sum`, `min` and `max` ([ADR 0444](../adr/0444-min-max-and-a-bool-or-an-enum-as-a-number-in-a-formula.md)); `product` and `ratio`, which read them too ([ADR 0445](../adr/0445-product-and-ratio-formulas.md)); `select` ([ADR 0446](../adr/0446-select-formulas.md)); and the options of `contents` and the `active` switch of an item instance ([ADR 0447](../adr/0447-contents-options-and-the-active-switch.md)). RFC 0053 is built. It made three recipes unnecessary: the staircase for a table with steps is one `select`, a trait entry that carries a formula for a flag is a `product` with the flag, and a container for what is worn is `contents` over what is active. Where a recipe below is kept, it is for a library that has not moved, or says so.

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

## Several systems in one library

A library holds the stats of several game systems by giving each a **system** ([RFC 0052](../rfcs/0052-game-systems-in-one-library.md), [ADR 0448](../adr/0448-a-game-system-as-a-row.md)): a row with a short lowercase slug (`ds`, `pf`, `bitd`), a name and an optional root entry. Nothing is seeded and no system is special.

- **A stat group belongs to a system, or to none.** The names of the stats in a system's group start with its slug and an underscore (`ds_stamina`), checked on create and rename, so two systems never collide on a name; a stat of no system takes any name. A definition stays in the group it was made in, so its system is permanent.
- **A stat row says where it is from.** The entry read, the bulk read and the explanation give each stat its `group_id` and `system`; `?system=ds` on the reads narrows `stats` to those of no system and of `ds`. Values are still resolved over the whole prototype graph, so a formula of one system may read another's ([ADR 0450](../adr/0450-the-system-filter-on-the-stat-reads.md)).
- **What the API reads is a role, not a name** ([ADR 0449](../adr/0449-roles-the-api-reads-a-stat-by-what-it-is-for.md)): `weight`, `height`, `price`, `rarity`, `hp`, `armor`, `size`, `carry_capacity`, `containment_capacity`, `max_item_size`, `binding` and `is_container` for a stat, `physical`, `economic`, `destroyable`, `damaging` and `tags` for a group ([well-known stats](../reference/well-known-stats.md)). One stat holds each in a library, it must fit the types the role is read as, and it belongs to no system. A stat or group called after a free role takes it by default (`role: null` says none), and a holder can be renamed.
- A unit is a string on the definition. Lorenzo does not convert between units; the same measure in two units is two stats, the second a `linear` formula of the first (see below). A copy that merges a stat into the library's own with another unit or bounds says so (`warnings`), or asks first with `strict_units` ([ADR 0453](../adr/0453-repositories-carry-systems-and-templates.md)).
- Changing a type or group is not possible, and a stat in use cannot be deleted. In a repository that others copy, settle types, groups and units before the first release.
- A repository carries its systems, the system of each group and its templates; a copy joins a system by slug and keeps the library's name for it. Updates do not carry them yet.

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

`select` says a table in one formula (RFC 0053 slice K3, [ADR 0446](../adr/0446-select-formulas.md)): `proficiency = select(level, threshold, from 1 gives 2, from 5 gives 3, from 9 gives 4, otherwise 0)`, or by category `dex_bonus = select(armour, match, light gives dex_modifier, medium gives 2, heavy gives 0)`. The staircase below is how a table is said without it.

Several steps of one input stat are a staircase. The step at threshold `t`, over an input from 0 to `X`, is

```text
linear(input, multiplier = 1/K, offset = 1 - t/K, round_mode = floor)
```

which is 0 below `t` and 1 from `t` up, as long as `K` is larger than both `t` and `X - t`. Choose a `K` with a short decimal form (8, 10 or 16). The result is the step, and a second `linear` or `sum` turns it into the values:

```text
tier   = linear(models, 0.125, 0.375, floor)     # 1 from 5 models, input 0 to 10
points = sum(tier x 80, offset 90)
```

Two thresholds are two step stats and a `sum`. Keep the input's minimum and maximum tight, since a value outside them breaks the steps. A table of irregular values, or one that depends on two inputs, is not reachable: store the values.

### A cap and a floor

`min` is a cap and `max` is a floor, each of two to five stats or constants: `dex_bonus = min(dex_modifier, dex_cap)`, `hit_points_shown = max(hit_points, 0)`. A clamp is two formulas, one reading the other. A `bool` is 1 or 0 in these and in `linear` and `sum`, so a flag that adds a fixed bonus is a `sum` term with the bonus as its coefficient (`total = sum(proficient x 3, base)`), and `max(a, b)` of two flags is OR. An `enum` is the `sort_order` of its value: number the values as the rule needs them, and know that a formula that reads an enum stops its values being moved or removed (409).

### A flag that changes a formula

A flag times a stat is a `product`: `skill_bonus = product(trained, proficiency)`, where `trained` is a `bool` (1 or 0) and `proficiency` a stat. That makes the trait entry that carries a formula unnecessary for a flag. A bonus that comes from which trait a being has, rather than a flag on the being, is still an **entry that carries the formula**:

- The base prototype has `stealth = linear(grace_mod, 1)`.
- A trait entry, `Trained in stealth`, has `stealth = sum(grace_mod, prof_bonus)` and is a parent of the being. Twice the bonus and half the bonus are two more trait entries (`sum` with coefficient 2, or 0.5 with `floor`).

When a default on the base prototype and a trait sit at the same distance from the being, parent order decides, and the base can win. Make the trait win by having it acquire a stat group of higher priority than the base's: set its stat with `acquire_group` on, in a group whose priority is higher.

### A condition that changes a number

A condition as a `bool` tag is shown, and changes nothing. To change a number, make the condition an entry (a parent) that stores the value, such as an armor bonus of 1. Two conditions on one stat do not add; one of them is read.

### Current and maximum

A current value and its maximum are two stats. Give the current one a minimum of 0, "adjustable in play", and the maximum as its hint, which the sheet shows as "3 of 9". The hint is a clue: nothing keeps the current value at or under the maximum, and nothing refills it.

A resource that is spent and refilled is easier as **spent and left**: `slots_spent` (adjustable, minimum 0), `slots_max` (stored), and `slots_left = sum(slots_max, slots_spent x -1)`. A refill is one write of 0. Spent above the maximum gives a negative `slots_left`; it is not clamped.

### Counting only what is worn or held

`contents` takes options (RFC 0053 slice K4, [ADR 0447](../adr/0447-contents-options-and-the-active-switch.md)): `aggregate` (`sum`, `min`, `max`, `count`), `only_active`, `only_kind` (`item_instance`, or `feature_instance` for what a holder has as features), `where_stat_definition_id` (a `bool` stat of the held thing) and `if_none`. Armour class from what is worn is `max` over active item instances of `armor` with `if_none` 10; a dexterity cap is `min` over active armour of its cap; attunement used is `count` over active things `where` `requires_attunement`. An item instance has an `active` switch (on by default; an item with `starts_inactive` makes instances that start off), which its holder flips with `PATCH /item-instances/{id}` and which does not move, free or bind it. `min`, `max` and `count` ignore the stack count; a sum still multiplies by it.

The container recipe below is the way without the options: `contents` adds up every directly contained entry that has the stat, so a spare item that is only carried counts. Put what counts into its own container, and read the container: a `Worn` item inside the being has `worn_total = contents(armor_bonus)`, and the being has `worn_bonus = contents(worn_total)`. A container has to be an entry that the being directly contains; two levels need two formulas.

### A feature a character has, and what grants it

A spell, a feat, a boon, a class feature or a playbook move is an entry of the kind `feature` ([ADR 0454](../adr/0454-features-two-kinds-and-what-a-holder-has.md)): its stats, description and parents like any prototype, and its type is a category entry among its parents (a spell school, a feat group). What a being, an item instance or a group has of it is a **feature instance**, with the feature as its one parent, its own stats for what the holder keeps (`uses_spent`, `prepared`) and an `active` switch. `repeatable` lets a holder have it twice; `starts_inactive` makes its instances begin switched off.

A holder reads what its features give with `contents`, `only_kind` of `feature_instance`: a bonus total is `sum` of the bonus stat with `only_active`, a count of the features of a kind is `count` with `where` a flag, and a flag feature is a `product` factor.

A **grant rule** ([ADR 0455](../adr/0455-grant-rules-and-the-prerequisites-of-a-feature.md)) hangs on a source entry (a race, a class, an archetype, a feature, an item) and says what it entitles a holder to: all its options, or a choice between a minimum and a maximum (a number, or a stat of the holder such as `cantrips_known`), from an explicit list of features or from the features under a category. Its conditions are comparisons on the holder or on the source, all of which must hold (an OR is a second rule): "at level 3, one of these" is a rule on the class with `level >= 3`. A feature can carry **prerequisites** on the holder (`strength >= 13`) that every rule offering it respects. This replaces the chain of level prototypes whose parent is swapped at each level-up.

Nothing is granted until someone asks ([ADR 0456](../adr/0456-the-grants-read-apply-picks-and-revocation.md)): `GET /entities/{id}/grants` says what is due, what is open to choose and what is orphaned; `POST .../grants/apply` makes what is due, records the picks, and goes on while a granted feature brings more. A level-up is a client writing the level and calling apply. A pick is held to the rule's minimum, maximum and the options' prerequisites unless a GM overrides, and a grant that lasts while its source does (the default) is revoked, with what it gave, in the request that removes the source, switches it off, moves it away or writes a stat that one of its conditions reads; a `permanent` grant stays. A feature that was removed by hand is not made again.

A template slot of the kind `features` ([ADR 0457](../adr/0457-the-features-slot-of-a-template.md)) lists them on a sheet by type, with the stats you choose as columns.

### An item with several profiles

A weapon with two profiles is a base item with one child item per profile. Each child inherits the shared stats and overrides the difference; the being holds one instance of each. The sheet shows one row each, ordered by name, so name the profiles to sort (`Carbine 1 standard`, `Carbine 2 overcharge`) and add a `profile` enum stat as a column. Child items of a held item are not shown on the sheet. Suffixed stats (`attacks_1`, `attacks_2`) give one row with all the columns.

### A rule with a parameter

An `int` stat with the unit `+` shows as "5 +": `lethal = 5`. A rule that is also a text of its own is an entry that the weapon has as a parent; the entry stores the default and the weapon overrides it. A `bool` rule is a chip on a being and shows as "-" in a weapons table, so give it a stat value of 1 if it has to show there.

### A value that depends on a class or tier

Where a table maps a tier to values (an experience value for a challenge rating), make an entry for each tier that stores the values, and let the thing have its tier entry as a parent. Changing the tier is changing the parent. Two tier entries at the same distance tie by parent order.

### The same measure in two units

A twin stat holds the converted value: `weight_kg = linear(weight, 0.45359237, 0, none)`, a `float` stat with the unit `kg`. Conversion is a constant per twin; a table of non-linear values is not.

## Checking a vocabulary

The rules above do what they say, and some of what they say surprises. `GET /tenants/{id}/vocabulary-check` ([ADR 0458](../adr/0458-the-vocabulary-check-route-and-its-first-findings.md) to [0461](../adr/0461-warnings-on-the-writes-of-a-stat-and-of-a-formula.md)) reads a library and says where, without refusing or changing anything. Its findings: `unset-input` (a computed stat has no value because an input has none), `own-value-shadows-formula` (a value of an entry's own wins over a formula an ancestor holds), `tie` (two ancestors set a stat at one distance and the group priority, the parent order or the id decided; for one entry, with `entry_id`), and, as information, `computed-outside-scale`, `above-hint` and `formula-chain-depth`. Narrow it with `code`, `entry_id` or `parent_id` with `recursive`, `kind` and `stat_definition_id`. A write of a stat, a tag or a formula answers with the findings for what it wrote when it carries `warnings=true`.

## Traps

- **An unset input leaves the result unset.** A `sum` with one term without a value has no value, and the explanation of it is not found. Store a 0 on the base prototype for every optional term.
- **A default at the same distance as a trait.** See above: parent order decides, silently.
- **A direct value shadows an inherited formula.** Writing a stat on a being that has a formula only on a prototype stores an own value, and the formula no longer shows.
- **A computed value is never held to a minimum or maximum.** Bounds check what is written.
- **Equal-distance parents tie by order.** Two parents that give the same stat at the same distance give the first one's value.
- **A very long chain.** Rules a few steps deep are fine; a write that would chain more than 200 formulas is refused, and a stat at the end of a longer stored chain has no value ([ADR 0443](../adr/0443-the-api-answers-what-it-used-to-ignore-crash-on-or-return-out-of-order.md)).

## What the formulas do not say

Left to the author: a `text` stat as input to arithmetic (a `comparison` reads only numbers, and a `select` matches text), a rule that nests one kind inside another (a longer rule is a chain of named stats, up to 200), and dice. A `ratio` rounds its quotient at 28 digits. For anything else, store the value on the entry and let the author keep it current.

## What the sheet draws

A **template** says which stats and notes a sheet shows, under which labels and in what order, as data ([ADR 0451](../adr/0451-templates-a-sheet-as-data.md)): slots of `stats` (a group, or a list), `held` (a table of what the entry holds), `features` (what it has as features, by type), `information` and `tags`, and a filter of a kind and an ancestor entry. A campaign names its game system, and the sheet read draws from that system's template for the being when exactly one matches, or from the one asked for with `template_id` ([ADR 0452](../adr/0452-a-campaign-names-a-system-and-the-sheet-reads-a-template.md)).

Without a template, the library's own settings: per stat group of the being, one line of cells (a `bool` is a chip only in the group with the role `tags`); a weapons table of the held items with a stat in the weapon group; the abilities of the library's ability type. Labels come from the stat name, and every stat with a value is shown, including the intermediate ones a chain makes. See [RFC 0043](../rfcs/0043-the-being-sheet.md), [ADR 0296](../adr/0296-being-stat-group.md) and [ADR 0283](../adr/0283-beings-sheet-play-stats-and-undo.md).

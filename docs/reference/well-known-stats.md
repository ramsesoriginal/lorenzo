# Well-known stats

Stats are tenant data: a tenant defines its own stat groups and stat definitions, and the API doesn't hardcode a game system ([ADR 0014](../adr/0014-stats.md)). A few names are special anyway. The API reads them by name, so a tenant that defines one gets the behavior that goes with it, and one that doesn't define it simply doesn't.

This page lists them, and the recipes built on formulas ([ADR 0104](../adr/0104-computed-stats.md)) that make them useful. [RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) adds more names as its slices land.

## Names the API reads

| Name | Where | Type | What reads it |
| --- | --- | --- | --- |
| `is_container` | the `tags` stat group | `bool` | Item and item-instance responses' `is_container` field ([ADR 0066](../adr/0066-is-container-computed-field.md)): `true` or `false` when set, `true` when unset but something is inside, otherwise `null`. Clients use it to offer something as a container. |
| `weight` | items | number | What `carry_capacity` adds up ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md)), `× quantity` for a stack. |
| `size` | items | number | What `containment_capacity` adds up, and what `max_item_size` compares. |
| `carry_capacity` | a container or a being | number | A move may not make `Σ weight × quantity` of what's directly inside grow past it, checked on the container moved into and every container above it. |
| `containment_capacity` | a container | number | A move may not make `Σ size × quantity` of what's directly inside grow past it. |
| `max_item_size` | a container | number | Nothing whose `size` is over it goes in. |

Each is read as resolved, so a formula counts, and something without a `weight` or `size` counts as 0. A GM can move anyway ([ADR 0128](../adr/0128-capacity-and-moving-anyway.md)).

## Recipe: weight that adds up

A container weighs its own weight plus what's inside it, unless it's something like a bag of holding. With `sum` ([ADR 0126](../adr/0126-sum-formulas.md)) and `contents` ([ADR 0127](../adr/0127-contents-formulas.md)) formulas, that's data on a tenant's base prototypes, defined once:

| Where | Stat | Formula |
| --- | --- | --- |
| the base item prototype | `contents_weight` | `contents(weight)` |
| the base item prototype | `weight` | `sum(own_weight, contents_weight)` |
| a dagger | `own_weight` | `1`, a direct value |
| a Bag of Holding | `weight` | `15`, a direct value: its contents don't weigh on its carrier |
| the base character prototype | `carried_weight` | `contents(weight)` |
| the base character prototype | `carry_capacity` | `linear(strength × 15)` |
| the base character prototype | `worn_ac_bonus` | `contents(ac_bonus)`: only what's directly on the being, meaning equipped |

How it resolves:

- **A direct value beats an inherited formula**, so the Bag of Holding's `weight` of 15 wins over the base prototype's `sum` ([ADR 0037](../adr/0037-effective-stat-resolution.md)).
- **Something without a weight counts as 0** inside a container. An item without `own_weight` has no `weight`, and the container around it still adds up.
- **Stacks count by quantity**: 20 arrows weigh 20 times one arrow.
- **Everything inside counts**, including what a reader can't see.
- **A being is its own Equipped** (RFC 0030 §2): what's contained directly by a character is what it carries in hand, so `carried_weight` over the character is what it's carrying, containers and all.
- **Only what's contained counts.** Something a character owns that sits in no container is shown with its owner ([ADR 0123](../adr/0123-held-by-listing-and-the-equipped-column.md)), but it isn't physically on them, so it isn't in `carried_weight`.

A repository ([RFC 0024](../rfcs/0024-repositories.md)) can ship the recipe for its tenants to copy.

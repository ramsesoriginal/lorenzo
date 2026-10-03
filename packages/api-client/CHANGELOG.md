# Changelog

## 1.0.0 (2026-10-03)


### ⚠ BREAKING CHANGES

* **api:** weight, height, price, rarity, hp and armor on item and item-instance responses, and the values in physical_stats, economic_stats, destroyable_stats and damaging_stats, are now numbers (integer or float) instead of integers, so a stat stored as a float reads as itself and no longer as null (ADR 0141). A JSON reader is unaffected; a client with a strict integer type for these fields needs to widen it. Accepted in openapi-breaking-accepted.txt.
* **api:** weight, height, price, rarity, hp and armor on item and item-instance responses, and the values in physical_stats, economic_stats, destroyable_stats and damaging_stats, are now numbers (integer or float) instead of integers, so a stat stored as a float reads as itself and no longer as null (ADR 0141). A JSON reader is unaffected; a client with a strict integer type for these fields needs to widen it. Accepted in openapi-breaking-accepted.txt.
* **api:** item and item-instance responses no longer carry `is_magical` or `is_cursed` (ADR 0129), and the 403 for a non-GM's `override` is now `override-forbidden`.
* **api:** a formula in GET .../entities/{entity_id}/computed-stats and PUT .../computed-stats/{stat_definition_id} responses can now be `kind: "contents"`, and GET .../stat-definitions/{stat_definition_id}/dependents can report
* **api:** a formula in GET .../entities/{entity_id}/computed-stats and PUT .../computed-stats/{stat_definition_id} responses can now be `kind: "sum"`, and GET .../stat-definitions/{stat_definition_id}/dependents can report `kind: "sum"`.

### Features

* **account-hub:** shared API client and tenant slug editing ([eb3a6e8](https://github.com/ramsesoriginal/lorenzo/commit/eb3a6e8919a19c02fb5abf1365ff363a93541067))
* **account-hub:** use shared API client and edit tenant slugs ([e68e10b](https://github.com/ramsesoriginal/lorenzo/commit/e68e10b65458d55beca265092c21746d1a5972e1))
* **api-client:** one typed API client for loot-bot and inventory-web (ADR 0122) ([3e2e370](https://github.com/ramsesoriginal/lorenzo/commit/3e2e3702c99320ba3b02a9bec6a01a349ac2f2cc))
* **api-client:** one typed API client for loot-bot and inventory-web (ADR 0122) ([d623480](https://github.com/ramsesoriginal/lorenzo/commit/d6234807790cb416353346a4f896db6c72b3943f))
* **api:** binding, derived from where things are and who owns them, and a GM lifting it ([639ec6d](https://github.com/ramsesoriginal/lorenzo/commit/639ec6daad7bd81d60ed16a106e72723a31f567e)), closes [#283](https://github.com/ramsesoriginal/lorenzo/issues/283)
* **api:** capacity on every move, a GM's override, and keeping a deleted container's contents ([e33ba31](https://github.com/ramsesoriginal/lorenzo/commit/e33ba31ccee0ea92a414774e1e85cf53c55ee038))
* **api:** contents formulas, adding up a stat over what's inside ([bdd1a72](https://github.com/ramsesoriginal/lorenzo/commit/bdd1a72837c515e73336401f6b13c617cf2b33ea))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([8fc2034](https://github.com/ramsesoriginal/lorenzo/commit/8fc20340d0bcdb498ccbd6754e15a395932645a5))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([54348fc](https://github.com/ramsesoriginal/lorenzo/commit/54348fcd4a9570b501eeaf5dca9d0c021a15b855))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([1e1c273](https://github.com/ramsesoriginal/lorenzo/commit/1e1c273611f33d3780191ac9e15025c84f330601))
* **api:** give a container with what's inside it, or give only what's inside ([0b876b8](https://github.com/ramsesoriginal/lorenzo/commit/0b876b84372cdb540ea26bc7498b0b139744127f))
* **api:** hand a pack out in one request ([3b146b8](https://github.com/ramsesoriginal/lorenzo/commit/3b146b87d76000ef0b98aa2c633db3285dc7b500))
* **api:** list what a being holds, Equipped first (ADR 0123) ([4f20eca](https://github.com/ramsesoriginal/lorenzo/commit/4f20ecada340632843ec14512a97158d0570a1cc))
* **api:** make a GM's view of beings in no campaign a tenant setting ([0b879ac](https://github.com/ramsesoriginal/lorenzo/commit/0b879acd8f2deba8eedfa89b05fae059b124ba31))
* **api:** merge what's identical on a move, when asked (ADR 0133) ([eee2b3f](https://github.com/ramsesoriginal/lorenzo/commit/eee2b3f0aac702792b749019bf5e62aac4ee7204)), closes [#306](https://github.com/ramsesoriginal/lorenzo/issues/306)
* **api:** say who carries each controlled-by column (ADR 0134) ([0fd23ea](https://github.com/ramsesoriginal/lorenzo/commit/0fd23eaedaeb1d9f17b3c268e78a33fd96620891))
* **api:** set a stack down as single items, and a deleted container's contents with it (ADR 0132) ([243a00c](https://github.com/ramsesoriginal/lorenzo/commit/243a00cab9a7e52e18b6ab3b2d069c604655355e)), closes [#305](https://github.com/ramsesoriginal/lorenzo/issues/305)
* **api:** sum formulas, adding up several stats of one entity ([9a5aca6](https://github.com/ramsesoriginal/lorenzo/commit/9a5aca67f89679510e0657065f31b6698d829a06))
* **api:** the controlled-by listing, what a board shows (ADR 0130) ([07f81f2](https://github.com/ramsesoriginal/lorenzo/commit/07f81f2f68383fe3570860943bcf1b51e34d5111)), closes [#303](https://github.com/ramsesoriginal/lorenzo/issues/303)
* board refinements - who has a column, read-only marked, and your character opened for you (ADR 0134) ([189dd3d](https://github.com/ramsesoriginal/lorenzo/commit/189dd3d10f132990ff0a19ff615d58a72db97bc9))
* capacity on every move, a GM's "Move anyway", and a deleted container keeps its contents (RFC 0030 slice 6) ([8d37fa5](https://github.com/ramsesoriginal/lorenzo/commit/8d37fa545988b58254e152983040e204b44b8a1c))
* give a container with what's inside it, or only what's inside (RFC 0030 slice 3) ([d600b81](https://github.com/ramsesoriginal/lorenzo/commit/d600b81ba7e2bf85f283ff44fe13c73698e76d45))
* what a being holds, with an Equipped column that's always there (ADR 0123) ([7f6d4ca](https://github.com/ramsesoriginal/lorenzo/commit/7f6d4ca671e808777a7632ac7d526502879ba1fb))
* what a board shows - controlled columns, setting things down, and merging what's identical (RFC 0031) ([9838682](https://github.com/ramsesoriginal/lorenzo/commit/9838682e0c78784c49fbc7b882e56706b6968d92))

# Changelog

## 0.1.0 (2026-10-03)


### ⚠ BREAKING CHANGES

* **cli:** lorenzo pack give requires --owner (a being or group) and no longer takes --into; a being now has the pack put into its hands. A map with a "text" row under [pack_items] no longer loads: say "item" instead.
* **cli:** the plan JSON's pack.plain_text is now pack.unresolved.
* **api:** weight, height, price, rarity, hp and armor on item and item-instance responses, and the values in physical_stats, economic_stats, destroyable_stats and damaging_stats, are now numbers (integer or float) instead of integers, so a stat stored as a float reads as itself and no longer as null (ADR 0141). A JSON reader is unaffected; a client with a strict integer type for these fields needs to widen it. Accepted in openapi-breaking-accepted.txt.
* **cli:** the plan JSON's pack.plain_text is now pack.unresolved.
* **api:** weight, height, price, rarity, hp and armor on item and item-instance responses, and the values in physical_stats, economic_stats, destroyable_stats and damaging_stats, are now numbers (integer or float) instead of integers, so a stat stored as a float reads as itself and no longer as null (ADR 0141). A JSON reader is unaffected; a client with a strict integer type for these fields needs to widen it. Accepted in openapi-breaking-accepted.txt.

### Features

* **api:** four small additions for the CLI importer (ADR 0139-0142) ([8fc2034](https://github.com/ramsesoriginal/lorenzo/commit/8fc20340d0bcdb498ccbd6754e15a395932645a5))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([54348fc](https://github.com/ramsesoriginal/lorenzo/commit/54348fcd4a9570b501eeaf5dca9d0c021a15b855))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([1e1c273](https://github.com/ramsesoriginal/lorenzo/commit/1e1c273611f33d3780191ac9e15025c84f330601))
* **api:** hand a pack out in one request ([3b146b8](https://github.com/ramsesoriginal/lorenzo/commit/3b146b87d76000ef0b98aa2c633db3285dc7b500))
* **api:** make a GM's view of beings in no campaign a tenant setting ([0b879ac](https://github.com/ramsesoriginal/lorenzo/commit/0b879acd8f2deba8eedfa89b05fae059b124ba31))
* **cli:** a richer item taxonomy, and keeping what the sheet says (ADR 0146) ([7199b44](https://github.com/ramsesoriginal/lorenzo/commit/7199b446b58512403d6ad31c3c7d2b549c1b5520))
* **cli:** a richer item taxonomy, and keeping what the sheet says (ADR 0146) ([a6bdd8d](https://github.com/ramsesoriginal/lorenzo/commit/a6bdd8d33469f7435ac2d5f671c31ee91a0f54c7))
* **cli:** a richer item taxonomy, and keeping what the sheet says (ADR 0146) ([d4162fa](https://github.com/ramsesoriginal/lorenzo/commit/d4162fa473529b591facab27328cbfd582885d8e))
* **cli:** apps/cli with a generated Python client, ops table and auth (ADR 0137) ([55a559c](https://github.com/ramsesoriginal/lorenzo/commit/55a559ca3c15c5f2f3789f032578eafbcd496872))
* **cli:** apps/cli with a generated Python client, ops table and auth (ADR 0137) ([43b6908](https://github.com/ramsesoriginal/lorenzo/commit/43b69082f3038a723e3705e9b408b6c8f1ee5932)), closes [#328](https://github.com/ramsesoriginal/lorenzo/issues/328)
* **cli:** hand a pack out through the API ([59120ba](https://github.com/ramsesoriginal/lorenzo/commit/59120ba6bfa46675ec1ae0fe8081b7692f556c36)), closes [#379](https://github.com/ramsesoriginal/lorenzo/issues/379)
* **cli:** JS host - an embedded V8 in a token-free worker (ADR 0138) ([20fc6c3](https://github.com/ramsesoriginal/lorenzo/commit/20fc6c3394c6eae34ead73cd6185c6fe503595fe))
* **cli:** JS host - an embedded V8 in a token-free worker (ADR 0138) ([18844f8](https://github.com/ramsesoriginal/lorenzo/commit/18844f83e653f8a7e83de142916f573c50089b19)), closes [#329](https://github.com/ramsesoriginal/lorenzo/issues/329)
* **cli:** JS host - an embedded V8 in a token-free worker (ADR 0138) ([24483a3](https://github.com/ramsesoriginal/lorenzo/commit/24483a324584d9d4670cc0556ac5fa1193f4b71d)), closes [#329](https://github.com/ramsesoriginal/lorenzo/issues/329)
* **cli:** lorenzo plan and apply - the mapping file, identity, non-interactive contract (ADR 0144) ([1172784](https://github.com/ramsesoriginal/lorenzo/commit/1172784805fa9703bd5c28fdcc6f210737d716ae))
* **cli:** lorenzo plan and apply - the mapping file, identity, non-interactive contract (ADR 0144) ([2de47df](https://github.com/ramsesoriginal/lorenzo/commit/2de47df620e7feff180d2a369064febc6e20a5a9)), closes [#332](https://github.com/ramsesoriginal/lorenzo/issues/332)
* **cli:** lorenzo plan and apply - the mapping file, identity, non-interactive contract (ADR 0144) ([48f3c00](https://github.com/ramsesoriginal/lorenzo/commit/48f3c008ad169c43955981638ae5c2056c648247)), closes [#332](https://github.com/ramsesoriginal/lorenzo/issues/332)
* **cli:** lorenzo seed - the item taxonomy and stat definitions (ADR 0143) ([80ec0d7](https://github.com/ramsesoriginal/lorenzo/commit/80ec0d77aff9b4908617153d81db8bc0f36c3b14))
* **cli:** lorenzo seed - the item taxonomy and stat definitions (ADR 0143) ([00f477e](https://github.com/ramsesoriginal/lorenzo/commit/00f477e551506f9103802096e95ddc26a01839b7)), closes [#331](https://github.com/ramsesoriginal/lorenzo/issues/331)
* **cli:** lorenzo seed - the item taxonomy and stat definitions (ADR 0143) ([acce34b](https://github.com/ramsesoriginal/lorenzo/commit/acce34b7069dd37effa7c690817e960aa6a2acc7)), closes [#331](https://github.com/ramsesoriginal/lorenzo/issues/331)
* **cli:** lorenzo tenant create (ADR 0147) ([c4dfb9e](https://github.com/ramsesoriginal/lorenzo/commit/c4dfb9e858a5be4fe1ceeb8f58ffea788f7cc83d))
* **cli:** lorenzo tenant create (ADR 0147) ([92e65bb](https://github.com/ramsesoriginal/lorenzo/commit/92e65bb48a79a4c209186d492888eb68baa4e9d8))
* **cli:** pack contents in the description, and lorenzo pack give (ADR 0145) ([d58c89b](https://github.com/ramsesoriginal/lorenzo/commit/d58c89b9940833942e15a0627658731ba2377e47))
* **cli:** pack contents in the description, and lorenzo pack give (ADR 0145) ([f14c987](https://github.com/ramsesoriginal/lorenzo/commit/f14c9875a694ef413b36c0917ea604088304307f)), closes [#333](https://github.com/ramsesoriginal/lorenzo/issues/333)
* **cli:** pack contents in the description, and lorenzo pack give (ADR 0145) ([5be7837](https://github.com/ramsesoriginal/lorenzo/commit/5be7837ae6a7fb47cf37cd0e22d742c16637bdab)), closes [#333](https://github.com/ramsesoriginal/lorenzo/issues/333)


### Bug Fixes

* **cli:** ammo names what a weapon draws on, it doesn't make it a launcher ([d9f263a](https://github.com/ramsesoriginal/lorenzo/commit/d9f263a7d24d72a27fd9500c8e9ea4fd920fe377))
* **cli:** ammo names what a weapon draws on, it doesn't make it a launcher ([53036ae](https://github.com/ramsesoriginal/lorenzo/commit/53036aea3dd433ca72783e20262ce626b9dcfe59))


### Documentation

* **cli:** describe pack give on the API in the README and overview ([bc15924](https://github.com/ramsesoriginal/lorenzo/commit/bc159240ae0329f825149558e1e2ff99501db73c))
* **cli:** install line, README badges, and stale CLI references ([c8c6399](https://github.com/ramsesoriginal/lorenzo/commit/c8c6399dbe16134a2ba6ccb86b6e720f194e9f95))
* **cli:** install line, README badges, and the CLI as built in the docs that said otherwise ([588fc6f](https://github.com/ramsesoriginal/lorenzo/commit/588fc6f1b1c322d485d1adbc4e8d39f3fa089168))
* **cli:** no pipe inside the tenant create table row ([d2a557d](https://github.com/ramsesoriginal/lorenzo/commit/d2a557de85e4a400ca2c5004fa09566dc946353c))
* **cli:** README covers inspect and reading MPMB files ([d4b88a7](https://github.com/ramsesoriginal/lorenzo/commit/d4b88a7b2985243da1f1a7f904cc36f492ee771c))
* **cli:** README covers inspect and reading MPMB files ([0013170](https://github.com/ramsesoriginal/lorenzo/commit/0013170aebfc4526a0136876602f913641dbd668))
* **cli:** README token hint ([0518fbc](https://github.com/ramsesoriginal/lorenzo/commit/0518fbc687d6c13829d8c6d2431b2b2da3d1a372))
* incorporate remote decision branch updates ([299f797](https://github.com/ramsesoriginal/lorenzo/commit/299f79749128e5563ccf736f611ad43325ff93b6))
* merge current account-hub decision branch ([b7c32ad](https://github.com/ramsesoriginal/lorenzo/commit/b7c32adda873b27fbb4c429b4f74cc9e18468790))

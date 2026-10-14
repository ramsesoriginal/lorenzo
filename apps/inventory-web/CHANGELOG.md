# Changelog

## [2.0.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.1.0...inventory-web-v2.0.0) (2026-10-14)


### ⚠ BREAKING CHANGES

* **api:** the role in GET /tenants and GET /me/managed can now be 'author'; accepted in openapi-breaking-accepted.txt.

### Features

* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **api:** stat definition display fields, order and PATCH ([e32ed57](https://github.com/ramsesoriginal/lorenzo/commit/e32ed570b62c4dd116c3060c43f3042b814575d1))
* **api:** the author role, an admin gate and a table-driven route audit ([f25f832](https://github.com/ramsesoriginal/lorenzo/commit/f25f83225ffe1ee4223996c0c556dfa27ae23542)), closes [#545](https://github.com/ramsesoriginal/lorenzo/issues/545)
* **api:** the device-code flow sends devices to the hub the app-links registry names ([abd9410](https://github.com/ramsesoriginal/lorenzo/commit/abd94102b1500fd8b58512df65ef994f44ab512d))
* **bench:** keyboard moves for tabs (11 of 12) ([9ff4392](https://github.com/ramsesoriginal/lorenzo/commit/9ff4392b7781676e0311bf4288e32840c41971e0))
* **bench:** the main picture - show, choose, replace, remove (B8) ([c19d639](https://github.com/ramsesoriginal/lorenzo/commit/c19d6391da96ed3c44fb6928b309dfd21fb58004))
* **inventory-names:** share the importer's spelling table with the Unsorted view ([3e075a0](https://github.com/ramsesoriginal/lorenzo/commit/3e075a0e52f40d8de05c50489cb43c6a4e983234))
* **inventory-names:** share the importer's spelling table with the Unsorted view ([d6ffadd](https://github.com/ramsesoriginal/lorenzo/commit/d6ffadd8306302f4bdd8e7cc28e558492607306c))
* **inventory-web:** "Not in the list" and the unsorted badge ([a5f205d](https://github.com/ramsesoriginal/lorenzo/commit/a5f205d3a0c322f54ad5818b1fdbb2117e44f6c8))
* **inventory-web:** "Not in the list" and the unsorted badge ([8bee0e1](https://github.com/ramsesoriginal/lorenzo/commit/8bee0e1accf75c202dce5246256b030a2a1628dc))
* **inventory-web:** a notification bell in the header (ADR 0265) ([0f5265e](https://github.com/ramsesoriginal/lorenzo/commit/0f5265e4d6d61d66b7d64d7eb702da746b5a4dd1))
* **inventory-web:** edit an item's stat values ([3ec929a](https://github.com/ramsesoriginal/lorenzo/commit/3ec929a96bd80fac962a40790d427638271868c4))
* **inventory-web:** edit an item's stat values ([43084a2](https://github.com/ramsesoriginal/lorenzo/commit/43084a215eb5c327832bed88c418ec3aaf184ac3))
* **inventory-web:** hover, focus and tap previews on links in texts ([5d0fdb7](https://github.com/ramsesoriginal/lorenzo/commit/5d0fdb735ebcd60bb2f82d9467e846f1223672cc))
* **inventory-web:** my/ links resolve against the entity the text belongs to ([36d9123](https://github.com/ramsesoriginal/lorenzo/commit/36d9123a43ef33d8d2ee5f5c6c5d7d3d5b3e82b9))
* **inventory-web:** my/ links resolve against the entity the text belongs to (ADR 0240, slice 3) ([9f4d3a5](https://github.com/ramsesoriginal/lorenzo/commit/9f4d3a5f8d71a46dbe7782d6d73710131237d145))
* **inventory-web:** the bell's See all link comes from the app-links registry ([b9476db](https://github.com/ramsesoriginal/lorenzo/commit/b9476dbe59a592ac1e9eaa82c92ff010b0bb5168))
* **inventory-web:** the Unsorted view ([25c6c62](https://github.com/ramsesoriginal/lorenzo/commit/25c6c624771b1e189958d7573b16a64a317216d9))
* **inventory-web:** the Unsorted view ([284bbf6](https://github.com/ramsesoriginal/lorenzo/commit/284bbf670c8d80dc85a4113998c5003c7f294b61))
* **lorenzoscript:** a stat in a text, {weight} ([3bccede](https://github.com/ramsesoriginal/lorenzo/commit/3bccede76447f031ce553bd60e92bf5acda0a513))


### Bug Fixes

* **inventory-web:** a tap on a link opens its card and does not follow, focus does not pre-empt it ([889af93](https://github.com/ramsesoriginal/lorenzo/commit/889af93fdf025c22555123142a5199bbac505ddd))
* **inventory-web:** Escape closes the bell wherever the focus is ([06f551e](https://github.com/ramsesoriginal/lorenzo/commit/06f551e11b2a01ca371b22b64975d70e03b6a1a4))

## [1.1.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.0.0...inventory-web-v1.1.0) (2026-09-23)


### Features

* **brand:** swap Instrument Serif for Newsreader as the display typeface ([f9abfbd](https://github.com/ramsesoriginal/lorenzo/commit/f9abfbd4687eab3fd79d4ca59b3b4d333de5b3aa))
* **inventory-web:** add a button fallback for moving an item between containers ([99685f7](https://github.com/ramsesoriginal/lorenzo/commit/99685f7b7f037ad1ee67577d3ea2845fac5d72a9))
* **inventory-web:** add a button fallback for moving an item between containers ([c6bd50e](https://github.com/ramsesoriginal/lorenzo/commit/c6bd50eaed4bdce2c184f6c4108c99dae06ef471))
* **inventory-web:** debug button to mark three entities as containers ([f6ffddd](https://github.com/ramsesoriginal/lorenzo/commit/f6ffdddc9501208575145a2b29abbecca9be80a0))
* **inventory-web:** debug button to mark three entities as containers ([f6aee7e](https://github.com/ramsesoriginal/lorenzo/commit/f6aee7ed0bc3a3f0f46692ab8b53c1020ec1eb74))


### Bug Fixes

* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for OAuth callback ([9642c5a](https://github.com/ramsesoriginal/lorenzo/commit/9642c5a8ae5e7871a13587086db2b95ef8ba68e5))
* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for the OAuth callback ([690194e](https://github.com/ramsesoriginal/lorenzo/commit/690194eac234a974a2aae1f1a1c05e9913078367))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([790d7a2](https://github.com/ramsesoriginal/lorenzo/commit/790d7a2e399d132e5f507d433206aa7a3c557433))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([dc9c0df](https://github.com/ramsesoriginal/lorenzo/commit/dc9c0df2da3438406d3a78b8c230da0be6b69b22))
* **inventory-web:** follow every page of the item catalog, not just the first ([f20b767](https://github.com/ramsesoriginal/lorenzo/commit/f20b767717796c1cd0e0187d69e2ceed3ab0bc6f))
* **inventory-web:** follow every page of the item catalog, not just the first ([bfcc1c5](https://github.com/ramsesoriginal/lorenzo/commit/bfcc1c5a7842f5d8120914cc05e680dd4666ead5))
* **inventory-web:** tighten a handful of strings against the brand voice guide ([30dfc6e](https://github.com/ramsesoriginal/lorenzo/commit/30dfc6e9453924920dcfa13be8e0dce23924e835))
* **inventory-web:** tighten a handful of strings against the brand voice guide ([a902996](https://github.com/ramsesoriginal/lorenzo/commit/a902996170510edd38fc64f102ba2f563ccca6cf))

## 1.0.0 (2026-09-19)


### Features

* **inventory-web:** Authgear login/logout and a GET /me debug page ([99bd94d](https://github.com/ramsesoriginal/lorenzo/commit/99bd94dcc163fc5e1b17f7d38c64b539e59cca66))
* **inventory-web:** board item actions, tree ancestry, and GM being browsing ([c89cdd4](https://github.com/ramsesoriginal/lorenzo/commit/c89cdd4727ffd4cf523cbfd4fc9f5231251dff62))
* **inventory-web:** character picker on the board page ([66dd43c](https://github.com/ramsesoriginal/lorenzo/commit/66dd43c79fbc0deca469d2320f5c6a2755b2c735))
* **inventory-web:** debug tool to seed a demo character ([10b49ed](https://github.com/ramsesoriginal/lorenzo/commit/10b49ed67d3e69fa3a70f3bc001b7ed223ba4c5d))
* **inventory-web:** drag-and-drop item moves between containers ([d0d37cb](https://github.com/ramsesoriginal/lorenzo/commit/d0d37cb8fae81d5a5e9e12486d08c9d4614e299c))
* **inventory-web:** edit catalog items, including prototypes ([e263dc4](https://github.com/ramsesoriginal/lorenzo/commit/e263dc4c19fad3321aba45de29ca13785adecb44))
* **inventory-web:** GM item catalog/instance management and assignment ([e2456a7](https://github.com/ramsesoriginal/lorenzo/commit/e2456a7e6de2ad4b888c9146ff91bacb6154294e))
* **inventory-web:** GM item/instance management, board actions, and standalone item pages ([51b2eb3](https://github.com/ramsesoriginal/lorenzo/commit/51b2eb36aee955e52dcfec753e4a056fbff700e9))
* **inventory-web:** item detail view ([64bdb90](https://github.com/ramsesoriginal/lorenzo/commit/64bdb908c2ed1e982e17d41c10f63d69be50e828))
* **inventory-web:** read-only inventory board ([24b7bb7](https://github.com/ramsesoriginal/lorenzo/commit/24b7bb7713652350e738507a00033ff9e11f9189))
* **inventory-web:** scaffold apps/inventory-web with brand tokens ([b00a0f7](https://github.com/ramsesoriginal/lorenzo/commit/b00a0f797cd1081d5a724f021dce41e7cb4bc09e))
* **inventory-web:** standalone item page, slugs, and catalog caching ([ad80bb3](https://github.com/ramsesoriginal/lorenzo/commit/ad80bb341a4ae5183cc3d071d8ff60d46d3a8e93))
* **inventory-web:** static Astro app - auth, tenant/character pickers, drag-and-drop inventory board ([ea47ea5](https://github.com/ramsesoriginal/lorenzo/commit/ea47ea575c7bca6ea9007bafa4a1fb902d5495e0))
* **inventory-web:** tenant picker ([42e4931](https://github.com/ramsesoriginal/lorenzo/commit/42e4931d531d73babd8a6f407506620ad32cff07))
* **inventory-web:** use the API's is_container tag for the container ([fa1f0e4](https://github.com/ramsesoriginal/lorenzo/commit/fa1f0e4b5e4a73126eb9cdb2e9746cbd3b705e1b))


### Bug Fixes

* **inventory-web:** CI failures - markdownlint table style, vitest advisory ([7b30541](https://github.com/ramsesoriginal/lorenzo/commit/7b305419833851e0314f54ffea05d2cf00e82aae))
* **inventory-web:** fall back to the referenced-elsewhere heuristic for is_container ([060728e](https://github.com/ramsesoriginal/lorenzo/commit/060728e106ae67f64c14157c03d45e81681ef8fc))
* **inventory-web:** unscope styles that target client-created elements ([629673d](https://github.com/ramsesoriginal/lorenzo/commit/629673db99998d6da871d47a33573780645a046b))
* **inventory-web:** use the API's real is_container/title fields ([eec731d](https://github.com/ramsesoriginal/lorenzo/commit/eec731da7fd7a38451f09b7b621640f9e23f8711))

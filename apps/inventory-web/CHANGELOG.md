# Changelog

## [2.0.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.1.0...inventory-web-v2.0.0) (2026-10-03)


### ⚠ BREAKING CHANGES

* **api:** `slug` on POST /tenants/{tenant_id}/item-instances must now match `^[A-Za-z0-9][A-Za-z0-9_-]*$` and be at most 100 characters; anything else is a 422. Slugs already stored are untouched and still resolve.

### Features

* **api-client:** one typed API client for loot-bot and inventory-web (ADR 0122) ([3e2e370](https://github.com/ramsesoriginal/lorenzo/commit/3e2e3702c99320ba3b02a9bec6a01a349ac2f2cc))
* **api-client:** one typed API client for loot-bot and inventory-web (ADR 0122) ([d623480](https://github.com/ramsesoriginal/lorenzo/commit/d6234807790cb416353346a4f896db6c72b3943f))
* **api:** computed stats - linear and comparison formulas (ADR 0104) ([ef4953a](https://github.com/ramsesoriginal/lorenzo/commit/ef4953a71f707408f822ae41dc23837c27935b58))
* **api:** computed stats - linear and comparison formulas (ADR 0104) ([67ba505](https://github.com/ramsesoriginal/lorenzo/commit/67ba5052617fa6ec7960d8d049a261d275576d1b)), closes [#217](https://github.com/ramsesoriginal/lorenzo/issues/217)
* **api:** copy a repository into a tenant, bridges included (ADR 0119, 0120) ([ede5c93](https://github.com/ramsesoriginal/lorenzo/commit/ede5c9354f7d78cacd2190976b8ea7474d42e6d1))
* **api:** editable information and description payloads (ADR 0101) ([348f3b6](https://github.com/ramsesoriginal/lorenzo/commit/348f3b668ca6f084074419f9dd4df1633b3d757e))
* **api:** entity slugs and batch slug resolve (RFC 0027 stage 5) ([689b13b](https://github.com/ramsesoriginal/lorenzo/commit/689b13b6d4b4b158fcd2f87551d87e98a80c65de))
* **api:** four small additions for the CLI importer (ADR 0139-0142) ([8fc2034](https://github.com/ramsesoriginal/lorenzo/commit/8fc20340d0bcdb498ccbd6754e15a395932645a5))
* **api:** hand over on give, stacks leave containers into their owner, players read the catalog (ADR 0115, 0116) ([9a895fb](https://github.com/ramsesoriginal/lorenzo/commit/9a895fbcdaad73abcae8d87f7f06d026a5012697))
* **api:** hold item-instance creation slugs to RFC 0027's grammar ([516ee49](https://github.com/ramsesoriginal/lorenzo/commit/516ee4960381adafc3223ead76cb441f1c072032))
* **api:** items inherit descriptions and pictures; stats say if they are own (ADR 0111) ([512cd2a](https://github.com/ramsesoriginal/lorenzo/commit/512cd2ac3af46a449b4fff875e26a46f6d69863f))
* **api:** merge what's identical on a move, when asked (ADR 0133) ([eee2b3f](https://github.com/ramsesoriginal/lorenzo/commit/eee2b3f0aac702792b749019bf5e62aac4ee7204)), closes [#306](https://github.com/ramsesoriginal/lorenzo/issues/306)
* **api:** player knowers, knower listing, and the entity information list (ADR 0109) ([1178ae7](https://github.com/ramsesoriginal/lorenzo/commit/1178ae77af0cd8f519b6e1046d4a9b30e251e364))
* **api:** player knowers, knower listing, and the entity information list (ADR 0109) ([0e15cb9](https://github.com/ramsesoriginal/lorenzo/commit/0e15cb9ea16f49758264e134ab51fbb2a6130d4c)), closes [#230](https://github.com/ramsesoriginal/lorenzo/issues/230)
* **api:** repositories — grants, gated read, copy, bridges, updates (RFC 0024, ADR 0117-0121) ([d3b7644](https://github.com/ramsesoriginal/lorenzo/commit/d3b7644caf8fc731324363b9133bbed8a30751d9))
* **api:** repository contributions, dry runs, and copying again (ADR 0119, 0121) ([9b1d1a4](https://github.com/ramsesoriginal/lorenzo/commit/9b1d1a4472e735c42b433cd373429e313453e66e))
* **api:** repository contributions, dry runs, and copying again (ADR 0119, 0121) ([a6ab1d0](https://github.com/ramsesoriginal/lorenzo/commit/a6ab1d05fab2c5215b091279946608b19abec488))
* **api:** repository grants and the gated cross-tenant read (ADR 0118) ([8002569](https://github.com/ramsesoriginal/lorenzo/commit/800256995e8a39d2a3537a0234d8395df9682f97)), closes [#265](https://github.com/ramsesoriginal/lorenzo/issues/265)
* **api:** repository tenants - immutable kind, no campaigns, publishing (ADR 0118) ([14cde84](https://github.com/ramsesoriginal/lorenzo/commit/14cde84b13ab772cf8449909c9b9c87967cc40bb)), closes [#265](https://github.com/ramsesoriginal/lorenzo/issues/265)
* **api:** repository updates and re-sync (ADR 0121) ([1037204](https://github.com/ramsesoriginal/lorenzo/commit/1037204d00950963b7b72c3a03fd8e88d3e1b7ad)), closes [#268](https://github.com/ramsesoriginal/lorenzo/issues/268)
* **api:** stat tag endpoints, enum values, and mandatory groups (ADR 0103) ([92298fd](https://github.com/ramsesoriginal/lorenzo/commit/92298fdfd120f2f227ca0f739f6d7a154ff28da1))
* board refinements - who has a column, read-only marked, and your character opened for you (ADR 0134) ([189dd3d](https://github.com/ramsesoriginal/lorenzo/commit/189dd3d10f132990ff0a19ff615d58a72db97bc9))
* capacity on every move, a GM's "Move anyway", and a deleted container keeps its contents (RFC 0030 slice 6) ([8d37fa5](https://github.com/ramsesoriginal/lorenzo/commit/8d37fa545988b58254e152983040e204b44b8a1c))
* give a container with what's inside it, or only what's inside (RFC 0030 slice 3) ([d600b81](https://github.com/ramsesoriginal/lorenzo/commit/d600b81ba7e2bf85f283ff44fe13c73698e76d45))
* groups own things, and moving something isn't giving it away (ADR 0124) ([128bbde](https://github.com/ramsesoriginal/lorenzo/commit/128bbde26a55a1f7b13d4ecb6fbbb1c7c248a5db))
* hand items over on give, stacks leave containers whole, players read the catalog (ADR 0115, 0116) ([8bc12a1](https://github.com/ramsesoriginal/lorenzo/commit/8bc12a17e9319efd16d86e1f2c5ebbf17a61c1e7))
* **inventory-web:** ask a GM to move anyway when a move doesn't fit ([8b2c22f](https://github.com/ramsesoriginal/lorenzo/commit/8b2c22f28133d50767694e723822b3ba48f55d8f)), closes [#282](https://github.com/ramsesoriginal/lorenzo/issues/282)
* **inventory-web:** board columns, cards, and item dialog from templates ([8eb1d1c](https://github.com/ramsesoriginal/lorenzo/commit/8eb1d1cd79c2c094b8563ccda026d3df975f86f8))
* **inventory-web:** bound marks, and a GM's give or move anyway, lifting a binding ([6e84134](https://github.com/ramsesoriginal/lorenzo/commit/6e84134e2630aa49f7eab2917a740923bf5f9d88)), closes [#283](https://github.com/ramsesoriginal/lorenzo/issues/283)
* **inventory-web:** call tenants libraries, and open a user's only one directly ([fbf980f](https://github.com/ramsesoriginal/lorenzo/commit/fbf980fb6cfef4571f217f844e32c39ca4f9a144))
* **inventory-web:** edit item descriptions with the LorenzoScript editor ([267a024](https://github.com/ramsesoriginal/lorenzo/commit/267a024701e45fe660ca87513ed29cb2adf8bad8))
* **inventory-web:** end-to-end tests, slugs, and players' notes (ADR 0113, 0114) ([83ef058](https://github.com/ramsesoriginal/lorenzo/commit/83ef058fd144b5f47d9c34da1b29c5e68e5cd70a))
* **inventory-web:** give a container with what's inside, or only what's inside ([2368a4a](https://github.com/ramsesoriginal/lorenzo/commit/2368a4ad4736549bd0bb689748a674888c0a11ba))
* **inventory-web:** GMs set slugs, prefilled with the first free one (ADR 0113) ([61be0cc](https://github.com/ramsesoriginal/lorenzo/commit/61be0cc2fdce672e3debccc306cf02e27a21d691))
* **inventory-web:** GMs set slugs, prefilled with the first free one (ADR 0113) ([375f74a](https://github.com/ramsesoriginal/lorenzo/commit/375f74ad6012983a173337d1d2bba8d1749fbdb7))
* **inventory-web:** groups get boards and can be given things (ADR 0124) ([e00b6c5](https://github.com/ramsesoriginal/lorenzo/commit/e00b6c55b797476220b70ad946462083507e6d44))
* **inventory-web:** hand items over, carry stacks out of containers, and the catalog for players (ADR 0115, 0116) ([903727b](https://github.com/ramsesoriginal/lorenzo/commit/903727bdc1440a70993619ef2390ce19b0b398a0))
* **inventory-web:** hand items over, carry stacks out of containers, and the catalog for players (ADR 0115, 0116) ([1639c92](https://github.com/ramsesoriginal/lorenzo/commit/1639c92de3d215340c87cd48cb12b41e60e8f136))
* **inventory-web:** header navigation, account, and tenant switcher ([4b5b7b6](https://github.com/ramsesoriginal/lorenzo/commit/4b5b7b627a097bef3b26501bb525915e57792216))
* **inventory-web:** library icons, and a library switcher in the header ([b93ebee](https://github.com/ramsesoriginal/lorenzo/commit/b93ebeef1d24bba0db39d17c18b0983b3139f40c))
* **inventory-web:** LorenzoScript descriptions and editor (RFC 0027 stage 6) ([3a8c195](https://github.com/ramsesoriginal/lorenzo/commit/3a8c19556fe7c2f32e15ca2ff1fcecfc81c80ccd))
* **inventory-web:** players add notes to their items (ADR 0113) ([e4fa3f3](https://github.com/ramsesoriginal/lorenzo/commit/e4fa3f388c531acf11da3abe3075dd11390b9128))
* **inventory-web:** players add notes to their items (ADR 0113) ([9047ce1](https://github.com/ramsesoriginal/lorenzo/commit/9047ce1b4b0e741ed20c934698b41d068871c8ce))
* **inventory-web:** render descriptions as LorenzoScript ([55ef866](https://github.com/ramsesoriginal/lorenzo/commit/55ef866e8b76c5d4799b110fc262073b9dd075e3))
* **inventory-web:** set things down, a stack as single items after asking (ADR 0132) ([6a249f7](https://github.com/ramsesoriginal/lorenzo/commit/6a249f796b1e0eb3be588714ab4895fe43c8c467)), closes [#305](https://github.com/ramsesoriginal/lorenzo/issues/305)
* **inventory-web:** show the whole item, and edit its descriptions, tags, and information ([8c77579](https://github.com/ramsesoriginal/lorenzo/commit/8c77579d5b6b181fb08364f7769a06d97afafafb))
* **inventory-web:** show what an item is mentioned in ([109c07a](https://github.com/ramsesoriginal/lorenzo/commit/109c07afe8ca23dc7ab2797b6763fbe59c73c8a7))
* **inventory-web:** slugs wherever an address takes an id (ADR 0135) ([040776b](https://github.com/ramsesoriginal/lorenzo/commit/040776bb819f6ad8de29676802eed1c07c0b04bc))
* **inventory-web:** slugs wherever an address takes an id (ADR 0135) ([5ce557f](https://github.com/ramsesoriginal/lorenzo/commit/5ce557fe99c0d445926854e5c6889322e3d1c5f6)), closes [#321](https://github.com/ramsesoriginal/lorenzo/issues/321)
* **inventory-web:** stack what's identical on every move, with no Undo after a merge (ADR 0133) ([74b14fd](https://github.com/ramsesoriginal/lorenzo/commit/74b14fde388a1110811388f3295b3dc9679bb498)), closes [#306](https://github.com/ramsesoriginal/lorenzo/issues/306)
* **inventory-web:** the board on controlled-by, every column in one row (ADR 0131) ([af90d72](https://github.com/ramsesoriginal/lorenzo/commit/af90d72ccb8144a4a0c794bc052201671b54f0c3)), closes [#304](https://github.com/ramsesoriginal/lorenzo/issues/304)
* **inventory-web:** the board shows what a being holds, Equipped first (ADR 0123) ([2aa333c](https://github.com/ramsesoriginal/lorenzo/commit/2aa333c11bc8d5a362c0499730edbe9a80887873))
* **inventory-web:** the whole item - view, description titles, tags, information (ADR 0112) ([f8f61c3](https://github.com/ramsesoriginal/lorenzo/commit/f8f61c39dd540a7d0d9a6d4a838aeab1a70a1fba))
* **inventory-web:** who has a column, a moved container's note kept right, and your character opened for you (ADR 0134) ([ce5e01a](https://github.com/ramsesoriginal/lorenzo/commit/ce5e01a272a9b4e9754c9c8c353d30e04867ae95))
* **loot-bot:** /inventory and /inspect show what a character holds (ADR 0123) ([ed91615](https://github.com/ramsesoriginal/lorenzo/commit/ed916153a3f6116346053a479cc6bc89a7746ae3))
* LorenzoScript - Markdown for descriptions, editor, slugs, and backlinks (RFC 0027) ([e1877c5](https://github.com/ramsesoriginal/lorenzo/commit/e1877c577fad6c684d692726b3819c43cb172dd2))
* LorenzoScript references and backlinks (RFC 0027 stage 7) ([d9e7ca9](https://github.com/ramsesoriginal/lorenzo/commit/d9e7ca949569a5b3942032aace3ee9541a65ed2b))
* the whole item - inherited descriptions, one item view, and editing in inventory-web (ADR 0111, 0112) ([b26e3f2](https://github.com/ramsesoriginal/lorenzo/commit/b26e3f2d82288895a163bb1913102d313a55e0fd))
* what a being holds, with an Equipped column that's always there (ADR 0123) ([7f6d4ca](https://github.com/ramsesoriginal/lorenzo/commit/7f6d4ca671e808777a7632ac7d526502879ba1fb))
* what a board shows - controlled columns, setting things down, and merging what's identical (RFC 0031) ([9838682](https://github.com/ramsesoriginal/lorenzo/commit/9838682e0c78784c49fbc7b882e56706b6968d92))


### Bug Fixes

* **api:** keep ItemInstanceCreate.slug's existing contract ([6d05826](https://github.com/ramsesoriginal/lorenzo/commit/6d05826878a9b6d88fa2962b15b52ba884c92c05))
* **inventory-web:** ignore Astro's preview lock in the e2e launcher ([b363781](https://github.com/ramsesoriginal/lorenzo/commit/b363781e0713e7bdff728a71cd67ace7e0d2a3aa))
* **inventory-web:** offer "Also give what's inside" only for a container with something in it, and steady the e2e runs ([21699f0](https://github.com/ramsesoriginal/lorenzo/commit/21699f00ea3609254dc78fd136c51357d9bd8f38)), closes [#304](https://github.com/ramsesoriginal/lorenzo/issues/304)
* **inventory-web:** offer Undo after a give only when it can succeed (ADR 0124) ([6429d4c](https://github.com/ramsesoriginal/lorenzo/commit/6429d4c7f00331ecc77c8d3cb63e4e8fc6654646))
* **inventory-web:** stop the e2e preview server with the run on Windows ([97ec112](https://github.com/ramsesoriginal/lorenzo/commit/97ec112d15b21849b6cb29c7e97018a70db090c9))
* **inventory-web:** the fake Authgear only serves and returns to the site ([3b8ead1](https://github.com/ramsesoriginal/lorenzo/commit/3b8ead1f755a2ac0d9a05bf9421c1736b297990e))
* **inventory-web:** what the end-to-end tests found (ADR 0114) ([fd67b82](https://github.com/ramsesoriginal/lorenzo/commit/fd67b821643fedde8173ce3ea931334dee3b8af5))
* TypeScript callers send the fields the API's new defaults make required ([01df965](https://github.com/ramsesoriginal/lorenzo/commit/01df965a38d0f7ee495b28895d433e230fb22b1c))
* TypeScript callers send the fields the API's new defaults make required ([b37b777](https://github.com/ramsesoriginal/lorenzo/commit/b37b7777cb4e31a83525ede5720e7ca834b05533))

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

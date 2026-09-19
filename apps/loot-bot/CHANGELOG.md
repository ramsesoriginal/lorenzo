# Changelog

## [0.3.0](https://github.com/ramsesoriginal/lorenzo/compare/loot-bot-v0.2.0...loot-bot-v0.3.0) (2026-09-19)


### Features

* **loot-bot:** /give-bulk - give several items at once, no API change ([3ed9a23](https://github.com/ramsesoriginal/lorenzo/commit/3ed9a23d13853be650428bc2c83d2f3fcb0a8c88))
* **loot-bot:** /help - list every command, or one command's full options ([3d2158f](https://github.com/ramsesoriginal/lorenzo/commit/3d2158f3283393311550bfe82e92776975c94bdb))
* **loot-bot:** /inventory gains an optional search filter ([e8be6af](https://github.com/ramsesoriginal/lorenzo/commit/e8be6afd9433ed0130e71b871cfbec631712b1ae))
* **loot-bot:** /merge and /rename - inventory hygiene, no API change ([84e0311](https://github.com/ramsesoriginal/lorenzo/commit/84e0311b81e009ad9bd9c5647b1044979fdf6e12))
* **loot-bot:** /move and /set-current narrow container suggestions to is_container ([bfc6a4d](https://github.com/ramsesoriginal/lorenzo/commit/bfc6a4d0e8c023fee289ae0797fb835e820908d8))
* **loot-bot:** /move-bulk, /add-to-group, /add-channel-to-group ([4ad3944](https://github.com/ramsesoriginal/lorenzo/commit/4ad3944963d77e49aa41960bfd8b98e52ecb3b3c))
* **loot-bot:** /my-groups - list which groups your characters belong to ([83443a3](https://github.com/ramsesoriginal/lorenzo/commit/83443a3cac536a185269484d27002c2f1e342e3f))
* **loot-bot:** /pending-claims - server-wide outstanding-claims summary ([b2cb372](https://github.com/ramsesoriginal/lorenzo/commit/b2cb372b3ba73e00d9042a2e2e4d4989673f1a8c))
* **loot-bot:** /undo - self-service undo for give/reassign/move/rename/merge ([6d9bfa3](https://github.com/ramsesoriginal/lorenzo/commit/6d9bfa3b939e9564856b2ab8201423f921af22d0))
* **loot-bot:** add /whoami and /introduce, integrating apps/api's profile expansion ([3046a11](https://github.com/ramsesoriginal/lorenzo/commit/3046a11eb7dd4bfe138d48db3c77ca51cb4a11a2))
* **loot-bot:** auto-set a player's sole character as current on link ([a09b270](https://github.com/ramsesoriginal/lorenzo/commit/a09b2706f1d19b6a9e878f8ff53ace95169a37a4))
* **loot-bot:** GM toolkit - /inspect, /confiscate, /reassign ([f0f2811](https://github.com/ramsesoriginal/lorenzo/commit/f0f28117f1c989ad0aa8622e82e98bb9ac2ff7a6))
* **loot-bot:** GM toolkit, inventory hygiene, groups, and /help ([04521f4](https://github.com/ramsesoriginal/lorenzo/commit/04521f44e2165cdf35bd0de7e806d57d78c77b72))
* **loot-bot:** integrate ADR 0060's profile fields into /whoami, add /introduce ([49d378b](https://github.com/ramsesoriginal/lorenzo/commit/49d378bf06d422a9744012a48c24dcb47de4d21a))
* **loot-bot:** per-channel preferences, drop clear-claims, need/greed claims ([c27713f](https://github.com/ramsesoriginal/lorenzo/commit/c27713f834624df543b88df1f4255c2d6004ea00))

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/loot-bot-v0.1.0...loot-bot-v0.2.0) (2026-09-17)


### Features

* **loot-bot:** /award command - GM awards a new item to a character ([86cd5b2](https://github.com/ramsesoriginal/lorenzo/commit/86cd5b28c9b4eedcfb95957643429e16477092a6))
* **loot-bot:** /drop accepts a slug, applies claims via bulk-assign ([c405d3a](https://github.com/ramsesoriginal/lorenzo/commit/c405d3adebf706a553cbcbd73900b01f74724f4b))
* **loot-bot:** /drop command - loot drop, take, claim/unclaim, apply claims ([3e8c497](https://github.com/ramsesoriginal/lorenzo/commit/3e8c497f1e531a53386c507b6edc21f55e65d781))
* **loot-bot:** /give — loot-splitting against the real write API ([ca0b43d](https://github.com/ramsesoriginal/lorenzo/commit/ca0b43de2e5214e5a60ba32745853fbcb3be107f))
* **loot-bot:** /give and /drop's take use split-with-owner in one call ([696e220](https://github.com/ramsesoriginal/lorenzo/commit/696e220b7eb3bb0d0ea01579602e4217dad1a103))
* **loot-bot:** /inventory command ([e49179c](https://github.com/ramsesoriginal/lorenzo/commit/e49179c147c8d6be204118bf8180d0e1e6a8ad0d))
* **loot-bot:** /item command - display an item's description, stats, and notes ([3c15957](https://github.com/ramsesoriginal/lorenzo/commit/3c15957a9a3b35730d501ac935816a8b66680e73))
* **loot-bot:** /move and /note commands - manage inventory ([4ffd12b](https://github.com/ramsesoriginal/lorenzo/commit/4ffd12b5b3710e131d128d1891d0238045af9712))
* **loot-bot:** /note gains a group-visibility option ([cae25ae](https://github.com/ramsesoriginal/lorenzo/commit/cae25ae2dd52626660ba858e4b92aeedffd224d4))
* **loot-bot:** /set-current command ([a2d38eb](https://github.com/ramsesoriginal/lorenzo/commit/a2d38eb9586581d080ff1dfafcaef1da04e9e80d))
* **loot-bot:** /unlink command ([333a6c9](https://github.com/ramsesoriginal/lorenzo/commit/333a6c96e83b8cb2c709232772411a606ed6ed83))
* **loot-bot:** bot process skeleton - config, logging, http server, ping ([def6e18](https://github.com/ramsesoriginal/lorenzo/commit/def6e180159f0dd1135ca9555c7459a3e47d42f7))
* **loot-bot:** bot's own Postgres role, schema, and linked-account storage ([1bcb9db](https://github.com/ramsesoriginal/lorenzo/commit/1bcb9db1510a20556ef4065cfbb1ef7929d42791))
* **loot-bot:** capture/send ETag and If-Match in the Lorenzo API client ([65ccd50](https://github.com/ramsesoriginal/lorenzo/commit/65ccd50e058b09d63f9aebc82704e5d843af6267))
* **loot-bot:** Discord account linking via Authgear OAuth + PKCE ([1ac5336](https://github.com/ramsesoriginal/lorenzo/commit/1ac53362ad5e8c06b37a463dffb5a5490873de9c))
* **loot-bot:** Discord bot for account linking, inventory, and loot management ([ad6ca12](https://github.com/ramsesoriginal/lorenzo/commit/ad6ca12bb3cbcdf8ca02b5885826dc260521564f))
* **loot-bot:** extend the API client for apps/api 0.4.0's new capabilities ([941fc18](https://github.com/ramsesoriginal/lorenzo/commit/941fc18561b90c1235402da542e142c1c26f41c3))
* **loot-bot:** generic select-menu/button/modal dispatch on Command ([a991ae8](https://github.com/ramsesoriginal/lorenzo/commit/a991ae852193124ec88e441883c7ad2440c3bc0b))
* **loot-bot:** getGmCampaignIds, listItems, createItemInstance client methods ([1634acf](https://github.com/ramsesoriginal/lorenzo/commit/1634acf6a903ba6584300a14a83dcb302bb71b70))
* **loot-bot:** getItemInstancesByContainer client method ([3b570b0](https://github.com/ramsesoriginal/lorenzo/commit/3b570b08b64e32b3bac8d30f1a2eab55109b0618))
* **loot-bot:** getMyItemInstances/getEntity client methods ([a058972](https://github.com/ramsesoriginal/lorenzo/commit/a058972dfb8736f1e73cd41b4e4999f790ae26ef))
* **loot-bot:** isCampaignGm client method ([8cc7ad2](https://github.com/ramsesoriginal/lorenzo/commit/8cc7ad2d5b0782f3fa4e3440d97a2339b4fd4829))
* **loot-bot:** loot_drop/loot_claim tables and query functions ([3131c43](https://github.com/ramsesoriginal/lorenzo/commit/3131c431365a182326a56f80007b4fdee44c83f5))
* **loot-bot:** player_preference table - current character/container storage ([98a5974](https://github.com/ramsesoriginal/lorenzo/commit/98a5974e9aa630f3296deea316db9076c7851978))
* **loot-bot:** regenerate the API client against the real GET /me shape ([84656fd](https://github.com/ramsesoriginal/lorenzo/commit/84656fd749cce348e43ebaa1fb773eb433d47f31))
* **loot-bot:** regenerate the client against the full CRUD API, show stack quantity ([068a4ad](https://github.com/ramsesoriginal/lorenzo/commit/068a4adc888d6ed66ad2e93b74708b0baba6a4b5))
* **loot-bot:** rewrite transport from Discord Gateway to HTTP Interactions ([f3f5f19](https://github.com/ramsesoriginal/lorenzo/commit/f3f5f198f9a2e63109a0bcb5e68fe11bc0917fc3))
* **loot-bot:** setItemInstanceContainer/createInformation/addInformationKnower ([d3ef247](https://github.com/ramsesoriginal/lorenzo/commit/d3ef247ed29f4a04cc762c8f6f73eeec0a2d53f1))
* **loot-bot:** thread If-Match through /give, map 412 to a friendly retry message ([a871fcd](https://github.com/ramsesoriginal/lorenzo/commit/a871fcdf55537bf92f9a014944943dca863b82d8))
* **loot-bot:** typed Lorenzo API client generated from apps/api's OpenAPI schema ([fc02c4a](https://github.com/ramsesoriginal/lorenzo/commit/fc02c4ae2417fe06753fcd9d7a74f91b92ee8832))


### Bug Fixes

* **loot-bot:** bump drizzle-orm to 0.45.2, patching a SQL-injection CVE ([6c41d09](https://github.com/ramsesoriginal/lorenzo/commit/6c41d09824a0dd3ab2951892690cb84471f294fe))
* **loot-bot:** bump vitest to 4.1.11, patching two CVEs ([92001d1](https://github.com/ramsesoriginal/lorenzo/commit/92001d1cd5cb82921f1059cfc8d212bc2f7f2df0))
* **loot-bot:** copy the root package.json into the Docker build context ([bdc58c6](https://github.com/ramsesoriginal/lorenzo/commit/bdc58c6fd5e09e99b3ed8a31153a85f54dcdaa32))
* **loot-bot:** copy the root package.json into the Docker build context ([1d6dd9d](https://github.com/ramsesoriginal/lorenzo/commit/1d6dd9d809c9077dedc3f7611b9a80af92b6a0c3))
* **loot-bot:** don't require LOOT_BOT_MIGRATIONS_DATABASE_URL for the deployed server ([b899f28](https://github.com/ramsesoriginal/lorenzo/commit/b899f283fed5b65fb4e7da3b4b287cc2dcaa25cf))
* **loot-bot:** drop the colliding useradd, run as the base image's own node user ([b561ab3](https://github.com/ramsesoriginal/lorenzo/commit/b561ab39292eb212e5903eeb39ce136b729d09dc))
* **loot-bot:** drop the colliding useradd, run as the base image's own node user ([ffe4e1a](https://github.com/ramsesoriginal/lorenzo/commit/ffe4e1a5e1db8d68d6ae814389c5aba80440d4ee))
* **loot-bot:** fix Cloud Run startup — three separate crash-before-listening bugs ([83a8bf0](https://github.com/ramsesoriginal/lorenzo/commit/83a8bf0c911e2762a7435aa139b7a13ae06420d9))
* **loot-bot:** fix Cloud Run startup — wrong port, then a crash-on-empty-URL ([ca4f2c7](https://github.com/ramsesoriginal/lorenzo/commit/ca4f2c794dc5db4aeb6481ba85de298957b7c9c1))
* **loot-bot:** install corepack explicitly, no longer bundled since Node 25 ([b4909ad](https://github.com/ramsesoriginal/lorenzo/commit/b4909ad88cbb420dae66bd2761cb34251ee66633))
* **loot-bot:** install corepack explicitly, no longer bundled since Node 25 ([2bed787](https://github.com/ramsesoriginal/lorenzo/commit/2bed78715bd122d24e5638791d74ad07ce1d04f4))
* **loot-bot:** listen on Cloud Run's own $PORT, not the 8090 default ([9be736a](https://github.com/ramsesoriginal/lorenzo/commit/9be736ac9d5faebcd5a7d909094aa95e38ad5b44))
* **loot-bot:** listen on Cloud Run's own $PORT, not the 8090 default ([aa0481c](https://github.com/ramsesoriginal/lorenzo/commit/aa0481cd46ad3cb0b09366081145654629007ee3))
* **loot-bot:** rename /healthz to /livez - Google Front End reserves that exact path ([58aeeae](https://github.com/ramsesoriginal/lorenzo/commit/58aeeaeeb2a695eff8cb21b9057ce3a847e3239f))
* **loot-bot:** rename /healthz to /livez — Google Front End reserves that exact path ([e208a46](https://github.com/ramsesoriginal/lorenzo/commit/e208a460c98ef1eb631c8d753113c7ea7808ffca))
* **loot-bot:** tolerate an empty LOOT_BOT_PUBLIC_BASE_URL, not just an absent one ([8250960](https://github.com/ramsesoriginal/lorenzo/commit/8250960b8a5fa622cd1060bca4215476a8038d8e))
* **loot-bot:** unwrap DrizzleQueryError before classifying unique-violation errors ([6a4b385](https://github.com/ramsesoriginal/lorenzo/commit/6a4b3859942d94486cc45e41fb1bd9e9c6c611ec))

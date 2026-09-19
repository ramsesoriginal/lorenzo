# Changelog

## [1.0.1](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.0.0...inventory-web-v1.0.1) (2026-09-19)


### Bug Fixes

* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for OAuth callback ([9642c5a](https://github.com/ramsesoriginal/lorenzo/commit/9642c5a8ae5e7871a13587086db2b95ef8ba68e5))
* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for the OAuth callback ([690194e](https://github.com/ramsesoriginal/lorenzo/commit/690194eac234a974a2aae1f1a1c05e9913078367))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([790d7a2](https://github.com/ramsesoriginal/lorenzo/commit/790d7a2e399d132e5f507d433206aa7a3c557433))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([dc9c0df](https://github.com/ramsesoriginal/lorenzo/commit/dc9c0df2da3438406d3a78b8c230da0be6b69b22))

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

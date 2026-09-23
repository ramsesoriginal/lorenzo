# Changelog

## [1.1.0](https://github.com/ramsesoriginal/lorenzo/compare/account-hub-v1.0.0...account-hub-v1.1.0) (2026-09-23)


### Features

* **account-hub:** cross-tenant/cross-campaign access overview ([ec67ec8](https://github.com/ramsesoriginal/lorenzo/commit/ec67ec89e7e8eac5ae947c2693ae48623b1c21ff))
* **account-hub:** pictures, unread badge, and cross-tenant overview ([0544d43](https://github.com/ramsesoriginal/lorenzo/commit/0544d43d11d74cf9dc398dd3afad4cd370d83ce3))
* **account-hub:** tenant and campaign picture upload/display ([c35e967](https://github.com/ramsesoriginal/lorenzo/commit/c35e967cf74d66522d6bf5cc3c63451df6270134))
* **account-hub:** unread-notification indicator on the home hub ([4a0ecf8](https://github.com/ramsesoriginal/lorenzo/commit/4a0ecf8cb7f81b38fe417d2b50affa67854ecd73))
* **brand:** swap Instrument Serif for Newsreader as the display typeface ([f9abfbd](https://github.com/ramsesoriginal/lorenzo/commit/f9abfbd4687eab3fd79d4ca59b3b4d333de5b3aa))


### Bug Fixes

* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for OAuth callback ([9642c5a](https://github.com/ramsesoriginal/lorenzo/commit/9642c5a8ae5e7871a13587086db2b95ef8ba68e5))
* **account-hub,inventory-web:** match Cloudflare's trailing-slash canonical URL for the OAuth callback ([690194e](https://github.com/ramsesoriginal/lorenzo/commit/690194eac234a974a2aae1f1a1c05e9913078367))
* **account-hub:** don't crash /tenants for participant-only tenants ([d48ffce](https://github.com/ramsesoriginal/lorenzo/commit/d48ffce963804ed45767ff73ccd2f818bc36c8c0))
* **account-hub:** don't crash /tenants for participant-only tenants ([ba3e026](https://github.com/ramsesoriginal/lorenzo/commit/ba3e026022a8d6180a91a26a472fa8913bb09f09))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([790d7a2](https://github.com/ramsesoriginal/lorenzo/commit/790d7a2e399d132e5f507d433206aa7a3c557433))
* **inventory-web,account-hub:** Cloudflare Pages build watch paths need ** not * ([dc9c0df](https://github.com/ramsesoriginal/lorenzo/commit/dc9c0df2da3438406d3a78b8c230da0be6b69b22))

## 1.0.0 (2026-09-19)


### Features

* **account-hub:** Beings sub-slice - tenant-scoped list/create/rename ([fbb4970](https://github.com/ramsesoriginal/lorenzo/commit/fbb49700b7e38a703822d42fcf334e2c0eace404))
* **account-hub:** campaign creation, GM assign/revoke, player invite ([4e6f4f5](https://github.com/ramsesoriginal/lorenzo/commit/4e6f4f58b6d48569c44b5f8d56033a2c36ea37b8))
* **account-hub:** campaign roster, tenant admin, notification sending (RFC 0017) ([728f580](https://github.com/ramsesoriginal/lorenzo/commit/728f580691438c714bbcb6e1627bb26c31df7544))
* **account-hub:** campaign visibility on /characters, shared user lookup ([d40fa89](https://github.com/ramsesoriginal/lorenzo/commit/d40fa89379345448ac15d6ffaf9c6c6d49e27e27))
* **account-hub:** character/being roster reuse - completes RFC 0014 ([96323e8](https://github.com/ramsesoriginal/lorenzo/commit/96323e84d7e024eb7ce07c71ae9cd1c7f9123033))
* **account-hub:** Characters sub-slice - list-mine, create, rename ([0e6f6c8](https://github.com/ramsesoriginal/lorenzo/commit/0e6f6c8045f43d0327a8ef8688709effc26c83fc))
* **account-hub:** edit an existing campaign ([3d9333d](https://github.com/ramsesoriginal/lorenzo/commit/3d9333d7405c3b2bf490491a3f4b9b1fd64c9404))
* **account-hub:** Foundation slice - scaffold, auth, GET /me proof ([6e82cd5](https://github.com/ramsesoriginal/lorenzo/commit/6e82cd556f5263b61fc19ba9823e594f5a468033))
* **account-hub:** Notifications sub-slice - inbox, mark-read, polling ([196ed54](https://github.com/ramsesoriginal/lorenzo/commit/196ed545dbea7a89b9ea42c8bbe729536d18e300))
* **account-hub:** Profile sub-slice - view/edit, picture upload ([72508c6](https://github.com/ramsesoriginal/lorenzo/commit/72508c647169b5d24b5e83cc866ce0b131d196ac))
* **account-hub:** tenants and campaigns sub-slice - read-only listing ([3310b92](https://github.com/ramsesoriginal/lorenzo/commit/3310b92bf385151aa34557a8f2fed522e30dcebe))
* apps/account-hub - a user's own account surface ([690aa9f](https://github.com/ramsesoriginal/lorenzo/commit/690aa9f2701a0b72d5f342dd9e11b7038cd033b1))


### Bug Fixes

* **account-hub:** flat build output, not directory-per-page, to fix login ([37a17f9](https://github.com/ramsesoriginal/lorenzo/commit/37a17f95b62f1a8eb4d9cd8147fc4fd6e794726c))
* **account-hub:** login fails with invalid redirect URI on Cloudflare Pages ([a5fc883](https://github.com/ramsesoriginal/lorenzo/commit/a5fc88341b7bd7428c45b478eabb26a661a6e519))

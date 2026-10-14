# Changelog

## [2.0.0](https://github.com/ramsesoriginal/lorenzo/compare/account-hub-v1.1.0...account-hub-v2.0.0) (2026-10-14)


### ⚠ BREAKING CHANGES

* **api:** campaign_name and role of GET /invites/{token}, campaign_id and role of a redemption and of a campaign's invite list and creation can now be null; accepted in openapi-breaking-accepted.txt.
* **api:** the role in GET /tenants and GET /me/managed can now be 'author'; accepted in openapi-breaking-accepted.txt.

### Features

* **account-hub,cli:** a public repository needs no invitation in the copy verdict ([00b3414](https://github.com/ramsesoriginal/lorenzo/commit/00b3414d8d076bdacb2c18aa111f403cbed633a1))
* **account-hub:** a parent added is a warning in the composer and the inbox ([8709f78](https://github.com/ramsesoriginal/lorenzo/commit/8709f7813d7ce5f1f5880cbffc5fccd13906d195))
* **account-hub:** connect a device page and a personal access tokens list ([6dbbe29](https://github.com/ramsesoriginal/lorenzo/commit/6dbbe29357a427b542ed8fac3ff63a7bfc471545))
* **account-hub:** delete a library or repository, with the name typed ([06df7a3](https://github.com/ramsesoriginal/lorenzo/commit/06df7a3f14592ab490624f8600d4e91729306937))
* **account-hub:** People with Authors and a panel for invite links ([5436025](https://github.com/ramsesoriginal/lorenzo/commit/54360258300b31abc37c50d34a1abe6988c353de)), closes [#547](https://github.com/ramsesoriginal/lorenzo/issues/547)
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** Studio view as a subscriber through a scratch Test library ([29831e2](https://github.com/ramsesoriginal/lorenzo/commit/29831e21f34e336e57612950f6416958fb650c87))
* **account-hub:** Studio, libraries using it, built on and activity (ADR 0205) ([83fdc0d](https://github.com/ramsesoriginal/lorenzo/commit/83fdc0d9ab7d594197c54cfb77044a1c8ceba09b))
* **account-hub:** Studio, the guarded publish dialog (ADR 0206) ([9a6b1f3](https://github.com/ramsesoriginal/lorenzo/commit/9a6b1f36391e05755be685bf05cca8dace6b8096))
* **account-hub:** Studio, the release composer (ADR 0209) ([cff4119](https://github.com/ramsesoriginal/lorenzo/commit/cff41190849b30aad1cf9822e690427212974be2))
* **account-hub:** Studio's guarded publish and unpublish dialog ([b23d6aa](https://github.com/ramsesoriginal/lorenzo/commit/b23d6aa3ded5bedabf17b00d426635855f7132ee)), closes [#527](https://github.com/ramsesoriginal/lorenzo/issues/527)
* **account-hub:** Studio's libraries using it, built on and activity ([b0aae73](https://github.com/ramsesoriginal/lorenzo/commit/b0aae7346442edafcf74da9c9a835e082e754eb7)), closes [#526](https://github.com/ramsesoriginal/lorenzo/issues/526)
* **account-hub:** Studio's release composer, Releases tab and release marks in the update inbox ([5e9c12e](https://github.com/ramsesoriginal/lorenzo/commit/5e9c12eab205aae89077603139eb8742215c6b07)), closes [#530](https://github.com/ramsesoriginal/lorenzo/issues/530)
* **api:** a release holds a digest, and a publish says what it breaks ([cc8f901](https://github.com/ramsesoriginal/lorenzo/commit/cc8f901a0795e20eb03846eeca476a237d5704e2))
* **api:** entries with kinds (RFC 0041 K2) ([8a8a6d1](https://github.com/ramsesoriginal/lorenzo/commit/8a8a6d1f7f6560bf4969e6f30f1769b4f7ba6330))
* **api:** make an entry with kinds, change its kinds, and publish only proven combinations ([fa50b2c](https://github.com/ramsesoriginal/lorenzo/commit/fa50b2c4897330bf4f49f4547408ae96ad41734b)), closes [#553](https://github.com/ramsesoriginal/lorenzo/issues/553)
* **api:** one invite table with kinds, role links and library-access links ([9644de9](https://github.com/ramsesoriginal/lorenzo/commit/9644de932ffe61a7621d865ac28ddcaffad48d36)), closes [#546](https://github.com/ramsesoriginal/lorenzo/issues/546)
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** sheet settings and the being sheet read ([12a72c9](https://github.com/ramsesoriginal/lorenzo/commit/12a72c945a0be534eacb9deaf13113cd0f6971ac))
* **api:** stat definition display fields, order and PATCH ([e32ed57](https://github.com/ramsesoriginal/lorenzo/commit/e32ed570b62c4dd116c3060c43f3042b814575d1))
* **api:** the author role, an admin gate and a table-driven route audit ([f25f832](https://github.com/ramsesoriginal/lorenzo/commit/f25f83225ffe1ee4223996c0c556dfa27ae23542)), closes [#545](https://github.com/ramsesoriginal/lorenzo/issues/545)
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the release digest and the breaking-change detector (ADR 0208) ([0742ebb](https://github.com/ramsesoriginal/lorenzo/commit/0742ebb5e0a8ed734d43dc782e808aa1f0502ed8))
* **api:** the release ledger, publishing makes a release (ADR 0207) ([d58f904](https://github.com/ramsesoriginal/lorenzo/commit/d58f904d5389b0628f90f1400dd2471b5478ee7f))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **beings,account-hub:** where the other apps live comes from the app-links registry ([7d915c8](https://github.com/ramsesoriginal/lorenzo/commit/7d915c8a6c8a1441d1e7a49ea7646aeef84e1b63))
* **beings:** Lorenzo Beings, a new app for characters and NPCs (ADR 0270-0272) ([26f7b8f](https://github.com/ramsesoriginal/lorenzo/commit/26f7b8f63eef01898a6ff14dc7c58129aca5e71c))
* **bench:** the main picture - show, choose, replace, remove (B8) ([c19d639](https://github.com/ramsesoriginal/lorenzo/commit/c19d6391da96ed3c44fb6928b309dfd21fb58004))
* **inventory-web:** edit an item's stat values ([3ec929a](https://github.com/ramsesoriginal/lorenzo/commit/3ec929a96bd80fac962a40790d427638271868c4))


### Bug Fixes

* **account-hub:** respect campaign detail access in library reads ([999fa35](https://github.com/ramsesoriginal/lorenzo/commit/999fa35a268b673b87815d3b1e3d28319eca8751))
* **account-hub:** respect campaign detail access in library reads ([40a1c7b](https://github.com/ramsesoriginal/lorenzo/commit/40a1c7b59de9e5109b632ba96b826af37aa764ac))
* **ci:** format account-hub and beings, keep bench e2e unconfigured, size the nav toggle ([82a0db9](https://github.com/ramsesoriginal/lorenzo/commit/82a0db98f55427dffb4b5599c7c32c5a21d12b4b))

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

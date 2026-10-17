# Changelog

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.7.0...api-v1.0.0) (2026-10-17)


### ⚠ BREAKING CHANGES

* **api:** Entry kind responses can include fact, as accepted in ADR 0305. Closed-enum consumers must support this kind.

### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** Studio's visibility switch (ADR 0290) ([ff4fca1](https://github.com/ramsesoriginal/lorenzo/commit/ff4fca102a6a934bedcb482fa0fd4b1d1b4440d3))
* **api,cli:** display fields in repository copy, updates and seed ([d7c00a1](https://github.com/ramsesoriginal/lorenzo/commit/d7c00a182e5952ea8700871678a78e5aa8627cbf))
* **api:** a GM's title per campaign (ADR 0294) ([1fad9bc](https://github.com/ramsesoriginal/lorenzo/commit/1fad9bc8d11e664422e53b7f4e7290aa6f11f88e)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)
* **api:** a public repository is made private and not unpublished; dependents say whether the caller owns them ([c91ad45](https://github.com/ramsesoriginal/lorenzo/commit/c91ad45c674a29619a4c815207df82e31128c710))
* **api:** add canonical facts with explicit outer audiences and subjects ([b81a0c1](https://github.com/ramsesoriginal/lorenzo/commit/b81a0c1d66199b66b8b25fd829a6fba6829558c4))
* **api:** add tenant being stat group and CLI settings ([767b25a](https://github.com/ramsesoriginal/lorenzo/commit/767b25a36c851dc04520f2ce6a2c921769c2bdd8))
* **api:** an Author's reach over the entry, profile and vocabulary routes main added ([0d88e6e](https://github.com/ramsesoriginal/lorenzo/commit/0d88e6e2381de58141adaa9d73d44f6e35d8fad2))
* **api:** announce a release through a table with a cursor, and hold a public repository's releases apart ([eab17b6](https://github.com/ramsesoriginal/lorenzo/commit/eab17b60c38b99f45a5f54ce5321cbb96837060d))
* **api:** ask a signed-in user for a private repository's picture ([ed20b42](https://github.com/ramsesoriginal/lorenzo/commit/ed20b42cca1f731097e762298166f9f08589fa13))
* **api:** break a stat tie by the entry's own parent order ([9827312](https://github.com/ramsesoriginal/lorenzo/commit/9827312314eead21b5b1ff355275c17c3ecd46fd))
* **api:** bulk entity export with cursor pages, gzip and a per-tenant revision ETag ([3065130](https://github.com/ramsesoriginal/lorenzo/commit/3065130b6f90066510be1b6a3154d8927e40f397))
* **api:** count the libraries that copied a repository, name its publishers, add the report link and the terms line ([e84470b](https://github.com/ramsesoriginal/lorenzo/commit/e84470b5a327a8cf50d43326d5c3f3fe6c8e7365))
* **api:** declare canonical fact response compatibility ([e0cf960](https://github.com/ramsesoriginal/lorenzo/commit/e0cf96032a926a51eaf692b4ac52d4744c4246a7))
* **api:** Discover, the listing and the storefront (ADR 0292) ([186c195](https://github.com/ramsesoriginal/lorenzo/commit/186c195581e9c2098fde00e922c841c0b3e6529b)), closes [#725](https://github.com/ramsesoriginal/lorenzo/issues/725)
* **api:** edit ordered information bundles with retry-safe payloads ([ab79dd0](https://github.com/ramsesoriginal/lorenzo/commit/ab79dd0fb469e109e32fccabf979586e10528620))
* **api:** GET /app-links, the registry of app links (ADR 0273) ([73da22c](https://github.com/ramsesoriginal/lorenzo/commit/73da22c00048e43e9b02d6842b9131fbe1947529))
* **api:** information shows who wrote it ([8aa11d5](https://github.com/ramsesoriginal/lorenzo/commit/8aa11d55f9d009914c8b15233ceb82a59c326b0b))
* **api:** link preview endpoint with per-kind templates in a registry ([168ba0f](https://github.com/ramsesoriginal/lorenzo/commit/168ba0f1a3dfc79f9e916163d5e93d9ed47fa8bd))
* **api:** operators delist a repository, and suspending an account delists what it owns ([4e3e084](https://github.com/ramsesoriginal/lorenzo/commit/4e3e0843a3a88d680b4eaafd5fea84c7966514e9))
* **api:** personal access tokens and the device-code flow ([704cb8e](https://github.com/ramsesoriginal/lorenzo/commit/704cb8e2f45340f78652aa20085cd30e2ee8e31a))
* **api:** quotas on a repository ([c2f3426](https://github.com/ramsesoriginal/lorenzo/commit/c2f34264be29d2bd694095056f9eefe15036467c))
* **api:** read private bundles through their existing edit gate ([b036ad5](https://github.com/ramsesoriginal/lorenzo/commit/b036ad56b213c14f4d3b07a77bfa6fa132a462b1))
* **api:** replace information audiences atomically with version guards ([2f2209a](https://github.com/ramsesoriginal/lorenzo/commit/2f2209a94092c276c3610a4369bb00dfdf880bb1))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** sheet settings and the being sheet read ([12a72c9](https://github.com/ramsesoriginal/lorenzo/commit/12a72c945a0be534eacb9deaf13113cd0f6971ac))
* **api:** stat definition display fields, order and PATCH ([e32ed57](https://github.com/ramsesoriginal/lorenzo/commit/e32ed570b62c4dd116c3060c43f3042b814575d1))
* **api:** stat hints ([bf2304c](https://github.com/ramsesoriginal/lorenzo/commit/bf2304cfdc481f5d84e959e38a2e42a8f7ac264d))
* **api:** tenant being stat group and CLI settings ([3f6cf10](https://github.com/ramsesoriginal/lorenzo/commit/3f6cf10890563eefee197bb6e8a3ebcaf593eeec))
* **api:** the device-code flow sends devices to the hub the app-links registry names ([abd9410](https://github.com/ramsesoriginal/lorenzo/commit/abd94102b1500fd8b58512df65ef994f44ab512d))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the flips as routes (ADR 0290) ([f576dbf](https://github.com/ramsesoriginal/lorenzo/commit/f576dbf6b4aac96ad98250c7ba9dba572c2be248))
* **api:** the flips as routes (ADR 0290) ([88a5248](https://github.com/ramsesoriginal/lorenzo/commit/88a524842773779c3ea8adc40568410bcb4d57b7)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **api:** the maintainer's quota numbers, and the copy engines are exempt ([56cb4dd](https://github.com/ramsesoriginal/lorenzo/commit/56cb4dd9f4692d9c7d07eb30d2ef85885bbbf23a))
* **api:** the preview (ADR 0293) ([6cd28ec](https://github.com/ramsesoriginal/lorenzo/commit/6cd28ec3f620ab646aa3369ff88b836f0e3a65c3))
* **api:** the preview (ADR 0293) ([5244d35](https://github.com/ramsesoriginal/lorenzo/commit/5244d35d203b88cb2706e2fe417a566ce1965e5f)), closes [#726](https://github.com/ramsesoriginal/lorenzo/issues/726)
* **api:** the read switch for public repositories (ADR 0286) ([61897d6](https://github.com/ramsesoriginal/lorenzo/commit/61897d671b2301eed489dc89a7bf0bc57c1ce681))
* **api:** the read switch for public repositories (ADR 0286) ([acaa100](https://github.com/ramsesoriginal/lorenzo/commit/acaa10097566a5c5e38e16506aa7bfbc027a29b7)), closes [#701](https://github.com/ramsesoriginal/lorenzo/issues/701)
* **api:** the release fan-out as a table, and a cooldown between releases (ADR 0301) ([e78a1b2](https://github.com/ramsesoriginal/lorenzo/commit/e78a1b2ea51230c0dcc6b636b813c8a74c408e86))
* **api:** the stat vocabulary is readable by every participant ([a501961](https://github.com/ramsesoriginal/lorenzo/commit/a501961b73ad4c01c003bd99e7b427501babb4ad))
* **api:** where a stat value comes from, and why ([4e1f892](https://github.com/ramsesoriginal/lorenzo/commit/4e1f89219bb1eca3bb91109e0a86c60e83432880))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **api:** who may read a public repository (ADR 0287) ([15869f2](https://github.com/ramsesoriginal/lorenzo/commit/15869f2a6d2fae77df6de21edd73e23d3afd6fc8)), closes [#702](https://github.com/ramsesoriginal/lorenzo/issues/702)
* **beings:** delete beings and settle their inventory ([49e000d](https://github.com/ramsesoriginal/lorenzo/commit/49e000df9beae15a84d09bf3f29fab95dfe90eef))
* **beings:** delete beings and settle their inventory ([46ad48e](https://github.com/ramsesoriginal/lorenzo/commit/46ad48e4b8397ef2a9974aa7d57329ee6cda879e))
* **beings:** Lorenzo Beings, a new app for characters and NPCs (ADR 0270-0272) ([26f7b8f](https://github.com/ramsesoriginal/lorenzo/commit/26f7b8f63eef01898a6ff14dc7c58129aca5e71c))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **bench:** keyboard moves for tabs (11 of 12) ([9ff4392](https://github.com/ramsesoriginal/lorenzo/commit/9ff4392b7781676e0311bf4288e32840c41971e0))
* **bench:** the main picture - show, choose, replace, remove (B8) ([c19d639](https://github.com/ramsesoriginal/lorenzo/commit/c19d6391da96ed3c44fb6928b309dfd21fb58004))
* **cli:** author stat vocabulary and render entry sheets ([c00a635](https://github.com/ramsesoriginal/lorenzo/commit/c00a635e5fbdccf3cd2c1cab6bfa5b53643537b6))
* **inventory-mobile:** keep ordered picture notes and audiences ([b0e7251](https://github.com/ramsesoriginal/lorenzo/commit/b0e72517454ed5fca4352939a03d8087bb73ed1b))
* **inventory-web:** edit an item's stat values ([3ec929a](https://github.com/ramsesoriginal/lorenzo/commit/3ec929a96bd80fac962a40790d427638271868c4))
* **lorenzoscript:** a stat in a text, {weight} ([3bccede](https://github.com/ramsesoriginal/lorenzo/commit/3bccede76447f031ce553bd60e92bf5acda0a513))
* merge canonical facts beneath information bundles ([957fd1f](https://github.com/ramsesoriginal/lorenzo/commit/957fd1f5901e8ba2b198cd9a0b3e486f1dfc970b))


### Bug Fixes

* **api:** load inherited weapon stat sources for being sheets ([0e1e182](https://github.com/ramsesoriginal/lorenzo/commit/0e1e18260889ccd2b2bcc24d3312fd447389821a))
* **api:** only a repository's members read delisted on its profile ([c619b66](https://github.com/ramsesoriginal/lorenzo/commit/c619b66aaf814815f7319dc0bd9a6f17c0fa5a3a))
* **api:** the invite table is the registry's invite, and the vocabulary gate reads well ([5f6a2c1](https://github.com/ramsesoriginal/lorenzo/commit/5f6a2c1f03bc1b010a44ffbd5eb2922ee4a93758))
* **api:** the parent-order migration runs on a database that has parents ([a40b879](https://github.com/ramsesoriginal/lorenzo/commit/a40b87974b464d93a3110bcdfecab28c9e5697f9))
* **api:** the profile migration follows main's latest ([8fc4953](https://github.com/ramsesoriginal/lorenzo/commit/8fc4953c035b47e82f1275eb238f33126af11f6f))
* **api:** the release document carries a stat definition's display fields ([370c47e](https://github.com/ramsesoriginal/lorenzo/commit/370c47e2af71c604fccdfcd88008c628c8489a83))
* **api:** write https URLs behind a proxy that speaks http to the API ([83193e6](https://github.com/ramsesoriginal/lorenzo/commit/83193e6babc82ec6719e8b299be31e4032ecb4fb))
* **api:** write https URLs behind a proxy that speaks http to the API ([a604890](https://github.com/ramsesoriginal/lorenzo/commit/a60489054aaf93ae0fcbb760c54631550041daea))
* **beings:** keep empty rows compact and cache picture bytes ([38fe9ed](https://github.com/ramsesoriginal/lorenzo/commit/38fe9ed168c302a1aa642581b47eda62eef1944e))
* **beings:** keep empty rows compact and cache picture bytes ([054b6e2](https://github.com/ramsesoriginal/lorenzo/commit/054b6e2553b60f9b1e6dce8a1ddeb88b2f1d7d36))
* D6d's optional user does not start a sweep, and D6e's tests accept the terms ([e4e13b3](https://github.com/ramsesoriginal/lorenzo/commit/e4e13b3f5f58053eb98469601e25c772618e4b68)), closes [#748](https://github.com/ramsesoriginal/lorenzo/issues/748)
* increase picture upload limits to 10 MB ([e787b11](https://github.com/ramsesoriginal/lorenzo/commit/e787b11095956f3a66d8d066cfebc0a99caf0912))
* increase picture upload limits to 10 MB ([e27de26](https://github.com/ramsesoriginal/lorenzo/commit/e27de26af7b92d60d8a00877a78e3ec484e89b25))
* the app-links registry avoids two patterns CodeQL flags ([6f18465](https://github.com/ramsesoriginal/lorenzo/commit/6f18465f3809ed5b8fa8fb86dbba125af96edd31))


### Performance Improvements

* **api:** an item read in half the statements: one query for the prototype chain, joined to-one loads, and visibility only as far as it is read ([1c55c7c](https://github.com/ramsesoriginal/lorenzo/commit/1c55c7c7b6a14d2be56c42fb9321a29143dbd422))
* **api:** an item read in half the statements: one query for the prototype chain, joined to-one loads, and visibility only as far as it is read ([9edff0b](https://github.com/ramsesoriginal/lorenzo/commit/9edff0b25bc45d5808dc5e2107b2019f6c9cb973))
* **api:** an item read loads what it reads with the row, and resolves who may read it as far as it needs ([ac0873a](https://github.com/ramsesoriginal/lorenzo/commit/ac0873a6e63c507907e872c4f160d2f717bdf4c5))
* **api:** ask the database once per request for the tenant and the caller's membership ([5149927](https://github.com/ramsesoriginal/lorenzo/commit/514992716368a12afb01d583378a237088d039b0))
* **api:** item reads cost what they read: entity-scoped stat views and no JIT ([3aae810](https://github.com/ramsesoriginal/lorenzo/commit/3aae8106ff6635f140501058fef7cf608d5ecfd3))
* **api:** the app role runs without JIT ([4f35337](https://github.com/ramsesoriginal/lorenzo/commit/4f353372e9bcb7fd94dd5d23b1fa5461916fbb71))
* **api:** the prototype chain of an item is one recursive query ([458dae9](https://github.com/ramsesoriginal/lorenzo/commit/458dae9705020f68951d492187f4608502d2c47c))
* **api:** the update engine inverts the entity links once, not per attachment end ([42913b6](https://github.com/ramsesoriginal/lorenzo/commit/42913b646306365e6d565328f86c3e2bad6e790a))
* **api:** the update engine inverts the entity links once, not per attachment end ([4901e6c](https://github.com/ramsesoriginal/lorenzo/commit/4901e6cc84fa3bd3fa486ff2a6ca29270fa45fec)), closes [#716](https://github.com/ramsesoriginal/lorenzo/issues/716)
* **api:** v_effective_stat, v_item and v_item_instance resolve per entity ([c3a9b3a](https://github.com/ramsesoriginal/lorenzo/commit/c3a9b3a5aca11fea50be4da8d5a6ed1397f5a874))
* **api:** write routes answer with the reader, and join to-one relationships ([91f80c6](https://github.com/ramsesoriginal/lorenzo/commit/91f80c6477eec22eb911baf15179de1f527ee983))
* **api:** write routes cost what they write ([0d47c97](https://github.com/ramsesoriginal/lorenzo/commit/0d47c97b26bec7f15493b64462bb3fe9bed6d17b))


### Documentation

* **adr:** the Author role is ADR 0219 ([9e6533c](https://github.com/ramsesoriginal/lorenzo/commit/9e6533cbe4d5c48d39a196c443a2b400a4ffc9fa))
* **beings:** describe permanent being deletion ([eb5de00](https://github.com/ramsesoriginal/lorenzo/commit/eb5de004ee310cddd57d2e99399b675659234289))
* **operations:** going public, the edge rule for Discover and copying, and the deploy variables ([f20eceb](https://github.com/ramsesoriginal/lorenzo/commit/f20eceb3b7feafe6d6d86b81c85924158131454d))
* **operations:** going public, the edge rule for Discover and copying, and the deploy variables ([451454f](https://github.com/ramsesoriginal/lorenzo/commit/451454f3d97dc5d9d96447068453b37828f403b7)), closes [#497](https://github.com/ramsesoriginal/lorenzo/issues/497)
* refresh repository documentation and reconcile tracking checklists ([1cb303c](https://github.com/ramsesoriginal/lorenzo/commit/1cb303c7f8754e4d55bcf4db78c6133ed863664c))
* refresh shipped capabilities and repository guidance ([95e7bb8](https://github.com/ramsesoriginal/lorenzo/commit/95e7bb841a554cec4faaa385898311cefd2f78bc))
* the being sheet as built ([782ac03](https://github.com/ramsesoriginal/lorenzo/commit/782ac0332cba4b2b92d315ede0b82951804558db))

## [0.7.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.6.0...api-v0.7.0) (2026-09-23)


### Features

* **api:** a tenant OWNER reads GM-only information like an ORGA (ADR 0091) ([959ae3a](https://github.com/ramsesoriginal/lorenzo/commit/959ae3ad626264bf2348a38e78827db034cef250))
* **api:** activity log coverage and member-removal notice (ADR 0084) ([009b954](https://github.com/ramsesoriginal/lorenzo/commit/009b9546244bff8e42eb26b9e566c2455a15d937))
* **api:** deliver [#154](https://github.com/ramsesoriginal/lorenzo/issues/154) to main - export reads, GET /me/managed, notifications since, OWNER visibility (ADR 0085/0086/0096) ([cebd784](https://github.com/ramsesoriginal/lorenzo/commit/cebd784b89efbfb8d10e50a75bbd13c887adf717))
* **api:** GET /me/managed and a since filter on GET /me/notifications ([529d6c0](https://github.com/ramsesoriginal/lorenzo/commit/529d6c0ead41d038cfe9e7a175d1d894119a5c01))
* **api:** list stat groups/definitions and tenant knowledge grants ([e90e122](https://github.com/ramsesoriginal/lorenzo/commit/e90e122cd264132179c1525e23c78c9b8fd4438f))
* **api:** log character, player, and group mutations in the activity log ([629900b](https://github.com/ramsesoriginal/lorenzo/commit/629900b4390e27eb1dc5b9ed20074808178b24ca))
* **api:** log information, knowledge grants, and stat definitions; document exclusions ([ea7f335](https://github.com/ramsesoriginal/lorenzo/commit/ea7f335045e29e2c6242945c2e014453bf54305d))
* **api:** log item and item-instance mutations in the activity log ([75f8cc1](https://github.com/ramsesoriginal/lorenzo/commit/75f8cc1dee94588cc0b9c158a52def1a5ff0c95e))
* **api:** log tenant/campaign PATCH and admin opt-out in the activity log ([4a6f4df](https://github.com/ramsesoriginal/lorenzo/commit/4a6f4df74aa693cabc7b3e2bb87442da14f019e7))
* **api:** notify and record detail when a member is removed from a tenant ([6a37c7b](https://github.com/ramsesoriginal/lorenzo/commit/6a37c7b943d05fbfe6261da5efd0c1e2a505e697))
* **api:** player-facing change feed - GET /me/changes (ADR 0099) ([4b01537](https://github.com/ramsesoriginal/lorenzo/commit/4b015376fc70a299b8271a9ccfc0c93e82b86318))
* **api:** player-facing change feed (ADR 0099) ([f433826](https://github.com/ramsesoriginal/lorenzo/commit/f433826c5d89f0c49772d5375bba267087549f78))
* **api:** shareable, expiring campaign invite links (ADR 0092) ([3e61e5f](https://github.com/ramsesoriginal/lorenzo/commit/3e61e5f220d3314033150892ea78f327cd1c7626))
* **api:** shareable, expiring campaign invite links (ADR 0092) ([588a080](https://github.com/ramsesoriginal/lorenzo/commit/588a0809bc30544b5717d8b1c763534cbd82a2b1))
* **api:** tenant export reads, GET /me/managed, notifications since (ADR 0085/0086) ([784fb36](https://github.com/ramsesoriginal/lorenzo/commit/784fb36a49977ca796d87df19b2de4b569fb639d))


### Bug Fixes

* **api:** GET /tenants/{id} no longer 404s for participant-only callers ([8375424](https://github.com/ramsesoriginal/lorenzo/commit/8375424ebb559f244622f5d1f676a5719f470bee))
* **api:** GET /tenants/{id} no longer 404s for participant-only callers ([9be4343](https://github.com/ramsesoriginal/lorenzo/commit/9be43439bd67273d6464c1e04e78e2ba200d4a08))
* **api:** record every departure an account deletion causes ([22c90a1](https://github.com/ramsesoriginal/lorenzo/commit/22c90a1d2f0eef2e7c3aeaf7d6290c8f01df4880))
* **api:** record every departure an account deletion causes (ADR 0084 addendum) ([6cb0b42](https://github.com/ramsesoriginal/lorenzo/commit/6cb0b4232e1f36401122c211b7276c77df55f4c4))


### Documentation

* add the change feed (ADR 0099) to the apps/api README, ER diagram and overview ([8721316](https://github.com/ramsesoriginal/lorenzo/commit/872131646df3a0b21ed338b7b24c61324f329b06))
* add the change feed (ADR 0099) to the apps/api README, ER diagram and overview ([9af5001](https://github.com/ramsesoriginal/lorenzo/commit/9af5001ba91f29feb57ab97f3fae3d40e8193e8f))
* bring apps/api README, ER diagram and overview up to date (ADR 0084-0096) ([59403d5](https://github.com/ramsesoriginal/lorenzo/commit/59403d528e7631f0f5816c22b202cc3b35620c9c))
* bring apps/api README, ER diagram and overview up to date with ADR 0084-0096 ([8b7d00f](https://github.com/ramsesoriginal/lorenzo/commit/8b7d00ffbd80b24ea84eee4b0ef92eb735ec4d9c))
* follow the renumbering of the invite-links RFC (0019 -&gt; 0023) ([ff98ebe](https://github.com/ramsesoriginal/lorenzo/commit/ff98ebe4d3c10ae407c94e036a2e8b68165157fd))
* follow the renumbering of the OWNER-visibility ADR (0091 -&gt; 0096) ([971d41f](https://github.com/ramsesoriginal/lorenzo/commit/971d41f996d4c3c27f0b79b2dc1bfe6d8e453f29))
* runbook for exporting a tenant, backed by an executable walk test ([70ed52a](https://github.com/ramsesoriginal/lorenzo/commit/70ed52a6fe9207f8cd024449301a88102bc6cdcd))

## [0.6.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.5.0...api-v0.6.0) (2026-09-19)


### Features

* **api:** add group write API (ADR 0064) ([71c8186](https://github.com/ramsesoriginal/lorenzo/commit/71c8186f23bfe627281bdef6bdde37b4ad6ea559))
* **api:** GET .../item-instances/unowned (ADR 0077) ([b1b332a](https://github.com/ramsesoriginal/lorenzo/commit/b1b332af8c9f5f966db12453cc535ba12280442d))
* **api:** GET /tenants/{id}/beings (ADR 0078) ([062c078](https://github.com/ramsesoriginal/lorenzo/commit/062c078fc2d0965fa8c569c46f67fe4f12031fd5))
* **api:** group write API, bulk container move, computed item fields ([80a6820](https://github.com/ramsesoriginal/lorenzo/commit/80a682080cc79927e3a316524c2849050021d119))
* **api:** item catalog prototype-set editing, inspection, and bulk editing ([2697666](https://github.com/ramsesoriginal/lorenzo/commit/2697666bffc78416a36d5498be3f7220b8f7d84e))
* **api:** item/item-instance read and write additions (ADR 0065/0066/0067) ([a40cc65](https://github.com/ramsesoriginal/lorenzo/commit/a40cc652a1c21ae5a60e93f896287aa926b8a518))
* **api:** prototype-graph reverse lookup, ancestry, and bulk editing ([3f580c7](https://github.com/ramsesoriginal/lorenzo/commit/3f580c7e74c8866e2948634995ae258f944236b2))
* **api:** PUT /items/{id}/prototypes to replace a catalog item's prototype set ([3d645f7](https://github.com/ramsesoriginal/lorenzo/commit/3d645f7edc3498a2d49d3db300d8e9511cb4b116))
* **api:** unowned item instances + being listing (ADR 0077/0078) ([e581042](https://github.com/ramsesoriginal/lorenzo/commit/e5810423a575d8895036753b3d2d6e19b3d1363c))


### Bug Fixes

* **api:** sync user email from Authgear's UserInfo endpoint (ADR 0075) ([9d7decb](https://github.com/ramsesoriginal/lorenzo/commit/9d7decbc0ec24c40277f5204801f08e2481ed996))
* **api:** sync user email from Authgear's UserInfo endpoint (ADR 0075) ([52005e2](https://github.com/ramsesoriginal/lorenzo/commit/52005e2588bda958f7ef56357778051d3bfef389))


### Documentation

* correct stale and inaccurate claims found in a full documentation audit ([49ed4dc](https://github.com/ramsesoriginal/lorenzo/commit/49ed4dc6bd0f901ffa707e36f689b431e0ab1471))
* fix stale docs, broken diagrams, and adopt Milestones/Issues alongside RFC/ADR ([76f0f0d](https://github.com/ramsesoriginal/lorenzo/commit/76f0f0d6a42d942f897d407e8414c0bedcc5fe98))
* **rfc:** renumber RFC 0014 -&gt; 0015 - main independently claimed 0014 ([c18cde4](https://github.com/ramsesoriginal/lorenzo/commit/c18cde41882155a0320226dc66381a1d1ff04142))

## [0.5.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.4.0...api-v0.5.0) (2026-09-17)


### Features

* **api:** group-scoped notifications ([fd484a0](https://github.com/ramsesoriginal/lorenzo/commit/fd484a0bbc1fe14ff63a64b3f5e4375a9b6cd9ef))
* **api:** platform operations and notifications ([2d12ab3](https://github.com/ramsesoriginal/lorenzo/commit/2d12ab3b182adf82e7805446e276fa259a77402f))
* **api:** profile pictures for User, Tenant, and Campaign ([96e4c32](https://github.com/ramsesoriginal/lorenzo/commit/96e4c323e64c4ac31551e3d8139552bd50460077))
* **api:** user identity via email/nickname, plus exact-match lookup ([68a1bd7](https://github.com/ramsesoriginal/lorenzo/commit/68a1bd7c33b571e9cbb2cf610442fef40aa51a4b))
* **api:** user profile expansion, sender read-receipts, bulk invite, tenant activity log ([78a259d](https://github.com/ramsesoriginal/lorenzo/commit/78a259ded40d344aea7cc05cb5e42e31e9f1cd5c))


### Bug Fixes

* **api:** surface suspension_reason in the 403 detail ([1f70a8f](https://github.com/ramsesoriginal/lorenzo/commit/1f70a8f6189f06dfd7cf45ccc298e9f486fa8d7e))
* **api:** switch CORS_ALLOWED_ORIGINS to space-separated, not a JSON array ([8bae318](https://github.com/ramsesoriginal/lorenzo/commit/8bae318ef1ecc065486a6c41a9cb143183d2978e))
* **api:** switch CORS_ALLOWED_ORIGINS to space-separated, not a JSON array ([7de51b3](https://github.com/ramsesoriginal/lorenzo/commit/7de51b380d7393b2adee681775f57f090d214331))
* **api:** the tenant-creator role key is tenant_creator, not tenant-creator ([02c8143](https://github.com/ramsesoriginal/lorenzo/commit/02c814316609019d7972a7e057264070938d16a8))
* **api:** the tenant-creator role key is tenant_creator, not tenant-creator ([b1b4e0d](https://github.com/ramsesoriginal/lorenzo/commit/b1b4e0d852e498c16c0b2c55f41375bb3d521625))
* **api:** use SHA256, not MD5, for the Gravatar lookup hash ([d3e923d](https://github.com/ramsesoriginal/lorenzo/commit/d3e923d93c41b1bf913665fc9b21a3b28c76f48c))
* **api:** validate user_id before granting campaign GM ([5521ba7](https://github.com/ramsesoriginal/lorenzo/commit/5521ba7b5b16d1d9d76443e85f84b19aa6febd67))


### Documentation

* **adr:** renumber 0050-0059 to 0054-0063 to avoid main's loot-bot collision ([0219229](https://github.com/ramsesoriginal/lorenzo/commit/021922931a78fe5994b5387ab4c33cf57c43ad53))

## [0.4.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.3.0...api-v0.4.0) (2026-09-16)


### Features

* **api:** campaign CRUD API (ADR 0034) ([9a5198e](https://github.com/ramsesoriginal/lorenzo/commit/9a5198e14a3185d528c47fbcbdd523487d42e3a4))
* **api:** campaign-scoped GM visibility (ADR 0035) ([18ab685](https://github.com/ramsesoriginal/lorenzo/commit/18ab6858cd449ec35c4b5e29602ab5343cf26667))
* **api:** character table and read API (ADR 0031) ([0322a91](https://github.com/ramsesoriginal/lorenzo/commit/0322a910bd336291243422dfdba1e3f1b615ca53))
* **api:** configure CORS ([5a6657e](https://github.com/ramsesoriginal/lorenzo/commit/5a6657ee3a6d6fc8b08360ebc6a05811e56165e1))
* **api:** containment quantity and stacking (ADR 0041) ([9def50f](https://github.com/ramsesoriginal/lorenzo/commit/9def50f20828bc28907b058ba364f517fdacaebf))
* **api:** effective stat resolution and stat CRUD (ADR 0037) ([b3a2844](https://github.com/ramsesoriginal/lorenzo/commit/b3a284470f2b652ae8fa9928d48172a035d84a3d))
* **api:** expose a concurrency token on item/item-instance reads ([24e223e](https://github.com/ramsesoriginal/lorenzo/commit/24e223ef1a41368543a0504069df3825d112a114))
* **api:** generalize stat resolution into v_effective_stat (ADR 0039) ([896aab3](https://github.com/ramsesoriginal/lorenzo/commit/896aab37c8d77695297c80c030a84f20d055d232))
* **api:** information/payload/knowledge CRUD API (ADR 0038) ([3e8b8d2](https://github.com/ramsesoriginal/lorenzo/commit/3e8b8d24ce65e10bec5a7ec55139c34657d5afb2))
* **api:** item and item-instance CRUD API (ADR 0032) ([6e43c87](https://github.com/ramsesoriginal/lorenzo/commit/6e43c878923b0668e64dc005daa510b10f9736be))
* **api:** item catalog search by name ([14d611b](https://github.com/ramsesoriginal/lorenzo/commit/14d611ba71beb6ef75bd19adbd24cac7299ab284))
* **api:** item-instance read visibility narrows to reachable owners ([2c4b1f5](https://github.com/ramsesoriginal/lorenzo/commit/2c4b1f57cf66ddf78c835b29e44788319cc2f877))
* **api:** item-instance slug and by-slug lookup ([f120c8d](https://github.com/ramsesoriginal/lorenzo/commit/f120c8d1dbd2eb4107ad9224fd7791d1eff9b6d7))
* **api:** loot-assignment, concurrency, CORS, and API cleanups ([d88ad4e](https://github.com/ramsesoriginal/lorenzo/commit/d88ad4e28d6c234c8adf369ff6b994f96dd2c85e))
* **api:** mine filter on GET /tenants/{tenant_id}/characters ([18f5b37](https://github.com/ramsesoriginal/lorenzo/commit/18f5b37a1903ed3be7c1c640f0847b010bd19a15))
* **api:** player join/leave and character CRUD (ADR 0036) ([135ad94](https://github.com/ramsesoriginal/lorenzo/commit/135ad945e4e9aa1711704602b5747fbb5ef15958))
* **api:** read-only groups API ([e95487a](https://github.com/ramsesoriginal/lorenzo/commit/e95487a522697bb9dff8287b63d28ceb8c86ffb9))
* **api:** REST API surface for milestone [#1](https://github.com/ramsesoriginal/lorenzo/issues/1) ([be288e5](https://github.com/ramsesoriginal/lorenzo/commit/be288e56fbbfccf87cb9227e282fbe5248520c1f))
* **api:** split-with-owner, merge, and bulk-assign for item instances ([90535ac](https://github.com/ramsesoriginal/lorenzo/commit/90535ac272991885e938ae332ad9c32845dc394a))
* **api:** sub-slice 1 -- entity.created_by/updated_by (ADR 0029) ([0435989](https://github.com/ramsesoriginal/lorenzo/commit/043598974f80b1768294bb7840d6d18cc2722329))
* **api:** tenant creation and update API (ADR 0033) ([0b17175](https://github.com/ramsesoriginal/lorenzo/commit/0b171750e851671a9a842fd9b96600861c4d9926))
* **api:** tenant/campaign read API (ADR 0030) ([f6f7426](https://github.com/ramsesoriginal/lorenzo/commit/f6f742679984d73a3ee9b8f152962b396ea4afd5))
* **api:** user deletion and membership invite/role-change/revoke (ADR 0036) ([c1c3f4e](https://github.com/ramsesoriginal/lorenzo/commit/c1c3f4effccbb3865bb54e7f722b6c3bdfa5ab9d))
* **api:** widen GM reachability to the party's surroundings ([caa4a52](https://github.com/ramsesoriginal/lorenzo/commit/caa4a522e4540c7ff0407c3bdf046b37d418c96e))


### Bug Fixes

* **api:** allow player/campaign_gm RLS self-access for GET /tenants ([515c4c3](https://github.com/ramsesoriginal/lorenzo/commit/515c4c32b88dacd3e2c4fa21b98e9cd9e918c30f))
* **api:** clean up a leaked tenant membership in a pagination test ([8c259ed](https://github.com/ramsesoriginal/lorenzo/commit/8c259ed881ed68dd2912093704b52d22ec5c46a1))
* **api:** populate EntityDetailOut.parent's own quantity ([08d6eae](https://github.com/ramsesoriginal/lorenzo/commit/08d6eae5b357f7809c8b7c227ab28329114dc8b9))
* **api:** stop admin opt-out from locking its own holder out (ADR 0034) ([bfc8302](https://github.com/ramsesoriginal/lorenzo/commit/bfc8302d68c153279fb06be2eda1ca9d2d251ef6))
* force get_current_user to resolve before get_tenant_or_404 sets RLS context ([03621b6](https://github.com/ramsesoriginal/lorenzo/commit/03621b6ae6bcdd1af367235d6d8f49a8da6af077))
* merge diverged Alembic migration heads (ADR 0033 + ADR 0034) ([e949f99](https://github.com/ramsesoriginal/lorenzo/commit/e949f99a44fd4753c0f51b51d1e5141ce53a9b4d))
* merge remaining diverged Alembic migration head (ADR 0037) ([53ccba1](https://github.com/ramsesoriginal/lorenzo/commit/53ccba19aefcbd705b138f9b18fbd43648000389))


### Documentation

* refresh README branding, badges, and stale docs ([ef3ee5e](https://github.com/ramsesoriginal/lorenzo/commit/ef3ee5e26da852426f4f8ff3c92797797ba0b891))
* stop claiming knowledge/visibility is unbuilt (ADR 0028 shipped) ([b1e32ec](https://github.com/ramsesoriginal/lorenzo/commit/b1e32ec7ad09142d926fd92c187e26f2538ef858))
* update architecture roadmap for ADR 0045 ([db5ce8d](https://github.com/ramsesoriginal/lorenzo/commit/db5ce8d5fe7b2a2c9e980b1b50db21667f3d3811))

## [0.3.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.2.0...api-v0.3.0) (2026-09-10)


### Features

* **api:** add a real login helper for local dev Authgear tokens ([0524e0b](https://github.com/ramsesoriginal/lorenzo/commit/0524e0bf4fe26f4d6c6b2fc78ff51bbaff9632bd))
* **api:** add a real login helper for local dev Authgear tokens ([e79b006](https://github.com/ramsesoriginal/lorenzo/commit/e79b0065284caaaa984e2d2737ffe84e5e0d7396))
* **api:** add an OpenAPI breaking-change check to CI ([7350b8f](https://github.com/ramsesoriginal/lorenzo/commit/7350b8fa301cb8eb3fd1b9d577afd4283e337b1f))
* **api:** add knowledge/group membership, fix visibility gaps ([530f354](https://github.com/ramsesoriginal/lorenzo/commit/530f354468df209c778d5e6508d65538b5f60bb0))
* **api:** add read-only convenience relationships on Entity ([7852e3f](https://github.com/ramsesoriginal/lorenzo/commit/7852e3f2be11142b487f4ff6ded557461d599332))
* **api:** add the real entity.tenant_id -&gt; tenant.id FK ([443824e](https://github.com/ramsesoriginal/lorenzo/commit/443824eb425cc66eea09ed4290188f7a0717bb78))
* **api:** auth, tenancy, campaigns, and the full RFC 0001/RFC 0002 domain model ([2cc9367](https://github.com/ramsesoriginal/lorenzo/commit/2cc93676ce39f1bb2d4235bb615f06d9cd588ad5))
* **api:** entities REST endpoints - list and rich detail ([240032f](https://github.com/ramsesoriginal/lorenzo/commit/240032f522782e3fcbb7ae9beda3ef1419f90f36))
* **api:** items, item instances, container/owner filtering, docs ([f997068](https://github.com/ramsesoriginal/lorenzo/commit/f9970681343c0de196312526aa2ee4f3e430938c))
* **api:** knowledge, group membership, and public information (ADR 0028) ([96b0a39](https://github.com/ramsesoriginal/lorenzo/commit/96b0a3949ede9b06eb85394291b6e9762d833e3a))
* **api:** REST API foundation - tenant scoping, schemas, payload content ([a0e687b](https://github.com/ramsesoriginal/lorenzo/commit/a0e687b716bd86b5549f6a1dcb550c421fa82a90))
* **api:** sub-slice 1 — restricted app role, RLS now actually enforced ([85e0224](https://github.com/ramsesoriginal/lorenzo/commit/85e0224d45ecb76f677c7c3dff92db6bac809c63))
* **api:** sub-slice 1 — the entity table ([53a0cc9](https://github.com/ramsesoriginal/lorenzo/commit/53a0cc9602c99edb033c4fdd8893bb898a1edc2d))
* **api:** sub-slice 2 — User, full Tenant, Membership ([007d018](https://github.com/ramsesoriginal/lorenzo/commit/007d0185bcd5b1a11c8a6338b084e76952380b6c))
* **api:** sub-slice 3 — Authgear token verification ([5a99677](https://github.com/ramsesoriginal/lorenzo/commit/5a996771f864700a559d58f945fa4d207fff98c0))
* **api:** sub-slice 3 — stat definitions, groups, and per-entity values ([5a02bb3](https://github.com/ramsesoriginal/lorenzo/commit/5a02bb3ea79be57839a05a4aae65b8c7fb2c1c22))
* **api:** sub-slice 4 — Campaign and Player ([4205fec](https://github.com/ramsesoriginal/lorenzo/commit/4205fec76c7caa45822717b7941ad4e86a0a4404))
* **api:** sub-slice 4 — entity_prototype, the inheritance graph ([15ae468](https://github.com/ramsesoriginal/lorenzo/commit/15ae468e58ebf1f647a307102ae08b4ceb30fc04))
* **api:** sub-slice 5 — Character (being), roster reuse, and ownership ([da1804b](https://github.com/ramsesoriginal/lorenzo/commit/da1804bef6c3c7c0c2a18e816dcb24fe2de82f88))
* **api:** sub-slice 5 — containment, the generic physical relation ([19703c4](https://github.com/ramsesoriginal/lorenzo/commit/19703c4e706e86c35b002f6113112c9682bb3b64))
* **api:** sub-slice 6 — Campaign GM, orga, and the campaign access rule ([39f6030](https://github.com/ramsesoriginal/lorenzo/commit/39f60302d00cdfd4506181b498b017b98f4ab839))
* **api:** sub-slice 6 — information and payloads ([10a2db2](https://github.com/ramsesoriginal/lorenzo/commit/10a2db295cef403582faa33045ca9a3f3d031a65))
* **api:** sub-slice 7 — item, item_instance, and the v_item view ([a87b789](https://github.com/ramsesoriginal/lorenzo/commit/a87b7893cf5fc8eef05f8cd6ec79967576d8fad5))
* **api:** tenant table bootstrap ([2137567](https://github.com/ramsesoriginal/lorenzo/commit/21375677169452e766691aa01203a7cd893c223b))


### Bug Fixes

* **api:** add player.campaign_id's missing index ([fedf8b5](https://github.com/ramsesoriginal/lorenzo/commit/fedf8b5bec9ccf2475d08af152f81082467b7763))
* **api:** close out four review findings ([dccc87c](https://github.com/ramsesoriginal/lorenzo/commit/dccc87c0f02276c398a0948120603e1578838f81))
* **api:** close out four review findings ([4c8ae20](https://github.com/ramsesoriginal/lorenzo/commit/4c8ae204b5e1fb00d2c00aa62b1551bdbee910a2))
* **api:** close the same information-disclosure gap in items/item-instances ([f9715ce](https://github.com/ramsesoriginal/lorenzo/commit/f9715ce93a4947d22881de89f605ae590539bc56))
* **api:** make GET /entities/{id} actually respect is_public/knowledge ([0cd215c](https://github.com/ramsesoriginal/lorenzo/commit/0cd215ce47f110eb03d715105a7970dd6e7e8d42))
* **api:** make GET /payloads/{id}/content respect is_public/knowledge too ([aed1f4e](https://github.com/ramsesoriginal/lorenzo/commit/aed1f4e0f7b719f8e12ef9934bae6e75c029a5c9))
* **api:** split v_item into v_item and v_item_instance ([23f5f92](https://github.com/ramsesoriginal/lorenzo/commit/23f5f922974ff881699612bee3cdcdd26fa8ffcd))
* **api:** sync uv.lock after the 0.2.0 bump, close the CI gap that mi… ([a6a2d9f](https://github.com/ramsesoriginal/lorenzo/commit/a6a2d9f3ce29a70a5ad8b9d5b5834cb1357f0182))
* **api:** sync uv.lock after the 0.2.0 bump, close the CI gap that missed it ([7f2c4ff](https://github.com/ramsesoriginal/lorenzo/commit/7f2c4ff8a61ea3a483e1c626a88dee95afa6611b))


### Documentation

* **api:** stop claiming RLS is unenforced now that the role fix shipped ([b616488](https://github.com/ramsesoriginal/lorenzo/commit/b61648823da93e3349572282b7f4748842d4abf0))
* clean up stale non-ADR/RFC documentation ([89dc443](https://github.com/ramsesoriginal/lorenzo/commit/89dc443b5441e1fbe1ebd9d0d5ec4b4465c823d7))
* confirm production deploy is verified end to end, fix stale merge refs ([e527f87](https://github.com/ramsesoriginal/lorenzo/commit/e527f87204df26c509729568f6b0e814b867dd82))
* confirm production deploy is verified end to end, fix stale merge refs ([b6289ad](https://github.com/ramsesoriginal/lorenzo/commit/b6289ad8429a0807de28de83e0dcdedb5df9bff5))
* merge the six per-slice ER diagrams into one domain model diagram ([0749530](https://github.com/ramsesoriginal/lorenzo/commit/0749530d75c0a70fa66041f16602e6afc6a50b15))
* pass 1 — audit and correct stale documentation ([a099830](https://github.com/ramsesoriginal/lorenzo/commit/a099830d778de159d669a08ab41e13dc7c924f56))
* pass 2 — document deployment architecture and observability ([1f836c8](https://github.com/ramsesoriginal/lorenzo/commit/1f836c84cc03355ad2face8aa11db94deb8bd87f))

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.1.0...api-v0.2.0) (2026-09-08)


### Features

* **api:** add continuous deployment to Cloud Run + Neon ([2cd7938](https://github.com/ramsesoriginal/lorenzo/commit/2cd7938d926e2d5514471d1c571315759fde385f))
* **api:** add mypy type checking ([99b1e80](https://github.com/ramsesoriginal/lorenzo/commit/99b1e80962e1a2d578ffdb52aac4417badaa564d))
* **api:** add OpenTelemetry tracing (FastAPI + SQLAlchemy) ([bde94b6](https://github.com/ramsesoriginal/lorenzo/commit/bde94b6753689e44c5f8f7cbc72671acf6094d98))
* **api:** add RFC 9457 problem+json error responses ([8465f89](https://github.com/ramsesoriginal/lorenzo/commit/8465f89cd6ac0f66b6473734efae4590c07554ce))
* **api:** scaffold apps/api - infra only, no domain models yet ([dc2b916](https://github.com/ramsesoriginal/lorenzo/commit/dc2b916994b310294ba241ddda390abf23965630))
* **api:** wire up fastapi-pagination ([d052b33](https://github.com/ramsesoriginal/lorenzo/commit/d052b33a19b55f517b8941d378ba69302c38cd94))
* **infra:** add local Postgres via Docker Compose ([4daaa42](https://github.com/ramsesoriginal/lorenzo/commit/4daaa42a51c8bef16047aba66adc41e274a63d25))


### Bug Fixes

* **api:** copy README.md into the Docker build context ([4e6e7d7](https://github.com/ramsesoriginal/lorenzo/commit/4e6e7d7b51e5cfe68825a99fb8b7c3333055fb3f))
* **api:** copy README.md into the Docker build context ([d88fdac](https://github.com/ramsesoriginal/lorenzo/commit/d88fdac826bfa7d2def8001171578583dd47cc92))
* **api:** drop Neon's channel_binding param for asyncpg too ([3751955](https://github.com/ramsesoriginal/lorenzo/commit/3751955740c339077fbf05cb45c61a8a70689020))
* **api:** drop Neon's channel_binding param for asyncpg too ([1caec90](https://github.com/ramsesoriginal/lorenzo/commit/1caec904dd85e2c044e5b5215e473f4e76ee65a7))
* **api:** let uv own the Python version, not mise, and target 3.14 ([896e4ea](https://github.com/ramsesoriginal/lorenzo/commit/896e4ea14c3421072c1af51ee258c5c6c68de1c4))
* **api:** listen on Cloud Run's $PORT instead of a hardcoded 8000 ([52773f8](https://github.com/ramsesoriginal/lorenzo/commit/52773f8d463c8deabee7c1831867c8e2fef64791))
* **api:** listen on Cloud Run's $PORT instead of a hardcoded 8000 ([d06c395](https://github.com/ramsesoriginal/lorenzo/commit/d06c3951ebe9bf458a56b481f8bdd2d93db5a484))
* **api:** rewrite Neon's sslmode query param for asyncpg ([6e78f2e](https://github.com/ramsesoriginal/lorenzo/commit/6e78f2edc248fdc0f9930c546a2914eb43df7c53))
* **api:** rewrite Neon's sslmode query param for asyncpg ([8cf6349](https://github.com/ramsesoriginal/lorenzo/commit/8cf6349dab30192bf2dc424dfcd5f5aae77620db))
* **ci:** three real failures from the first actual CI run on this PR ([927b71d](https://github.com/ramsesoriginal/lorenzo/commit/927b71d4cc064c900685048a17df6c8869aab86f))

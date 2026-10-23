:robot: I have created a release *beep* *boop*
---


<details><summary>account-hub: 2.0.0</summary>

## [2.0.0](https://github.com/ramsesoriginal/lorenzo/compare/account-hub-v1.1.0...account-hub-v2.0.0) (2026-10-23)


###   BREAKING CHANGES

* **api:** generic entry reads include the observance kind.
* **api:** generic entry reads include calendar_period and event kinds.

### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub,cli:** a public repository needs no invitation in the copy verdict ([00b3414](https://github.com/ramsesoriginal/lorenzo/commit/00b3414d8d076bdacb2c18aa111f403cbed633a1))
* **account-hub:** a campaign's own word for its GM, and the settings field for it (ADR 0294) ([d6e7398](https://github.com/ramsesoriginal/lorenzo/commit/d6e739870332f479c12075af6b544bc7470eb907))
* **account-hub:** campaign GMs can edit their campaign ([fb890ad](https://github.com/ramsesoriginal/lorenzo/commit/fb890ad4a8648f25ba8b6edc811f861c5a1b9442))
* **account-hub:** Discover and a repository's storefront (ADR 0292) ([73cd5d8](https://github.com/ramsesoriginal/lorenzo/commit/73cd5d8311eb91fa00b49d88fd5b24eefc172f6f))
* **account-hub:** Discover and a repository's storefront (ADR 0292) ([c880d02](https://github.com/ramsesoriginal/lorenzo/commit/c880d0223cac3fd23e04f76259a895ae621ccd1e))
* **account-hub:** fetch a repository's picture with the token ([d6a9dca](https://github.com/ramsesoriginal/lorenzo/commit/d6a9dcae782034c675e9a8e280fbc7f275cbe6b7)), closes [#747](https://github.com/ramsesoriginal/lorenzo/issues/747)
* **account-hub:** label facts in repository listings ([a8fe130](https://github.com/ramsesoriginal/lorenzo/commit/a8fe13004e7a40da053533c9dea65b1d4155a22a))
* **account-hub:** look inside a repository, and choose what people can look at (ADR 0293) ([c32729a](https://github.com/ramsesoriginal/lorenzo/commit/c32729af622bed88183f79a537e98af2c4431c72))
* **account-hub:** look inside a repository, the showcase and the lock (ADR 0293) ([7688810](https://github.com/ramsesoriginal/lorenzo/commit/7688810676fdca7a89d9d30eb2165ae6b6dd5d47))
* **account-hub:** no Unpublish for a public repository; links for public dependents ([36f008a](https://github.com/ramsesoriginal/lorenzo/commit/36f008a9dc3e9cef8e7f8e66d9889c62f92c78da)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **account-hub:** People with Authors and a panel for invite links ([5436025](https://github.com/ramsesoriginal/lorenzo/commit/54360258300b31abc37c50d34a1abe6988c353de)), closes [#547](https://github.com/ramsesoriginal/lorenzo/issues/547)
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** say a repository is full in the copy wizard, and test it ([66859ea](https://github.com/ramsesoriginal/lorenzo/commit/66859ea6af1d364f49daa3ba4fd813426576007a)), closes [#745](https://github.com/ramsesoriginal/lorenzo/issues/745)
* **account-hub:** show the publisher and a report link, name only invited libraries, and ask for the terms line ([03da3b8](https://github.com/ramsesoriginal/lorenzo/commit/03da3b8992b27f8f4e8b6d5037977770e1c745e7)), closes [#746](https://github.com/ramsesoriginal/lorenzo/issues/746)
* **account-hub:** Studio says a release was refused for coming too soon, and when the next can be made ([40a7868](https://github.com/ramsesoriginal/lorenzo/commit/40a78687c599790c314a50f1d1d52f45e1ee69c3))
* **account-hub:** Studio says a repository is off Discover and cannot be made public ([c623ae0](https://github.com/ramsesoriginal/lorenzo/commit/c623ae075c70c0e983233a709ea35a0ee9da89d5))
* **account-hub:** Studio's visibility switch (ADR 0290) ([ff4fca1](https://github.com/ramsesoriginal/lorenzo/commit/ff4fca102a6a934bedcb482fa0fd4b1d1b4440d3))
* **account-hub:** Studio's visibility switch (ADR 0290) ([2d37b03](https://github.com/ramsesoriginal/lorenzo/commit/2d37b0337195a96aebf95f7f92813611ed11c508)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **api:** author recurring calendar observances ([4ba7416](https://github.com/ramsesoriginal/lorenzo/commit/4ba741698272c501641d3a8fdd55baeaa3fca50b))
* **api:** record calendar periods and dated events ([68271be](https://github.com/ramsesoriginal/lorenzo/commit/68271be3afafde20180b4568f466dd4209c9ebd8))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the maintainer's quota numbers, and the copy engines are exempt ([56cb4dd](https://github.com/ramsesoriginal/lorenzo/commit/56cb4dd9f4692d9c7d07eb30d2ef85885bbbf23a))
* **api:** the release fan-out as a table, and a cooldown between releases (ADR 0301) ([e78a1b2](https://github.com/ramsesoriginal/lorenzo/commit/e78a1b2ea51230c0dcc6b636b813c8a74c408e86))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* include fact labels in the information bundle stack ([e73f6e7](https://github.com/ramsesoriginal/lorenzo/commit/e73f6e715d759c6862468fe5ef6a316bfe3ac3e1))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **calendars:** complete CI and shelf integration ([6a4a84a](https://github.com/ramsesoriginal/lorenzo/commit/6a4a84a2571af456f46d2813c7dfff0434dc8f40))
* **ci:** format account-hub and beings, keep bench e2e unconfigured, size the nav toggle ([82a0db9](https://github.com/ramsesoriginal/lorenzo/commit/82a0db98f55427dffb4b5599c7c32c5a21d12b4b))
* D6d's optional user does not start a sweep, and D6e's tests accept the terms ([e4e13b3](https://github.com/ramsesoriginal/lorenzo/commit/e4e13b3f5f58053eb98469601e25c772618e4b68)), closes [#748](https://github.com/ramsesoriginal/lorenzo/issues/748)
* increase picture upload limits to 10 MB ([e787b11](https://github.com/ramsesoriginal/lorenzo/commit/e787b11095956f3a66d8d066cfebc0a99caf0912))
* increase picture upload limits to 10 MB ([e27de26](https://github.com/ramsesoriginal/lorenzo/commit/e27de26af7b92d60d8a00877a78e3ec484e89b25))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* take HTML comments out of the wording scans one span at a time ([19066bc](https://github.com/ramsesoriginal/lorenzo/commit/19066bc80f182ef2c28f5553757fa6c87bef4913)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)
</details>

<details><summary>api: 1.0.0</summary>

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.7.0...api-v1.0.0) (2026-10-23)


###   BREAKING CHANGES

* **api:** Entry-kind responses include scene, scene_appearance and session per ADR 0317.
* **api:** Entry-kind responses include scene, scene_appearance and session per ADR 0317.
* **api:** generic entry reads include the observance kind.
* **api:** generic entry reads include calendar_period and event kinds.
* **api:** calendar widens the closed entry and repository kind response enums.
* **api:** Entry kind responses can include fact, as accepted in ADR 0305. Closed-enum consumers must support this kind.

### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** Studio's visibility switch (ADR 0290) ([ff4fca1](https://github.com/ramsesoriginal/lorenzo/commit/ff4fca102a6a934bedcb482fa0fd4b1d1b4440d3))
* **api:** a GM's title per campaign (ADR 0294) ([1fad9bc](https://github.com/ramsesoriginal/lorenzo/commit/1fad9bc8d11e664422e53b7f4e7290aa6f11f88e)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)
* **api:** a public repository is made private and not unpublished; dependents say whether the caller owns them ([c91ad45](https://github.com/ramsesoriginal/lorenzo/commit/c91ad45c674a29619a4c815207df82e31128c710))
* **api:** add canonical facts with explicit outer audiences and subjects ([b81a0c1](https://github.com/ramsesoriginal/lorenzo/commit/b81a0c1d66199b66b8b25fd829a6fba6829558c4))
* **api:** add tenant being stat group and CLI settings ([767b25a](https://github.com/ramsesoriginal/lorenzo/commit/767b25a36c851dc04520f2ce6a2c921769c2bdd8))
* **api:** an Author's reach over the entry, profile and vocabulary routes main added ([0d88e6e](https://github.com/ramsesoriginal/lorenzo/commit/0d88e6e2381de58141adaa9d73d44f6e35d8fad2))
* **api:** announce a release through a table with a cursor, and hold a public repository's releases apart ([eab17b6](https://github.com/ramsesoriginal/lorenzo/commit/eab17b60c38b99f45a5f54ce5321cbb96837060d))
* **api:** ask a signed-in user for a private repository's picture ([ed20b42](https://github.com/ramsesoriginal/lorenzo/commit/ed20b42cca1f731097e762298166f9f08589fa13))
* **api:** author and calculate calendars ([bd45cba](https://github.com/ramsesoriginal/lorenzo/commit/bd45cba1e97c98e5fd4784ca5ddf5be148454236))
* **api:** author recurring calendar observances ([4ba7416](https://github.com/ramsesoriginal/lorenzo/commit/4ba741698272c501641d3a8fdd55baeaa3fca50b))
* **api:** count the libraries that copied a repository, name its publishers, add the report link and the terms line ([e84470b](https://github.com/ramsesoriginal/lorenzo/commit/e84470b5a327a8cf50d43326d5c3f3fe6c8e7365))
* **api:** declare canonical fact response compatibility ([e0cf960](https://github.com/ramsesoriginal/lorenzo/commit/e0cf96032a926a51eaf692b4ac52d4744c4246a7))
* **api:** declare Session and Scene kind response extensions ([20d2023](https://github.com/ramsesoriginal/lorenzo/commit/20d20233a9885d9aa586a4984ad73e804250f6bc))
* **api:** declare Session and Scene kind response extensions ([7e79ebd](https://github.com/ramsesoriginal/lorenzo/commit/7e79ebd071f79ca5a054e5f72595150062a90fec))
* **api:** Discover, the listing and the storefront (ADR 0292) ([186c195](https://github.com/ramsesoriginal/lorenzo/commit/186c195581e9c2098fde00e922c841c0b3e6529b)), closes [#725](https://github.com/ramsesoriginal/lorenzo/issues/725)
* **api:** edit ordered information bundles with retry-safe payloads ([ab79dd0](https://github.com/ramsesoriginal/lorenzo/commit/ab79dd0fb469e109e32fccabf979586e10528620))
* **api:** operators delist a repository, and suspending an account delists what it owns ([4e3e084](https://github.com/ramsesoriginal/lorenzo/commit/4e3e0843a3a88d680b4eaafd5fea84c7966514e9))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** quotas on a repository ([c2f3426](https://github.com/ramsesoriginal/lorenzo/commit/c2f34264be29d2bd694095056f9eefe15036467c))
* **api:** read private bundles through their existing edit gate ([b036ad5](https://github.com/ramsesoriginal/lorenzo/commit/b036ad56b213c14f4d3b07a77bfa6fa132a462b1))
* **api:** record calendar periods and dated events ([68271be](https://github.com/ramsesoriginal/lorenzo/commit/68271be3afafde20180b4568f466dd4209c9ebd8))
* **api:** replace information audiences atomically with version guards ([2f2209a](https://github.com/ramsesoriginal/lorenzo/commit/2f2209a94092c276c3610a4369bb00dfdf880bb1))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** tenant being stat group and CLI settings ([3f6cf10](https://github.com/ramsesoriginal/lorenzo/commit/3f6cf10890563eefee197bb6e8a3ebcaf593eeec))
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
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **api:** who may read a public repository (ADR 0287) ([15869f2](https://github.com/ramsesoriginal/lorenzo/commit/15869f2a6d2fae77df6de21edd73e23d3afd6fc8)), closes [#702](https://github.com/ramsesoriginal/lorenzo/issues/702)
* **beings:** delete beings and settle their inventory ([49e000d](https://github.com/ramsesoriginal/lorenzo/commit/49e000df9beae15a84d09bf3f29fab95dfe90eef))
* **beings:** delete beings and settle their inventory ([46ad48e](https://github.com/ramsesoriginal/lorenzo/commit/46ad48e4b8397ef2a9974aa7d57329ee6cda879e))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** add calendar authoring and browsing app ([db7f60f](https://github.com/ramsesoriginal/lorenzo/commit/db7f60f2c3e8b5d4396645b7e5675cf090159f31))
* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** collaborate on Events and Facts by role and authorship ([fddf76b](https://github.com/ramsesoriginal/lorenzo/commit/fddf76b1a040f700f5e5eab0d65254fa5a6dec06))
* **calendars:** create group snapshots from all participating beings ([4275cb7](https://github.com/ramsesoriginal/lorenzo/commit/4275cb73242eb6fe4b8fb1020ad511c43a6d6f88))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** import reviewed calendar documents atomically ([9481515](https://github.com/ramsesoriginal/lorenzo/commit/9481515604ef3768eefcb937cc75abe6b57056e1))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **calendars:** record Event order and causal relationships ([fce69d4](https://github.com/ramsesoriginal/lorenzo/commit/fce69d49e72ec8efdac6bb42efe56aeb92416159))
* **calendars:** record Event order and causal relationships ([181c763](https://github.com/ramsesoriginal/lorenzo/commit/181c763c64ce3d2f6b266bc8902bf497a61fbf9f))
* **calendars:** record optional learning at Events ([55e6b1b](https://github.com/ramsesoriginal/lorenzo/commit/55e6b1b00bba255ca4d6b76332a5bd3ce374124c))
* **calendars:** record optional learning at Events ([11f1ec2](https://github.com/ramsesoriginal/lorenzo/commit/11f1ec20f047437dfa4aa27fe3ebce0bd835c337))
* **calendars:** share reader-scoped Event order ([1c79072](https://github.com/ramsesoriginal/lorenzo/commit/1c79072787c281f0f9c72256ca6daf7e2921cabc))
* **calendars:** share reader-scoped Event order ([b087172](https://github.com/ramsesoriginal/lorenzo/commit/b087172db6ed2f2192040dadc1cad0be793ad39b))
* **cli:** author stat vocabulary and render entry sheets ([c00a635](https://github.com/ramsesoriginal/lorenzo/commit/c00a635e5fbdccf3cd2c1cab6bfa5b53643537b6))
* **clocks:** add declared ratios and permitted conversion ([f47ed96](https://github.com/ramsesoriginal/lorenzo/commit/f47ed96a6c0c7493512ed9151811fea6e7237a03))
* **clocks:** declared ratios and reader-scoped conversion ([351787b](https://github.com/ramsesoriginal/lorenzo/commit/351787b86ae80513f892c233d150c4bc3b5a963e))
* merge canonical facts beneath information bundles ([957fd1f](https://github.com/ramsesoriginal/lorenzo/commit/957fd1f5901e8ba2b198cd9a0b3e486f1dfc970b))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** connect reusable Scenes and Session world references ([ead4c38](https://github.com/ramsesoriginal/lorenzo/commit/ead4c387c3caf6fd1e5f2409838abd140923a9d4))
* **sessions:** connect reusable Scenes and Session world references ([9bb1bb2](https://github.com/ramsesoriginal/lorenzo/commit/9bb1bb228d00d5d118b20715851e0aed7db9cb32))
* **sessions:** prepare Sessions and Scenes with scoped notes ([87c0145](https://github.com/ramsesoriginal/lorenzo/commit/87c0145aa6470d7fcaadcc78ebb3e3ae7b18d5d6))
* **sessions:** prepare Sessions and Scenes with scoped notes ([3fe68f6](https://github.com/ramsesoriginal/lorenzo/commit/3fe68f6319c682294d4897b265277d30f3236e7c))
* **sessions:** record explicit Session and presentation order ([f0845ed](https://github.com/ramsesoriginal/lorenzo/commit/f0845edb50d1f5e184de65c5173282b3c3152c57))
* **sessions:** record explicit Session and presentation order ([3fe2faa](https://github.com/ramsesoriginal/lorenzo/commit/3fe2faa25a641fa6c010c41c1e52d8d4c7cff813))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **api:** delete a tenant that holds Sessions ([080a07a](https://github.com/ramsesoriginal/lorenzo/commit/080a07a06cf6fc4b598a1a4fb097befc8401b85c))
* **api:** delete a tenant that holds Sessions ([1df453d](https://github.com/ramsesoriginal/lorenzo/commit/1df453dd543d6ee2da94ac9a4099a1e38391f9ea))
* **api:** isolate period visibility subqueries ([7c49bd7](https://github.com/ramsesoriginal/lorenzo/commit/7c49bd733f2e699aa77a9410b98437377a6a315f))
* **api:** load inherited weapon stat sources for being sheets ([0e1e182](https://github.com/ramsesoriginal/lorenzo/commit/0e1e18260889ccd2b2bcc24d3312fd447389821a))
* **api:** only a repository's members read delisted on its profile ([c619b66](https://github.com/ramsesoriginal/lorenzo/commit/c619b66aaf814815f7319dc0bd9a6f17c0fa5a3a))
* **api:** preserve private NPC group management and refresh contracts ([686e012](https://github.com/ramsesoriginal/lorenzo/commit/686e012158a1a7ba7ef6751423c02d752455d52e))
* **api:** record the accepted Clock response kind ([83f1689](https://github.com/ramsesoriginal/lorenzo/commit/83f1689da0c90ff20ce2fd72eef8376b9c2ab216))
* **api:** serialize clock readings with endpoint deletion ([2407670](https://github.com/ramsesoriginal/lorenzo/commit/2407670e00154cafffda80f19496a2dcea935630))
* **api:** the invite table is the registry's invite, and the vocabulary gate reads well ([5f6a2c1](https://github.com/ramsesoriginal/lorenzo/commit/5f6a2c1f03bc1b010a44ffbd5eb2922ee4a93758))
* **api:** the profile migration follows main's latest ([8fc4953](https://github.com/ramsesoriginal/lorenzo/commit/8fc4953c035b47e82f1275eb238f33126af11f6f))
* **api:** the release document carries a stat definition's display fields ([370c47e](https://github.com/ramsesoriginal/lorenzo/commit/370c47e2af71c604fccdfcd88008c628c8489a83))
* **beings:** keep empty rows compact and cache picture bytes ([38fe9ed](https://github.com/ramsesoriginal/lorenzo/commit/38fe9ed168c302a1aa642581b47eda62eef1944e))
* **beings:** keep empty rows compact and cache picture bytes ([054b6e2](https://github.com/ramsesoriginal/lorenzo/commit/054b6e2553b60f9b1e6dce8a1ddeb88b2f1d7d36))
* **bench:** preserve participant audiences in conflict snapshots ([5197b2e](https://github.com/ramsesoriginal/lorenzo/commit/5197b2e3973d48a1d97df041d333ac986ed4c3eb))
* **calendars:** complete CI and shelf integration ([6a4a84a](https://github.com/ramsesoriginal/lorenzo/commit/6a4a84a2571af456f46d2813c7dfff0434dc8f40))
* D6d's optional user does not start a sweep, and D6e's tests accept the terms ([e4e13b3](https://github.com/ramsesoriginal/lorenzo/commit/e4e13b3f5f58053eb98469601e25c772618e4b68)), closes [#748](https://github.com/ramsesoriginal/lorenzo/issues/748)
* increase picture upload limits to 10 MB ([e787b11](https://github.com/ramsesoriginal/lorenzo/commit/e787b11095956f3a66d8d066cfebc0a99caf0912))
* increase picture upload limits to 10 MB ([e27de26](https://github.com/ramsesoriginal/lorenzo/commit/e27de26af7b92d60d8a00877a78e3ec484e89b25))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* **sessions:** preserve drafts while reviewing concurrent edits ([e54bef2](https://github.com/ramsesoriginal/lorenzo/commit/e54bef29fe07b0bce18dba38a2c5db9b36472388))
* **sessions:** preserve drafts while reviewing concurrent edits ([0e11f13](https://github.com/ramsesoriginal/lorenzo/commit/0e11f13c3193650ff1a4902b4bfdd5e659ad0ac1))


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
* **api:** use indexed Event name lookups under RLS ([ca303b0](https://github.com/ramsesoriginal/lorenzo/commit/ca303b057fb10c41c7cc0a3fb52983ec026f3a6e))
* **api:** v_effective_stat, v_item and v_item_instance resolve per entity ([c3a9b3a](https://github.com/ramsesoriginal/lorenzo/commit/c3a9b3a5aca11fea50be4da8d5a6ed1397f5a874))
* **api:** write routes answer with the reader, and join to-one relationships ([91f80c6](https://github.com/ramsesoriginal/lorenzo/commit/91f80c6477eec22eb911baf15179de1f527ee983))
* **api:** write routes cost what they write ([0d47c97](https://github.com/ramsesoriginal/lorenzo/commit/0d47c97b26bec7f15493b64462bb3fe9bed6d17b))
* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))


### Documentation

* **adr:** the Author role is ADR 0219 ([9e6533c](https://github.com/ramsesoriginal/lorenzo/commit/9e6533cbe4d5c48d39a196c443a2b400a4ffc9fa))
* **beings:** describe permanent being deletion ([eb5de00](https://github.com/ramsesoriginal/lorenzo/commit/eb5de004ee310cddd57d2e99399b675659234289))
* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* **operations:** going public, the edge rule for Discover and copying, and the deploy variables ([f20eceb](https://github.com/ramsesoriginal/lorenzo/commit/f20eceb3b7feafe6d6d86b81c85924158131454d))
* **operations:** going public, the edge rule for Discover and copying, and the deploy variables ([451454f](https://github.com/ramsesoriginal/lorenzo/commit/451454f3d97dc5d9d96447068453b37828f403b7)), closes [#497](https://github.com/ramsesoriginal/lorenzo/issues/497)
* refresh repository documentation and reconcile tracking checklists ([1cb303c](https://github.com/ramsesoriginal/lorenzo/commit/1cb303c7f8754e4d55bcf4db78c6133ed863664c))
* refresh shipped capabilities and repository guidance ([95e7bb8](https://github.com/ramsesoriginal/lorenzo/commit/95e7bb841a554cec4faaa385898311cefd2f78bc))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>bench: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **account-hub:** look inside a repository, the showcase and the lock (ADR 0293) ([7688810](https://github.com/ramsesoriginal/lorenzo/commit/7688810676fdca7a89d9d30eb2165ae6b6dd5d47))
* **api:** the maintainer's quota numbers, and the copy engines are exempt ([56cb4dd](https://github.com/ramsesoriginal/lorenzo/commit/56cb4dd9f4692d9c7d07eb30d2ef85885bbbf23a))
* **api:** the release fan-out as a table, and a cooldown between releases (ADR 0301) ([e78a1b2](https://github.com/ramsesoriginal/lorenzo/commit/e78a1b2ea51230c0dcc6b636b813c8a74c408e86))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **bench:** the lock on a note that is Everyone's (ADR 0293) ([ee67827](https://github.com/ramsesoriginal/lorenzo/commit/ee67827bbbad91fd64955b945c667a87934aa571))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **information-editor:** share information with characters and groups ([e962983](https://github.com/ramsesoriginal/lorenzo/commit/e962983ca059949438efc88e66f877bf1d824890))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))
* stack fact API above information audience controls ([e22f9cd](https://github.com/ramsesoriginal/lorenzo/commit/e22f9cda972aac168e200c504781766f408e168a))


### Bug Fixes

* **bench:** preserve participant audiences in conflict snapshots ([5197b2e](https://github.com/ramsesoriginal/lorenzo/commit/5197b2e3973d48a1d97df041d333ac986ed4c3eb))
* **bench:** preserve selection while the library loads ([ce5aee3](https://github.com/ramsesoriginal/lorenzo/commit/ce5aee32610ec53d1eae6b82ea21bc8d2fb2e425))
* **ci:** format account-hub and beings, keep bench e2e unconfigured, size the nav toggle ([82a0db9](https://github.com/ramsesoriginal/lorenzo/commit/82a0db98f55427dffb4b5599c7c32c5a21d12b4b))
* increase picture upload limits to 10 MB ([e787b11](https://github.com/ramsesoriginal/lorenzo/commit/e787b11095956f3a66d8d066cfebc0a99caf0912))
* increase picture upload limits to 10 MB ([e27de26](https://github.com/ramsesoriginal/lorenzo/commit/e27de26af7b92d60d8a00877a78e3ec484e89b25))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
</details>

<details><summary>cli: 0.1.0</summary>

## 0.1.0 (2026-10-23)


###   BREAKING CHANGES

* **api:** generic entry reads include the observance kind.
* **api:** generic entry reads include calendar_period and event kinds.
* **api:** calendar widens the closed entry and repository kind response enums.

### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub,cli:** a public repository needs no invitation in the copy verdict ([00b3414](https://github.com/ramsesoriginal/lorenzo/commit/00b3414d8d076bdacb2c18aa111f403cbed633a1))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** Studio says a release was refused for coming too soon, and when the next can be made ([40a7868](https://github.com/ramsesoriginal/lorenzo/commit/40a78687c599790c314a50f1d1d52f45e1ee69c3))
* **account-hub:** Studio's visibility switch (ADR 0290) ([ff4fca1](https://github.com/ramsesoriginal/lorenzo/commit/ff4fca102a6a934bedcb482fa0fd4b1d1b4440d3))
* **api:** a GM's title per campaign (ADR 0294) ([1fad9bc](https://github.com/ramsesoriginal/lorenzo/commit/1fad9bc8d11e664422e53b7f4e7290aa6f11f88e)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)
* **api:** a public repository is made private and not unpublished; dependents say whether the caller owns them ([c91ad45](https://github.com/ramsesoriginal/lorenzo/commit/c91ad45c674a29619a4c815207df82e31128c710))
* **api:** add canonical facts with explicit outer audiences and subjects ([b81a0c1](https://github.com/ramsesoriginal/lorenzo/commit/b81a0c1d66199b66b8b25fd829a6fba6829558c4))
* **api:** add tenant being stat group and CLI settings ([767b25a](https://github.com/ramsesoriginal/lorenzo/commit/767b25a36c851dc04520f2ce6a2c921769c2bdd8))
* **api:** author and calculate calendars ([bd45cba](https://github.com/ramsesoriginal/lorenzo/commit/bd45cba1e97c98e5fd4784ca5ddf5be148454236))
* **api:** author recurring calendar observances ([4ba7416](https://github.com/ramsesoriginal/lorenzo/commit/4ba741698272c501641d3a8fdd55baeaa3fca50b))
* **api:** count the libraries that copied a repository, name its publishers, add the report link and the terms line ([e84470b](https://github.com/ramsesoriginal/lorenzo/commit/e84470b5a327a8cf50d43326d5c3f3fe6c8e7365))
* **api:** Discover, the listing and the storefront (ADR 0292) ([186c195](https://github.com/ramsesoriginal/lorenzo/commit/186c195581e9c2098fde00e922c841c0b3e6529b)), closes [#725](https://github.com/ramsesoriginal/lorenzo/issues/725)
* **api:** edit ordered information bundles with retry-safe payloads ([ab79dd0](https://github.com/ramsesoriginal/lorenzo/commit/ab79dd0fb469e109e32fccabf979586e10528620))
* **api:** operators delist a repository, and suspending an account delists what it owns ([4e3e084](https://github.com/ramsesoriginal/lorenzo/commit/4e3e0843a3a88d680b4eaafd5fea84c7966514e9))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** record calendar periods and dated events ([68271be](https://github.com/ramsesoriginal/lorenzo/commit/68271be3afafde20180b4568f466dd4209c9ebd8))
* **api:** replace information audiences atomically with version guards ([2f2209a](https://github.com/ramsesoriginal/lorenzo/commit/2f2209a94092c276c3610a4369bb00dfdf880bb1))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** tenant being stat group and CLI settings ([3f6cf10](https://github.com/ramsesoriginal/lorenzo/commit/3f6cf10890563eefee197bb6e8a3ebcaf593eeec))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the flips as routes (ADR 0290) ([f576dbf](https://github.com/ramsesoriginal/lorenzo/commit/f576dbf6b4aac96ad98250c7ba9dba572c2be248))
* **api:** the flips as routes (ADR 0290) ([88a5248](https://github.com/ramsesoriginal/lorenzo/commit/88a524842773779c3ea8adc40568410bcb4d57b7)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **api:** the preview (ADR 0293) ([6cd28ec](https://github.com/ramsesoriginal/lorenzo/commit/6cd28ec3f620ab646aa3369ff88b836f0e3a65c3))
* **api:** the preview (ADR 0293) ([5244d35](https://github.com/ramsesoriginal/lorenzo/commit/5244d35d203b88cb2706e2fe417a566ce1965e5f)), closes [#726](https://github.com/ramsesoriginal/lorenzo/issues/726)
* **api:** the release fan-out as a table, and a cooldown between releases (ADR 0301) ([e78a1b2](https://github.com/ramsesoriginal/lorenzo/commit/e78a1b2ea51230c0dcc6b636b813c8a74c408e86))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **api:** who may read a public repository (ADR 0287) ([15869f2](https://github.com/ramsesoriginal/lorenzo/commit/15869f2a6d2fae77df6de21edd73e23d3afd6fc8)), closes [#702](https://github.com/ramsesoriginal/lorenzo/issues/702)
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** add calendar authoring and browsing app ([db7f60f](https://github.com/ramsesoriginal/lorenzo/commit/db7f60f2c3e8b5d4396645b7e5675cf090159f31))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** import reviewed calendar documents atomically ([9481515](https://github.com/ramsesoriginal/lorenzo/commit/9481515604ef3768eefcb937cc75abe6b57056e1))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **calendars:** record Event order and causal relationships ([fce69d4](https://github.com/ramsesoriginal/lorenzo/commit/fce69d49e72ec8efdac6bb42efe56aeb92416159))
* **calendars:** record Event order and causal relationships ([181c763](https://github.com/ramsesoriginal/lorenzo/commit/181c763c64ce3d2f6b266bc8902bf497a61fbf9f))
* **calendars:** record optional learning at Events ([55e6b1b](https://github.com/ramsesoriginal/lorenzo/commit/55e6b1b00bba255ca4d6b76332a5bd3ce374124c))
* **calendars:** record optional learning at Events ([11f1ec2](https://github.com/ramsesoriginal/lorenzo/commit/11f1ec20f047437dfa4aa27fe3ebce0bd835c337))
* **calendars:** share reader-scoped Event order ([1c79072](https://github.com/ramsesoriginal/lorenzo/commit/1c79072787c281f0f9c72256ca6daf7e2921cabc))
* **calendars:** share reader-scoped Event order ([b087172](https://github.com/ramsesoriginal/lorenzo/commit/b087172db6ed2f2192040dadc1cad0be793ad39b))
* **cli:** author stat vocabulary and render entry sheets ([c00a635](https://github.com/ramsesoriginal/lorenzo/commit/c00a635e5fbdccf3cd2c1cab6bfa5b53643537b6))
* **cli:** author stat vocabulary and render entry sheets ([821bad0](https://github.com/ramsesoriginal/lorenzo/commit/821bad082730df687219c1b7c1a0e87981924dba))
* **cli:** say how many libraries copied a repository by themselves ([e8cf5b5](https://github.com/ramsesoriginal/lorenzo/commit/e8cf5b58bdba3072c8018c192e5f40af8970a3e2))
* **clocks:** add declared ratios and permitted conversion ([f47ed96](https://github.com/ramsesoriginal/lorenzo/commit/f47ed96a6c0c7493512ed9151811fea6e7237a03))
* **clocks:** declared ratios and reader-scoped conversion ([351787b](https://github.com/ramsesoriginal/lorenzo/commit/351787b86ae80513f892c233d150c4bc3b5a963e))
* merge canonical facts beneath information bundles ([957fd1f](https://github.com/ramsesoriginal/lorenzo/commit/957fd1f5901e8ba2b198cd9a0b3e486f1dfc970b))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** connect reusable Scenes and Session world references ([ead4c38](https://github.com/ramsesoriginal/lorenzo/commit/ead4c387c3caf6fd1e5f2409838abd140923a9d4))
* **sessions:** connect reusable Scenes and Session world references ([9bb1bb2](https://github.com/ramsesoriginal/lorenzo/commit/9bb1bb228d00d5d118b20715851e0aed7db9cb32))
* **sessions:** prepare Sessions and Scenes with scoped notes ([87c0145](https://github.com/ramsesoriginal/lorenzo/commit/87c0145aa6470d7fcaadcc78ebb3e3ae7b18d5d6))
* **sessions:** prepare Sessions and Scenes with scoped notes ([3fe68f6](https://github.com/ramsesoriginal/lorenzo/commit/3fe68f6319c682294d4897b265277d30f3236e7c))
* **sessions:** record explicit Session and presentation order ([f0845ed](https://github.com/ramsesoriginal/lorenzo/commit/f0845edb50d1f5e184de65c5173282b3c3152c57))
* **sessions:** record explicit Session and presentation order ([3fe2faa](https://github.com/ramsesoriginal/lorenzo/commit/3fe2faa25a641fa6c010c41c1e52d8d4c7cff813))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **api:** only a repository's members read delisted on its profile ([c619b66](https://github.com/ramsesoriginal/lorenzo/commit/c619b66aaf814815f7319dc0bd9a6f17c0fa5a3a))
* **api:** preserve private NPC group management and refresh contracts ([686e012](https://github.com/ramsesoriginal/lorenzo/commit/686e012158a1a7ba7ef6751423c02d752455d52e))
* **cli:** show calendar import activity and allow longer waits ([aa46080](https://github.com/ramsesoriginal/lorenzo/commit/aa46080f03e3df17825c0758b691b825afa110a0))
* **cli:** show calendar import activity and allow longer waits ([2ad1f1e](https://github.com/ramsesoriginal/lorenzo/commit/2ad1f1e1c47903affd028207465bb9d9207f00c5))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))


### Documentation

* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>inventory-web: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.1.0...inventory-web-v1.2.0) (2026-10-23)


### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **information-editor:** edit ordered text and picture bundles ([ba65c9f](https://github.com/ramsesoriginal/lorenzo/commit/ba65c9fdf26d9048d1491ab55944f0bab7379559))
* **information-editor:** share information with characters and groups ([e962983](https://github.com/ramsesoriginal/lorenzo/commit/e962983ca059949438efc88e66f877bf1d824890))
* **inventory-web:** a campaign's title for its game master (ADR 0294) ([ce144e0](https://github.com/ramsesoriginal/lorenzo/commit/ce144e0264d6aef89ddcd48aaca37e2b936601ef))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* stack fact API above information audience controls ([e22f9cd](https://github.com/ramsesoriginal/lorenzo/commit/e22f9cda972aac168e200c504781766f408e168a))


### Bug Fixes

* **inventory-web:** say GM when a campaign of the being can't be listed (ADR 0294) ([0ebcd4e](https://github.com/ramsesoriginal/lorenzo/commit/0ebcd4e3dc928e1b31c09a16cadff389d62cd620))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* take HTML comments out of the wording scans one span at a time ([19066bc](https://github.com/ramsesoriginal/lorenzo/commit/19066bc80f182ef2c28f5553757fa6c87bef4913)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
</details>

<details><summary>loot-bot: 0.5.0</summary>

## [0.5.0](https://github.com/ramsesoriginal/lorenzo/compare/loot-bot-v0.4.0...loot-bot-v0.5.0) (2026-10-23)


### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **loot-bot:** /whoami names the GM with the campaigns' title (ADR 0294) ([831071d](https://github.com/ramsesoriginal/lorenzo/commit/831071d3b9cc6cd3aab9cccb5f877865cdbc62cb))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>brand: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/brand-v1.1.0...brand-v1.2.0) (2026-10-23)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **brand:** add the eight moon phases to the icon atlas ([bac7400](https://github.com/ramsesoriginal/lorenzo/commit/bac7400c9f8df7260251c464e9acd4619c1b7d8b))
* **brand:** add the eight moon phases to the icon atlas ([cd16e26](https://github.com/ramsesoriginal/lorenzo/commit/cd16e260fd145577035422d8f855a365d76fafee))
* **brand:** add the eight moon phases to the icon atlas ([643577a](https://github.com/ramsesoriginal/lorenzo/commit/643577a4abbd86de6230eba3a10b16941d57fce2))
* **calendars:** stand on the shared brand ([8daa5cd](https://github.com/ramsesoriginal/lorenzo/commit/8daa5cd9a1a94d637be595c7ef1cc6e527714f1d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **brand:** --text-tertiary meets WCAG AA in the light theme ([140a354](https://github.com/ramsesoriginal/lorenzo/commit/140a3543c1ebeda496109e2e01f1d5e096449ebb))
* **brand:** --text-tertiary meets WCAG AA in the light theme ([8878d61](https://github.com/ramsesoriginal/lorenzo/commit/8878d61a62238726e0bf0832c7791af017c2eaca))
* **brand:** footer text uses the secondary text colour ([0847f5f](https://github.com/ramsesoriginal/lorenzo/commit/0847f5fc1b7ea715fa45ee54907c4f419345d42f))
* **ci:** format account-hub and beings, keep bench e2e unconfigured, size the nav toggle ([82a0db9](https://github.com/ramsesoriginal/lorenzo/commit/82a0db98f55427dffb4b5599c7c32c5a21d12b4b))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>api-client: 1.0.0</summary>

## 1.0.0 (2026-10-23)


###   BREAKING CHANGES

* **api:** generic entry reads include the observance kind.
* **api:** generic entry reads include calendar_period and event kinds.
* **api:** calendar widens the closed entry and repository kind response enums.

### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **account-hub:** Studio's visibility switch (ADR 0290) ([ff4fca1](https://github.com/ramsesoriginal/lorenzo/commit/ff4fca102a6a934bedcb482fa0fd4b1d1b4440d3))
* **api:** a GM's title per campaign (ADR 0294) ([1fad9bc](https://github.com/ramsesoriginal/lorenzo/commit/1fad9bc8d11e664422e53b7f4e7290aa6f11f88e)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)
* **api:** a public repository is made private and not unpublished; dependents say whether the caller owns them ([c91ad45](https://github.com/ramsesoriginal/lorenzo/commit/c91ad45c674a29619a4c815207df82e31128c710))
* **api:** add canonical facts with explicit outer audiences and subjects ([b81a0c1](https://github.com/ramsesoriginal/lorenzo/commit/b81a0c1d66199b66b8b25fd829a6fba6829558c4))
* **api:** add tenant being stat group and CLI settings ([767b25a](https://github.com/ramsesoriginal/lorenzo/commit/767b25a36c851dc04520f2ce6a2c921769c2bdd8))
* **api:** an Author's reach over the entry, profile and vocabulary routes main added ([0d88e6e](https://github.com/ramsesoriginal/lorenzo/commit/0d88e6e2381de58141adaa9d73d44f6e35d8fad2))
* **api:** ask a signed-in user for a private repository's picture ([ed20b42](https://github.com/ramsesoriginal/lorenzo/commit/ed20b42cca1f731097e762298166f9f08589fa13))
* **api:** author and calculate calendars ([bd45cba](https://github.com/ramsesoriginal/lorenzo/commit/bd45cba1e97c98e5fd4784ca5ddf5be148454236))
* **api:** author recurring calendar observances ([4ba7416](https://github.com/ramsesoriginal/lorenzo/commit/4ba741698272c501641d3a8fdd55baeaa3fca50b))
* **api:** count the libraries that copied a repository, name its publishers, add the report link and the terms line ([e84470b](https://github.com/ramsesoriginal/lorenzo/commit/e84470b5a327a8cf50d43326d5c3f3fe6c8e7365))
* **api:** Discover, the listing and the storefront (ADR 0292) ([186c195](https://github.com/ramsesoriginal/lorenzo/commit/186c195581e9c2098fde00e922c841c0b3e6529b)), closes [#725](https://github.com/ramsesoriginal/lorenzo/issues/725)
* **api:** edit ordered information bundles with retry-safe payloads ([ab79dd0](https://github.com/ramsesoriginal/lorenzo/commit/ab79dd0fb469e109e32fccabf979586e10528620))
* **api:** operators delist a repository, and suspending an account delists what it owns ([4e3e084](https://github.com/ramsesoriginal/lorenzo/commit/4e3e0843a3a88d680b4eaafd5fea84c7966514e9))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** read private bundles through their existing edit gate ([b036ad5](https://github.com/ramsesoriginal/lorenzo/commit/b036ad56b213c14f4d3b07a77bfa6fa132a462b1))
* **api:** record calendar periods and dated events ([68271be](https://github.com/ramsesoriginal/lorenzo/commit/68271be3afafde20180b4568f466dd4209c9ebd8))
* **api:** replace information audiences atomically with version guards ([2f2209a](https://github.com/ramsesoriginal/lorenzo/commit/2f2209a94092c276c3610a4369bb00dfdf880bb1))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** tenant being stat group and CLI settings ([3f6cf10](https://github.com/ramsesoriginal/lorenzo/commit/3f6cf10890563eefee197bb6e8a3ebcaf593eeec))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the flips as routes (ADR 0290) ([f576dbf](https://github.com/ramsesoriginal/lorenzo/commit/f576dbf6b4aac96ad98250c7ba9dba572c2be248))
* **api:** the flips as routes (ADR 0290) ([88a5248](https://github.com/ramsesoriginal/lorenzo/commit/88a524842773779c3ea8adc40568410bcb4d57b7)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **api:** the preview (ADR 0293) ([6cd28ec](https://github.com/ramsesoriginal/lorenzo/commit/6cd28ec3f620ab646aa3369ff88b836f0e3a65c3))
* **api:** the preview (ADR 0293) ([5244d35](https://github.com/ramsesoriginal/lorenzo/commit/5244d35d203b88cb2706e2fe417a566ce1965e5f)), closes [#726](https://github.com/ramsesoriginal/lorenzo/issues/726)
* **api:** the release fan-out as a table, and a cooldown between releases (ADR 0301) ([e78a1b2](https://github.com/ramsesoriginal/lorenzo/commit/e78a1b2ea51230c0dcc6b636b813c8a74c408e86))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **api:** who may read a public repository (ADR 0287) ([15869f2](https://github.com/ramsesoriginal/lorenzo/commit/15869f2a6d2fae77df6de21edd73e23d3afd6fc8)), closes [#702](https://github.com/ramsesoriginal/lorenzo/issues/702)
* **beings:** delete beings and settle their inventory ([49e000d](https://github.com/ramsesoriginal/lorenzo/commit/49e000df9beae15a84d09bf3f29fab95dfe90eef))
* **beings:** delete beings and settle their inventory ([46ad48e](https://github.com/ramsesoriginal/lorenzo/commit/46ad48e4b8397ef2a9974aa7d57329ee6cda879e))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** add calendar authoring and browsing app ([db7f60f](https://github.com/ramsesoriginal/lorenzo/commit/db7f60f2c3e8b5d4396645b7e5675cf090159f31))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** collaborate on Events and Facts by role and authorship ([fddf76b](https://github.com/ramsesoriginal/lorenzo/commit/fddf76b1a040f700f5e5eab0d65254fa5a6dec06))
* **calendars:** create group snapshots from all participating beings ([4275cb7](https://github.com/ramsesoriginal/lorenzo/commit/4275cb73242eb6fe4b8fb1020ad511c43a6d6f88))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** import reviewed calendar documents atomically ([9481515](https://github.com/ramsesoriginal/lorenzo/commit/9481515604ef3768eefcb937cc75abe6b57056e1))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **calendars:** record Event order and causal relationships ([fce69d4](https://github.com/ramsesoriginal/lorenzo/commit/fce69d49e72ec8efdac6bb42efe56aeb92416159))
* **calendars:** record Event order and causal relationships ([181c763](https://github.com/ramsesoriginal/lorenzo/commit/181c763c64ce3d2f6b266bc8902bf497a61fbf9f))
* **calendars:** record optional learning at Events ([55e6b1b](https://github.com/ramsesoriginal/lorenzo/commit/55e6b1b00bba255ca4d6b76332a5bd3ce374124c))
* **calendars:** record optional learning at Events ([11f1ec2](https://github.com/ramsesoriginal/lorenzo/commit/11f1ec20f047437dfa4aa27fe3ebce0bd835c337))
* **calendars:** share reader-scoped Event order ([1c79072](https://github.com/ramsesoriginal/lorenzo/commit/1c79072787c281f0f9c72256ca6daf7e2921cabc))
* **calendars:** share reader-scoped Event order ([b087172](https://github.com/ramsesoriginal/lorenzo/commit/b087172db6ed2f2192040dadc1cad0be793ad39b))
* **clocks:** add declared ratios and permitted conversion ([f47ed96](https://github.com/ramsesoriginal/lorenzo/commit/f47ed96a6c0c7493512ed9151811fea6e7237a03))
* **clocks:** declared ratios and reader-scoped conversion ([351787b](https://github.com/ramsesoriginal/lorenzo/commit/351787b86ae80513f892c233d150c4bc3b5a963e))
* merge canonical facts beneath information bundles ([957fd1f](https://github.com/ramsesoriginal/lorenzo/commit/957fd1f5901e8ba2b198cd9a0b3e486f1dfc970b))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** connect reusable Scenes and Session world references ([ead4c38](https://github.com/ramsesoriginal/lorenzo/commit/ead4c387c3caf6fd1e5f2409838abd140923a9d4))
* **sessions:** connect reusable Scenes and Session world references ([9bb1bb2](https://github.com/ramsesoriginal/lorenzo/commit/9bb1bb228d00d5d118b20715851e0aed7db9cb32))
* **sessions:** prepare Sessions and Scenes with scoped notes ([87c0145](https://github.com/ramsesoriginal/lorenzo/commit/87c0145aa6470d7fcaadcc78ebb3e3ae7b18d5d6))
* **sessions:** prepare Sessions and Scenes with scoped notes ([3fe68f6](https://github.com/ramsesoriginal/lorenzo/commit/3fe68f6319c682294d4897b265277d30f3236e7c))
* **sessions:** record explicit Session and presentation order ([f0845ed](https://github.com/ramsesoriginal/lorenzo/commit/f0845edb50d1f5e184de65c5173282b3c3152c57))
* **sessions:** record explicit Session and presentation order ([3fe2faa](https://github.com/ramsesoriginal/lorenzo/commit/3fe2faa25a641fa6c010c41c1e52d8d4c7cff813))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **api:** delete a tenant that holds Sessions ([080a07a](https://github.com/ramsesoriginal/lorenzo/commit/080a07a06cf6fc4b598a1a4fb097befc8401b85c))
* **api:** only a repository's members read delisted on its profile ([c619b66](https://github.com/ramsesoriginal/lorenzo/commit/c619b66aaf814815f7319dc0bd9a6f17c0fa5a3a))
* **beings:** keep empty rows compact and cache picture bytes ([38fe9ed](https://github.com/ramsesoriginal/lorenzo/commit/38fe9ed168c302a1aa642581b47eda62eef1944e))
* **beings:** keep empty rows compact and cache picture bytes ([054b6e2](https://github.com/ramsesoriginal/lorenzo/commit/054b6e2553b60f9b1e6dce8a1ddeb88b2f1d7d36))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
</details>

<details><summary>converters: 0.1.0</summary>

## 0.1.0 (2026-10-23)


### Features

* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **converters:** convert donjon calendars to native documents ([d432959](https://github.com/ramsesoriginal/lorenzo/commit/d432959a9c1c8bc2b3a99bd00e74d057149e6f76))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Documentation

* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>inventory-names: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>brand-package: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/brand-package-v1.1.0...brand-package-v1.2.0) (2026-10-23)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzoscript: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
</details>

<details><summary>lorenzoscript-editor: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>beings: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* a GM's title per campaign (ADR 0294) ([5f71cae](https://github.com/ramsesoriginal/lorenzo/commit/5f71caeba76e0795e781017e0a6c281a896c72b8))
* **account-hub:** look inside a repository, the showcase and the lock (ADR 0293) ([7688810](https://github.com/ramsesoriginal/lorenzo/commit/7688810676fdca7a89d9d30eb2165ae6b6dd5d47))
* **beings:** a campaign's title for its game master (ADR 0294) ([24d9776](https://github.com/ramsesoriginal/lorenzo/commit/24d9776e94973321b06cda944342f3096181058c))
* **beings:** delete beings and settle their inventory ([49e000d](https://github.com/ramsesoriginal/lorenzo/commit/49e000df9beae15a84d09bf3f29fab95dfe90eef))
* **beings:** delete beings and settle their inventory ([46ad48e](https://github.com/ramsesoriginal/lorenzo/commit/46ad48e4b8397ef2a9974aa7d57329ee6cda879e))
* **beings:** show being group and valued stats ([984a633](https://github.com/ramsesoriginal/lorenzo/commit/984a633ba7deef7c94c6f234b3a7d6fe71df44cf))
* **beings:** show being group and valued stats ([b58f949](https://github.com/ramsesoriginal/lorenzo/commit/b58f94903324ba4cba75ecd24953d95fa57aaff3))
* **beings:** show list portraits and desktop picture previews ([77a35d3](https://github.com/ramsesoriginal/lorenzo/commit/77a35d31430fb1a95b430fdd401eba4cb409646a))
* **beings:** show list portraits and desktop picture previews ([3113c57](https://github.com/ramsesoriginal/lorenzo/commit/3113c5725ee6c71267c33490de6366f91bbefc07))
* **beings:** show ordered participating Event titles ([17c8074](https://github.com/ramsesoriginal/lorenzo/commit/17c8074e6a7b7b82e585bc8734556cec297552b4))
* **beings:** the lock on a note of a repository's being (ADR 0293) ([dcb79e4](https://github.com/ramsesoriginal/lorenzo/commit/dcb79e4fd18b683d2779e766408b1ed891250192))
* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **information-editor:** edit ordered text and picture bundles ([ba65c9f](https://github.com/ramsesoriginal/lorenzo/commit/ba65c9fdf26d9048d1491ab55944f0bab7379559))
* **information-editor:** share information with characters and groups ([e962983](https://github.com/ramsesoriginal/lorenzo/commit/e962983ca059949438efc88e66f877bf1d824890))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))
* stack fact API above information audience controls ([e22f9cd](https://github.com/ramsesoriginal/lorenzo/commit/e22f9cda972aac168e200c504781766f408e168a))


### Bug Fixes

* **beings:** await deletion errors before navigating ([f02bf3c](https://github.com/ramsesoriginal/lorenzo/commit/f02bf3c39f9bf912f2fb3386c57e312127bf1bad))
* **beings:** keep empty rows compact and cache picture bytes ([38fe9ed](https://github.com/ramsesoriginal/lorenzo/commit/38fe9ed168c302a1aa642581b47eda62eef1944e))
* **beings:** keep empty rows compact and cache picture bytes ([054b6e2](https://github.com/ramsesoriginal/lorenzo/commit/054b6e2553b60f9b1e6dce8a1ddeb88b2f1d7d36))
* **ci:** format account-hub and beings, keep bench e2e unconfigured, size the nav toggle ([82a0db9](https://github.com/ramsesoriginal/lorenzo/commit/82a0db98f55427dffb4b5599c7c32c5a21d12b4b))
* increase picture upload limits to 10 MB ([e787b11](https://github.com/ramsesoriginal/lorenzo/commit/e787b11095956f3a66d8d066cfebc0a99caf0912))
* increase picture upload limits to 10 MB ([e27de26](https://github.com/ramsesoriginal/lorenzo/commit/e27de26af7b92d60d8a00877a78e3ec484e89b25))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* take HTML comments out of the wording scans one span at a time ([19066bc](https://github.com/ramsesoriginal/lorenzo/commit/19066bc80f182ef2c28f5553757fa6c87bef4913)), closes [#733](https://github.com/ramsesoriginal/lorenzo/issues/733)


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
</details>

<details><summary>stat-values: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>inventory-mobile: 0.2.0</summary>

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-mobile-v0.1.0...inventory-mobile-v0.2.0) (2026-10-23)


### Features

* **inventory-mobile:** add native Android inventory app ([04a0473](https://github.com/ramsesoriginal/lorenzo/commit/04a04731d09000dcc620af286ace4b84b7132695))
* **inventory-mobile:** add the native Android inventory companion (ADR 0291) ([81c39b1](https://github.com/ramsesoriginal/lorenzo/commit/81c39b16c8fbd4a7e9d6338cd3febfb3c83d249b))
* **inventory-mobile:** keep ordered picture notes and audiences ([150fd67](https://github.com/ramsesoriginal/lorenzo/commit/150fd67dd02bf6f8e40b34654862ccb32ea19b4a))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **inventory-mobile:** bring validated onboarding fixes into the ADR PR ([528e232](https://github.com/ramsesoriginal/lorenzo/commit/528e23224d5503d2fb6417396ca801a5c1af1b02))
* **inventory-mobile:** complete app registration and Android CI setup ([b178cce](https://github.com/ramsesoriginal/lorenzo/commit/b178ccefd75766385f8f657f3791ea8f80d9fbc6))
* **inventory-mobile:** fence responses across same-token sessions ([da8db35](https://github.com/ramsesoriginal/lorenzo/commit/da8db35daf5a6e37e7d8d70e56c90ae25d06e05f))
* **inventory-mobile:** merge registration and CI fixes ([d552ad3](https://github.com/ramsesoriginal/lorenzo/commit/d552ad3a66cbca3b037830c0650237156467c959))
* **inventory-mobile:** merge SDK package and attribution fixes ([51cfff2](https://github.com/ramsesoriginal/lorenzo/commit/51cfff2206a2e0bccf41c895d81870039858ba1b))
* **inventory-mobile:** use the published SDK package and lint attribution ([c3e7855](https://github.com/ramsesoriginal/lorenzo/commit/c3e785542e69a45cd3d61036b142ace187070858))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>information-editor: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **bench:** author facts and targeted information bundles ([b50b2c7](https://github.com/ramsesoriginal/lorenzo/commit/b50b2c75eb498e49c100b285fad74ee499a567b9))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** add calendar authoring and browsing app ([db7f60f](https://github.com/ramsesoriginal/lorenzo/commit/db7f60f2c3e8b5d4396645b7e5675cf090159f31))
* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **information-editor:** edit ordered text and picture bundles ([ba65c9f](https://github.com/ramsesoriginal/lorenzo/commit/ba65c9fdf26d9048d1491ab55944f0bab7379559))
* **information-editor:** share information with characters and groups ([e962983](https://github.com/ramsesoriginal/lorenzo/commit/e962983ca059949438efc88e66f877bf1d824890))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* stack fact API above information audience controls ([e22f9cd](https://github.com/ramsesoriginal/lorenzo/commit/e22f9cda972aac168e200c504781766f408e168a))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>app-shell: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>period-picker: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **period-picker:** one picker for a day, a month, a year or several ([ffdf958](https://github.com/ramsesoriginal/lorenzo/commit/ffdf958ec711e2194195c9a3a65c92ad7580ae97))
* **period-picker:** one picker for a day, a month, a year or several ([4adfe6e](https://github.com/ramsesoriginal/lorenzo/commit/4adfe6e342964eede5a4c258c35588b4b730bc68))
* **period-picker:** one picker for a day, a month, a year or several ([8e8c533](https://github.com/ramsesoriginal/lorenzo/commit/8e8c533a4b724ba4d30f47b65c4ecde7f46bfbcc))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** choose periods with the period picker ([bbc0904](https://github.com/ramsesoriginal/lorenzo/commit/bbc0904ba3896b5a58f337a0204625ca426ed372))
* **sessions:** choose periods with the period picker ([1696625](https://github.com/ramsesoriginal/lorenzo/commit/169662583c12c72fa90a9bc182808fe9a5ab22e3))
* **sessions:** choose periods with the period picker ([1ae23b0](https://github.com/ramsesoriginal/lorenzo/commit/1ae23b0d5c1c6628b8b13bf9d4d188c2e68a848a))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>read-cache: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **calendars:** use the shared read cache and read the start-up data in parallel ([8a0722a](https://github.com/ramsesoriginal/lorenzo/commit/8a0722ac7de4befa889f01d047f35df6e0ea2a93))
* **calendars:** use the shared read cache and read the start-up data in parallel ([9ed59a7](https://github.com/ramsesoriginal/lorenzo/commit/9ed59a7825d5050e0da1e474d6be9468ec64d114))
* **read-cache:** a viewer-scoped cache in front of fetch, and a bounded prefetch queue ([c175d67](https://github.com/ramsesoriginal/lorenzo/commit/c175d677171cdacf9efdeaa8995157e5f810bd6a))
* **read-cache:** a viewer-scoped cache in front of fetch, and a bounded prefetch queue ([f852b9e](https://github.com/ramsesoriginal/lorenzo/commit/f852b9e0214701ef5191206b3ab1a91e1d6b57fe))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>inventory-ios: 0.2.0</summary>

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-ios-v0.1.0...inventory-ios-v0.2.0) (2026-10-23)


### Features

* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **inventory-ios:** add native inventory and durable information notes ([3df49a2](https://github.com/ramsesoriginal/lorenzo/commit/3df49a26150fd44ae5b7c2cf09f6c57ded76f336))
* **inventory-ios:** complete native media and AltStore packaging ([4d49ebe](https://github.com/ramsesoriginal/lorenzo/commit/4d49ebe1239f51ea76bbe8fcbc4935923d655981))
* **inventory-ios:** native inventory and AltStore testing ([a2e9b4d](https://github.com/ramsesoriginal/lorenzo/commit/a2e9b4d29aecbe1a2a08d4f569df0cc5caaee83f))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **inventory-ios:** fence revoked caches and repair native call syntax ([838219a](https://github.com/ramsesoriginal/lorenzo/commit/838219a678f3e7008360bdd2405304e7286591f6))
* **inventory-ios:** finish draft controls and native test syntax ([65465e2](https://github.com/ramsesoriginal/lorenzo/commit/65465e2eb9f813bda83b6ada09ac0ae481735572))
* **inventory-ios:** finish native module access and offline pictures ([8cfbc79](https://github.com/ramsesoriginal/lorenzo/commit/8cfbc79b013a0b80869199e26cc2a493b5c51793))
* **inventory-ios:** keep stat aggregation simple for Swift compiler ([2735e1c](https://github.com/ramsesoriginal/lorenzo/commit/2735e1c99408256ee2199c493da6d1b2c0933ae1))
* **inventory-ios:** preserve editor audiences and isolate simulator configuration ([0195c92](https://github.com/ramsesoriginal/lorenzo/commit/0195c92ff0426f1cc0131d7abdc001895a0ad487))
* **inventory-ios:** preserve multipart replay ids and newest reads ([b37fe71](https://github.com/ramsesoriginal/lorenzo/commit/b37fe7116b2e3795456b23b32368d3b17b9457dd))
* **inventory-ios:** preserve Swift literals and test durable replay ([e6db072](https://github.com/ramsesoriginal/lorenzo/commit/e6db0725992402430af3d797e8b9a81e01cce739))
* **inventory-ios:** sign simulator builds for private Keychain access ([25a4596](https://github.com/ramsesoriginal/lorenzo/commit/25a459609ad1d8eb41bd577b2d04b30a1dd5975e))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzo-calendar: 0.1.0</summary>

## 0.1.0 (2026-10-23)


###   BREAKING CHANGES

* **api:** generic entry reads include the observance kind.
* **api:** calendar widens the closed entry and repository kind response enums.

### Features

* **api:** author and calculate calendars ([bd45cba](https://github.com/ramsesoriginal/lorenzo/commit/bd45cba1e97c98e5fd4784ca5ddf5be148454236))
* **api:** author recurring calendar observances ([4ba7416](https://github.com/ramsesoriginal/lorenzo/commit/4ba741698272c501641d3a8fdd55baeaa3fca50b))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **converters:** convert donjon calendars to native documents ([d432959](https://github.com/ramsesoriginal/lorenzo/commit/d432959a9c1c8bc2b3a99bd00e74d057149e6f76))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))


### Documentation

* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>calendars: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **calendars:** add a whole-year view with shared month rendering ([80f9672](https://github.com/ramsesoriginal/lorenzo/commit/80f9672f91ac2365a3430b54e21e95e54aa352c2))
* **calendars:** add a whole-year view with shared month rendering ([499bb79](https://github.com/ramsesoriginal/lorenzo/commit/499bb7973e4c73a23429377c33cb7cb6612749a1))
* **calendars:** add calendar authoring and browsing app ([c5d9d60](https://github.com/ramsesoriginal/lorenzo/commit/c5d9d60ed58f03ce05e700876ae0169e667f6dff))
* **calendars:** add calendar authoring and browsing app ([db7f60f](https://github.com/ramsesoriginal/lorenzo/commit/db7f60f2c3e8b5d4396645b7e5675cf090159f31))
* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
* **calendars:** align layout and voice with the shared brand ([85559de](https://github.com/ramsesoriginal/lorenzo/commit/85559dec0fa18c01e383ae450331f45fab7108a3))
* **calendars:** align layout and voice with the shared brand ([7c791b4](https://github.com/ramsesoriginal/lorenzo/commit/7c791b4a26c5491ddf4a5e5cc69ef4099fc50508))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** collaborate on Events and Facts by role and authorship ([fddf76b](https://github.com/ramsesoriginal/lorenzo/commit/fddf76b1a040f700f5e5eab0d65254fa5a6dec06))
* **calendars:** create group snapshots from all participating beings ([4275cb7](https://github.com/ramsesoriginal/lorenzo/commit/4275cb73242eb6fe4b8fb1020ad511c43a6d6f88))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** draw the Clocks pages and panels in the shared brand ([9a6a195](https://github.com/ramsesoriginal/lorenzo/commit/9a6a19585b9f7d5d750c053d811c7be437ab6339))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **calendars:** read a month's notes and dated entries in one request ([b42d954](https://github.com/ramsesoriginal/lorenzo/commit/b42d954186135a4567661ee819eff3f34680063e))
* **calendars:** read a month's notes and dated entries in one request ([0f2c8a2](https://github.com/ramsesoriginal/lorenzo/commit/0f2c8a2dbb9428b58bf627ef27754df2fef9e4d8))
* **calendars:** record Event order and causal relationships ([fce69d4](https://github.com/ramsesoriginal/lorenzo/commit/fce69d49e72ec8efdac6bb42efe56aeb92416159))
* **calendars:** record Event order and causal relationships ([181c763](https://github.com/ramsesoriginal/lorenzo/commit/181c763c64ce3d2f6b266bc8902bf497a61fbf9f))
* **calendars:** record optional learning at Events ([55e6b1b](https://github.com/ramsesoriginal/lorenzo/commit/55e6b1b00bba255ca4d6b76332a5bd3ce374124c))
* **calendars:** record optional learning at Events ([11f1ec2](https://github.com/ramsesoriginal/lorenzo/commit/11f1ec20f047437dfa4aa27fe3ebce0bd835c337))
* **calendars:** share reader-scoped Event order ([1c79072](https://github.com/ramsesoriginal/lorenzo/commit/1c79072787c281f0f9c72256ca6daf7e2921cabc))
* **calendars:** share reader-scoped Event order ([b087172](https://github.com/ramsesoriginal/lorenzo/commit/b087172db6ed2f2192040dadc1cad0be793ad39b))
* **calendars:** show day content with compact moon phases ([51f8739](https://github.com/ramsesoriginal/lorenzo/commit/51f873937531f8af8000419195d2bfc0f158bd61))
* **calendars:** show day content with compact moon phases ([f25344f](https://github.com/ramsesoriginal/lorenzo/commit/f25344ffb320a0fc30fc479cbfd8f23eee0e64be))
* **calendars:** stand on the shared brand ([8daa5cd](https://github.com/ramsesoriginal/lorenzo/commit/8daa5cd9a1a94d637be595c7ef1cc6e527714f1d))
* **calendars:** stand on the shared brand ([5be57d3](https://github.com/ramsesoriginal/lorenzo/commit/5be57d378eefae7e497aa9f442bf9d775a3d04f3))
* **calendars:** stand on the shared brand ([43ea7e7](https://github.com/ramsesoriginal/lorenzo/commit/43ea7e7242ad66d20d907db0bbb7ad29e3d27af1))
* **calendars:** stand on the shared brand ([f136c34](https://github.com/ramsesoriginal/lorenzo/commit/f136c342434ce709768d9ba6594887f594a188ae))
* **calendars:** use the shared read cache and read the start-up data in parallel ([8a0722a](https://github.com/ramsesoriginal/lorenzo/commit/8a0722ac7de4befa889f01d047f35df6e0ea2a93))
* **calendars:** use the shared read cache and read the start-up data in parallel ([9ed59a7](https://github.com/ramsesoriginal/lorenzo/commit/9ed59a7825d5050e0da1e474d6be9468ec64d114))
* **clocks:** add declared ratios and permitted conversion ([f47ed96](https://github.com/ramsesoriginal/lorenzo/commit/f47ed96a6c0c7493512ed9151811fea6e7237a03))
* **clocks:** declared ratios and reader-scoped conversion ([351787b](https://github.com/ramsesoriginal/lorenzo/commit/351787b86ae80513f892c233d150c4bc3b5a963e))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **calendars:** drop the local tertiary-text override ([6cf37d5](https://github.com/ramsesoriginal/lorenzo/commit/6cf37d5c6b639682b0244d6b2503318c7d8ad6f9))
* **calendars:** drop the local tertiary-text override ([ad309ba](https://github.com/ramsesoriginal/lorenzo/commit/ad309bab316087d1475c850c9b2ddda48d55860b))
* **calendars:** drop the local tertiary-text override ([a6b7b11](https://github.com/ramsesoriginal/lorenzo/commit/a6b7b11da142b1ccb94b54835191e43ab9a53c8b))
* **calendars:** preserve the selected theme across navigation ([ad94ca9](https://github.com/ramsesoriginal/lorenzo/commit/ad94ca945927bf1a1ad51f844c59db00211046a4))
* **calendars:** preserve the selected theme across navigation ([5e0f2ac](https://github.com/ramsesoriginal/lorenzo/commit/5e0f2ac5b167bdd6d206f3e07d3e4c9efa5721bd))
* **calendars:** qualify reader order labels and format guide ([c6d503b](https://github.com/ramsesoriginal/lorenzo/commit/c6d503b1804a599d508e8c08898b42e2eaf792f4))
* **calendars:** recover a stale remembered library ([95c858d](https://github.com/ramsesoriginal/lorenzo/commit/95c858d1010ee1a96f7ca0080bcdc3c40b45ab06))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([9345e54](https://github.com/ramsesoriginal/lorenzo/commit/9345e549319c28a6dfae92c976db4a9edc26bc50))
* **calendars:** cache scoped reads and prefetch likely navigation ([dc2663c](https://github.com/ramsesoriginal/lorenzo/commit/dc2663c8366933e8a2b805a4fc76248cb1b59022))
* **calendars:** read a calendar and its entry together ([d48a57c](https://github.com/ramsesoriginal/lorenzo/commit/d48a57c4479f604d34cfa9d08b184a9833011b98))
* **calendars:** read a calendar and its entry together ([8b7f293](https://github.com/ramsesoriginal/lorenzo/commit/8b7f293d519857ec146b0b07c37104da980ef820))
</details>

<details><summary>sessions: 1.0.0</summary>

## 1.0.0 (2026-10-23)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **sessions:** a save draws again only the panels it changed ([58b2ed4](https://github.com/ramsesoriginal/lorenzo/commit/58b2ed4302c9318322257164f94e29b170e54243))
* **sessions:** a save draws again only the panels it changed ([17dc889](https://github.com/ramsesoriginal/lorenzo/commit/17dc889056ec038e4f76da25c85dd293468048ca))
* **sessions:** choose periods with the period picker ([bbc0904](https://github.com/ramsesoriginal/lorenzo/commit/bbc0904ba3896b5a58f337a0204625ca426ed372))
* **sessions:** choose periods with the period picker ([1696625](https://github.com/ramsesoriginal/lorenzo/commit/169662583c12c72fa90a9bc182808fe9a5ab22e3))
* **sessions:** choose periods with the period picker ([1ae23b0](https://github.com/ramsesoriginal/lorenzo/commit/1ae23b0d5c1c6628b8b13bf9d4d188c2e68a848a))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** connect reusable Scenes and Session world references ([ead4c38](https://github.com/ramsesoriginal/lorenzo/commit/ead4c387c3caf6fd1e5f2409838abd140923a9d4))
* **sessions:** connect reusable Scenes and Session world references ([9bb1bb2](https://github.com/ramsesoriginal/lorenzo/commit/9bb1bb228d00d5d118b20715851e0aed7db9cb32))
* **sessions:** prepare Sessions and Scenes with scoped notes ([87c0145](https://github.com/ramsesoriginal/lorenzo/commit/87c0145aa6470d7fcaadcc78ebb3e3ae7b18d5d6))
* **sessions:** prepare Sessions and Scenes with scoped notes ([3fe68f6](https://github.com/ramsesoriginal/lorenzo/commit/3fe68f6319c682294d4897b265277d30f3236e7c))
* **sessions:** record explicit Session and presentation order ([f0845ed](https://github.com/ramsesoriginal/lorenzo/commit/f0845edb50d1f5e184de65c5173282b3c3152c57))
* **sessions:** record explicit Session and presentation order ([3fe2faa](https://github.com/ramsesoriginal/lorenzo/commit/3fe2faa25a641fa6c010c41c1e52d8d4c7cff813))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))
* **sessions:** stand on the shared brand (ADR 0322) ([9fb9fdb](https://github.com/ramsesoriginal/lorenzo/commit/9fb9fdb1c93fdf379a5c8b357cd6c2a731c21475))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* **sessions:** preserve drafts while reviewing concurrent edits ([e54bef2](https://github.com/ramsesoriginal/lorenzo/commit/e54bef29fe07b0bce18dba38a2c5db9b36472388))
* **sessions:** preserve drafts while reviewing concurrent edits ([0e11f13](https://github.com/ramsesoriginal/lorenzo/commit/0e11f13c3193650ff1a4902b4bfdd5e659ad0ac1))


### Performance Improvements

* **sessions:** ask for every panel together, keep reads, open the roster on demand ([b0bf081](https://github.com/ramsesoriginal/lorenzo/commit/b0bf08182b5d636fd466a388a7250b7798a1689b))
* **sessions:** ask for every panel together, keep reads, open the roster on demand ([006cdd9](https://github.com/ramsesoriginal/lorenzo/commit/006cdd9c6e461c933a8fb7bd2497473ddde5b32a))
* **sessions:** read a Session ahead when its link is about to be followed ([f4f6924](https://github.com/ramsesoriginal/lorenzo/commit/f4f6924d02f0ba6cd07324015ab0a13e64b7e1f5))
* **sessions:** read a Session ahead when its link is about to be followed ([0aa61f8](https://github.com/ramsesoriginal/lorenzo/commit/0aa61f8e4b72e475bfc1c5cbbf6d7d454ee2ca47))
</details>

---
This PR was generated with [Release Please](https://github.com/googleapis/release-please). See [documentation](https://github.com/googleapis/release-please#release-please).
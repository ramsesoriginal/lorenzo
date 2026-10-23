# Changelog

## 1.0.0 (2026-10-23)


### ⚠ BREAKING CHANGES

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

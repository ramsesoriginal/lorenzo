# Changelog

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/cli-v0.1.0...cli-v1.0.0) (2026-11-20)


### ⚠ BREAKING CHANGES

* **cli:** `lorenzo seed` and `lorenzo unseed` are removed; use `lorenzo apply --starter neutral` (and `--starter dnd5e`). D&D's stats are renamed with a dnd5e_ prefix.
* **cli:** the MPMB, inventory and calendar commands have new names.
* **cli:** writes in a script need --yes, a refused or declined write exits 2 instead of 1, and --json lists are objects with a format.

### Features

* **api,maps:** a Location's Map count, the Maps it is on and where each character says it is ([#1214](https://github.com/ramsesoriginal/lorenzo/issues/1214)) ([4656234](https://github.com/ramsesoriginal/lorenzo/commit/465623443b61820f280f505dbcb9832dd7783a5b))
* **api,maps:** the Locations pages' Map count, On these Maps and Where is… ([#1214](https://github.com/ramsesoriginal/lorenzo/issues/1214)) ([1fadc57](https://github.com/ramsesoriginal/lorenzo/commit/1fadc57e48473b2619231f764d9825d28b021c9e))
* **api,writing:** undo a manuscript split (ADR 0513) ([839f0ef](https://github.com/ramsesoriginal/lorenzo/commit/839f0eff12b384ce340da3095ba8f3bcef04e3f5))
* **api:** a being's recent stat changes, for the History of its sheet (ADR 0525) ([c082e77](https://github.com/ramsesoriginal/lorenzo/commit/c082e77a3d9e34104ec0a07245136f0db22e3456))
* **api:** a library can let the controller of a holder award it a feature (ADR 0465) ([34438d3](https://github.com/ramsesoriginal/lorenzo/commit/34438d344cacf21f304f0984f4358acb39349bb2))
* **api:** a write of a stat or of a formula can answer with warnings (RFC 0055 V4) ([9842c53](https://github.com/ramsesoriginal/lorenzo/commit/9842c536053980b0341c70bc571c076176166dcc))
* **api:** list the Editions shared with me for review ([caab79f](https://github.com/ramsesoriginal/lorenzo/commit/caab79f95ad6d0df31f885a8d7a38488f1d37e1e))
* **api:** the dice formula builds a dice value from a count and sides; RFC 0056 is built (RFC 0056 D3) ([0c0cd97](https://github.com/ramsesoriginal/lorenzo/commit/0c0cd979ec0fe9d0e37ce07bc318618439a85beb))
* **api:** the dice formula builds a dice value from a count and sides; RFC 0056 is built (RFC 0056 D3) ([a1e1253](https://github.com/ramsesoriginal/lorenzo/commit/a1e12539acfb234da57cedcd511fe192e1f6e807))
* **api:** the dice value type, stored as parts and written as notation (RFC 0056 D1) ([4c26bc8](https://github.com/ramsesoriginal/lorenzo/commit/4c26bc84b09ce8e2afa4b6eaf3cbd9fce5ba98be))
* **api:** the dice_value formula reads the minimum, maximum or average of a dice stat (RFC 0056 D2) ([04f29a3](https://github.com/ramsesoriginal/lorenzo/commit/04f29a35cebf32f074690d2f58fc88255881f0e9))
* **api:** undo a Scene extraction (ADR 0517) ([1e772cd](https://github.com/ramsesoriginal/lorenzo/commit/1e772cd85572fd81451909002e8da9b2a7d38c65))
* **api:** updates track game systems and templates (ADR 0467) ([93f1bb7](https://github.com/ramsesoriginal/lorenzo/commit/93f1bb789e052142a796516ef2d79e76ba3340e8))
* **api:** updates track game systems and templates (ADR 0467) ([2f8cd1b](https://github.com/ramsesoriginal/lorenzo/commit/2f8cd1b8016f10ab6356cdaa24e5d9b72d6e6ebf))
* **cli:** complete library slugs and names from a private cache ([687d2af](https://github.com/ramsesoriginal/lorenzo/commit/687d2afc41a276cadf71dbb902964fefb26f89fb))
* **cli:** D&D armour class bonuses, and MPMB's ways of working out AC ([13773bd](https://github.com/ramsesoriginal/lorenzo/commit/13773bd5fb8c1134f1d9cca97899f24ec2b11967))
* **cli:** D&D armour class from the armour and shield a character wears ([2f43793](https://github.com/ramsesoriginal/lorenzo/commit/2f4379303cbf8f8f0efb10dd277641253c5c022a))
* **cli:** D&D armour class from the best way a feature gives ([516bac0](https://github.com/ramsesoriginal/lorenzo/commit/516bac096769a4175cf60032de03c16ec233ae01))
* **cli:** features, grant rules, prerequisites and grants (RFC 0057 C8) ([54e4497](https://github.com/ramsesoriginal/lorenzo/commit/54e4497d6a9fa4c170fbf1f9d7e0c1e7d424f725))
* **cli:** formulas of every kind, in the document and with lorenzo formula (RFC 0057 C6) ([87b094d](https://github.com/ramsesoriginal/lorenzo/commit/87b094d921a87e10197018d7daac17f0a8f2fbd4))
* **cli:** lorenzo check, the vocabulary check for a person and for CI (RFC 0057 C9) ([4f1ea5f](https://github.com/ramsesoriginal/lorenzo/commit/4f1ea5f5137ef9c095449206dbb61ae723a493b1))
* **cli:** one console, one write contract, JSON with a format (RFC 0057 C2) ([d877b5a](https://github.com/ramsesoriginal/lorenzo/commit/d877b5a8d6cda2b028340c6d768951d14ad8ff75))
* **cli:** replace the seed with the neutral, dnd5e and wrath-and-glory starters ([1d0857e](https://github.com/ramsesoriginal/lorenzo/commit/1d0857eb52524d0e57a2bc92e5a6f0347656b3b3))
* **cli:** show systems, templates and unit warnings in the repo commands ([6fa37c0](https://github.com/ramsesoriginal/lorenzo/commit/6fa37c053d55a98be45b0f1fb663bece4fb748ec))
* **cli:** templates, campaigns and beings, and reads by system (RFC 0057 C7) ([a364232](https://github.com/ramsesoriginal/lorenzo/commit/a3642320191cd030a1223785edf0319ac8a933c7))
* **cli:** the core rulebook's species, archetypes and talents in the wrath-and-glory starter ([de0ddc6](https://github.com/ramsesoriginal/lorenzo/commit/de0ddc6e6e8f4c5f55e0bb022c03a4e385f981d5))
* **cli:** the importers move under `lorenzo import` and `export` (RFC 0057 C3) ([1bad0f1](https://github.com/ramsesoriginal/lorenzo/commit/1bad0f1e3c919ddd7a0ed7934cf3417e4c1a167b))
* **cli:** the library document, lorenzo system and the vocabulary with systems, roles and bounds (RFC 0057 C5) ([5973565](https://github.com/ramsesoriginal/lorenzo/commit/5973565fb5c7fb3f8ca7cb5c7b6e31892a88fa6c))
* **cli:** typed operations for systems, templates, features, grants and the check (RFC 0057 C4) ([44eb099](https://github.com/ramsesoriginal/lorenzo/commit/44eb099ee45c579700c4b20f8584cc9dd8744faf))
* **writing:** apply reviewed manuscript compositions atomically ([d6f7156](https://github.com/ramsesoriginal/lorenzo/commit/d6f71560ee54c1c5ace67ebb3ea2e9f4c79f54a8))
* **writing:** export saved manuscripts as source and printable PDF ([afcb7f2](https://github.com/ramsesoriginal/lorenzo/commit/afcb7f245ff891f17fd9d661207ee4f707af22b6))
* **writing:** move a block to another Chapter from its menu (ADR 0520) ([3be2d82](https://github.com/ramsesoriginal/lorenzo/commit/3be2d821984a4e4c26d16df003af11a987cf5afa))
* **writing:** the shelf shows when each work was edited, and counts them (ADR 0519) ([36b7c7f](https://github.com/ramsesoriginal/lorenzo/commit/36b7c7f894f2881490b5560cc2a6695ece4b288d))


### Bug Fixes

* **cli:** check the wrath-and-glory starter against the core rulebook ([76f6dc4](https://github.com/ramsesoriginal/lorenzo/commit/76f6dc4b62f1996c7d0c272d0b8dc9aa6fc5ed24))
* **cli:** count a long plan by kind, and name a system's root by its slug ([4e669e4](https://github.com/ramsesoriginal/lorenzo/commit/4e669e4a3a8e28f46b9200743334c25cff20ffc0))
* **cli:** draw a being's sheet through the template its campaign picks ([6d60972](https://github.com/ramsesoriginal/lorenzo/commit/6d609722c105a505f350cc72a1feefcd2819fb85))
* **cli:** feature list as a table with slug, category and values ([bac622d](https://github.com/ramsesoriginal/lorenzo/commit/bac622dba0c640581b5f7769346eaf1aa05d17b4))
* **cli:** never cut a feature's slug in feature list ([0aabc96](https://github.com/ramsesoriginal/lorenzo/commit/0aabc96f7e5041662b2ee1c724602e8d9076ce1e))
* **cli:** regenerate the models with the repo's own command ([69b41e2](https://github.com/ramsesoriginal/lorenzo/commit/69b41e29503d1af045996d34f46c00b39ed391fd))
* **cli:** say a finding many entries share once, with where ([665621b](https://github.com/ramsesoriginal/lorenzo/commit/665621bed3439a077f34a043d15fb4522b38c897))
* **cli:** say a repository's roles plainly in repo contents ([eca0eba](https://github.com/ramsesoriginal/lorenzo/commit/eca0eba35b97417017a10a374ea3ffff692e1cbe))
* regenerate clients after Writing stack integration ([6dbdef9](https://github.com/ramsesoriginal/lorenzo/commit/6dbdef955e99c6d56e67f06f1dc4bd15085f9257))


### Performance Improvements

* **cli:** load command groups and models when they are used (RFC 0057 C1) ([2d50492](https://github.com/ramsesoriginal/lorenzo/commit/2d50492ecf5b0afdb67f7e6d218afad1cdf85951))


### Documentation

* **adr:** renumber RFC 0057's ADRs 0481-0493 to 0495-0507 ([092693b](https://github.com/ramsesoriginal/lorenzo/commit/092693b9b395925b22201b2129320259ee486fd8))
* **cli:** a walkthrough from an empty table to a D&D character ([27625d1](https://github.com/ramsesoriginal/lorenzo/commit/27625d18725fdb30ad4ddfaacaf500cc7a240103))
* **cli:** a walkthrough from an empty table to a D&D character ([9c0586a](https://github.com/ramsesoriginal/lorenzo/commit/9c0586a9306f86cd5591662769b22520d5979977))
* **cli:** escape the pipes in the README's command table (RFC 0057 C7) ([ddd85bf](https://github.com/ramsesoriginal/lorenzo/commit/ddd85bfb31c415903b3dc7bd70dcba04d24b81b8))

## 0.1.0 (2026-10-29)


### ⚠ BREAKING CHANGES

* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364)
* **writing:** entity kind responses add scene_telling and Writing entry responses add scene, scene_telling and biography. Generated clients and exact accepted OpenAPI findings are updated together.
* **api:** the generic `kinds` responses can now carry the value `map`.
* **api:** the kinds an entry's responses carry can now include `location`.

### Features

* **api:** a stored picture fingerprint, SVG pictures and a Map's layers (ADR 0360, 0361) ([5c8f9ac](https://github.com/ramsesoriginal/lorenzo/commit/5c8f9ac649559a14f31a5f4fc367fbcbf3c75bf0))
* **api:** atomic batch placement writes and a Map's theme name (ADR 0351, 0352) ([8853de4](https://github.com/ramsesoriginal/lorenzo/commit/8853de4d5eb8e14b01e0762414cfbec591c0ec6e))
* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364) ([d31b770](https://github.com/ramsesoriginal/lorenzo/commit/d31b77002046e108bdaf222d8ae2ead984b56347))
* **api:** grid systems, a Map's view and the hex rule (ADR 0354) ([1a6b866](https://github.com/ramsesoriginal/lorenzo/commit/1a6b8662538e2476991e0a0fbc223ec1ef8b8ba8))
* **api:** Locations, their part-of tree and the any-kind rule (ADR 0330, 0331) ([2f4aea2](https://github.com/ramsesoriginal/lorenzo/commit/2f4aea239d323a67455ca44d544556b23fdcfc88))
* **api:** Maps and their placements (ADR 0336 to 0338) ([7489338](https://github.com/ramsesoriginal/lorenzo/commit/7489338703d5bc74c175b6fff880d70951121bcf))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** placement and the player's whereabouts read (ADR 0333, 0334) ([def69c2](https://github.com/ramsesoriginal/lorenzo/commit/def69c25c373d816f07f63a0c814de6bde3ea0bf))
* **api:** the GM's address read and the Location lint (ADR 0335) ([3e40801](https://github.com/ramsesoriginal/lorenzo/commit/3e40801df058641e95f1d5193955fa5abce683c6))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **calendars:** record Event order and causal relationships ([fce69d4](https://github.com/ramsesoriginal/lorenzo/commit/fce69d49e72ec8efdac6bb42efe56aeb92416159))
* **calendars:** record Event order and causal relationships ([181c763](https://github.com/ramsesoriginal/lorenzo/commit/181c763c64ce3d2f6b266bc8902bf497a61fbf9f))
* **calendars:** record optional learning at Events ([55e6b1b](https://github.com/ramsesoriginal/lorenzo/commit/55e6b1b00bba255ca4d6b76332a5bd3ce374124c))
* **calendars:** record optional learning at Events ([11f1ec2](https://github.com/ramsesoriginal/lorenzo/commit/11f1ec20f047437dfa4aa27fe3ebce0bd835c337))
* **calendars:** share reader-scoped Event order ([1c79072](https://github.com/ramsesoriginal/lorenzo/commit/1c79072787c281f0f9c72256ca6daf7e2921cabc))
* **calendars:** share reader-scoped Event order ([b087172](https://github.com/ramsesoriginal/lorenzo/commit/b087172db6ed2f2192040dadc1cad0be793ad39b))
* **clocks:** add declared ratios and permitted conversion ([f47ed96](https://github.com/ramsesoriginal/lorenzo/commit/f47ed96a6c0c7493512ed9151811fea6e7237a03))
* **clocks:** declared ratios and reader-scoped conversion ([351787b](https://github.com/ramsesoriginal/lorenzo/commit/351787b86ae80513f892c233d150c4bc3b5a963e))
* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
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
* **writing:** add edition-scoped review access and private notes ([472ea2d](https://github.com/ramsesoriginal/lorenzo/commit/472ea2d767dd027da8b30ac17e698bd29a511b4c))
* **writing:** compose books editions and nested chapters ([0c97dea](https://github.com/ramsesoriginal/lorenzo/commit/0c97dea8c1e2a8f2f387ed125c29a116b3796537))
* **writing:** extract outline elements into nested chapters ([f81efc0](https://github.com/ramsesoriginal/lorenzo/commit/f81efc0e89f3c50280f1b0188dc2ff0e381ffa47))
* **writing:** move manuscript entries atomically between outlines ([8f5c912](https://github.com/ramsesoriginal/lorenzo/commit/8f5c912384907b6baa5f7c6a95cc5143a30e7a02))
* **writing:** reuse scenes through independent tellings ([2a0c4cd](https://github.com/ramsesoriginal/lorenzo/commit/2a0c4cd88e5ff0ad86d45327b2df7cf6378b942a))
* **writing:** split saved prose at safe paragraph boundaries ([242de21](https://github.com/ramsesoriginal/lorenzo/commit/242de2175415b43fecd5fc61df8a1fc71632e7cb))


### Bug Fixes

* **api:** name the frame membership response so it keeps MembershipOut free ([0ccabdd](https://github.com/ramsesoriginal/lorenzo/commit/0ccabdd03ebc3184be4d00bf814adc95c8e30268))
* **api:** preserve private NPC group management and refresh contracts ([686e012](https://github.com/ramsesoriginal/lorenzo/commit/686e012158a1a7ba7ef6751423c02d752455d52e))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* **writing:** run browser CI and refresh CLI response models ([625c37d](https://github.com/ramsesoriginal/lorenzo/commit/625c37d7e2b865ab387d42efbd785e54bf372eaa))


### Documentation

* **api,cli,loot-bot:** refresh READMEs against the code ([960f574](https://github.com/ramsesoriginal/lorenzo/commit/960f574809b4ea8668e90ce468003ab594addf4d))
* **cli:** repair the repo copy row of the commands table ([65dac4a](https://github.com/ramsesoriginal/lorenzo/commit/65dac4aaf761ad5513a8b2f8e36881abe8c82f16))
* **cli:** show the real order in the missing API URL hint ([da09bda](https://github.com/ramsesoriginal/lorenzo/commit/da09bda95a0d3803548f58ed5b345b8d21bbb103))
* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))

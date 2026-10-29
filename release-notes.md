:robot: I have created a release *beep* *boop*
---


<details><summary>account-hub: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/account-hub-v1.1.0...account-hub-v1.2.0) (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>api: 1.0.0</summary>

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.7.0...api-v1.0.0) (2026-10-29)


###   BREAKING CHANGES

* **api:** the via of an address step may now be frame, and a frame step carries an axis; accepted in openapi-breaking-accepted.txt.
* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364)
* **writing:** entity kind responses add scene_telling and Writing entry responses add scene, scene_telling and biography. Generated clients and exact accepted OpenAPI findings are updated together.
* **api:** Entity-kind responses can include book, edition and chapter as decided in ADR 0336. Clients with exhaustive kind matching must accept these values; generated clients are updated.
* **api:** the generic `kinds` responses can now carry the value `map`.
* **api:** the kinds an entry's responses carry can now include `location`.
* **api:** Entry-kind responses include scene, scene_appearance and session per ADR 0317.
* **api:** Entry-kind responses include scene, scene_appearance and session per ADR 0317.

### Features

* **api:** a stored picture fingerprint, SVG pictures and a Map's layers (ADR 0360, 0361) ([5c8f9ac](https://github.com/ramsesoriginal/lorenzo/commit/5c8f9ac649559a14f31a5f4fc367fbcbf3c75bf0))
* **api:** atomic batch placement writes and a Map's theme name (ADR 0351, 0352) ([8853de4](https://github.com/ramsesoriginal/lorenzo/commit/8853de4d5eb8e14b01e0762414cfbec591c0ec6e))
* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364) ([d31b770](https://github.com/ramsesoriginal/lorenzo/commit/d31b77002046e108bdaf222d8ae2ead984b56347))
* **api:** declare Session and Scene kind response extensions ([20d2023](https://github.com/ramsesoriginal/lorenzo/commit/20d20233a9885d9aa586a4984ad73e804250f6bc))
* **api:** declare Session and Scene kind response extensions ([7e79ebd](https://github.com/ramsesoriginal/lorenzo/commit/7e79ebd071f79ca5a054e5f72595150062a90fec))
* **api:** frames and axes, resolved along the GM address ([0892193](https://github.com/ramsesoriginal/lorenzo/commit/0892193e1c44c60c0f9231e0d2cd5f69fde52a23))
* **api:** grid systems, a Map's view and the hex rule (ADR 0354) ([1a6b866](https://github.com/ramsesoriginal/lorenzo/commit/1a6b8662538e2476991e0a0fbc223ec1ef8b8ba8))
* **api:** Location and Map preview templates (ADR 0350) ([5234b07](https://github.com/ramsesoriginal/lorenzo/commit/5234b07edfdc15087ee72fbad682095c1cf8a1cb))
* **api:** Locations, their part-of tree and the any-kind rule (ADR 0330, 0331) ([2f4aea2](https://github.com/ramsesoriginal/lorenzo/commit/2f4aea239d323a67455ca44d544556b23fdcfc88))
* **api:** Maps and their placements (ADR 0336 to 0338) ([7489338](https://github.com/ramsesoriginal/lorenzo/commit/7489338703d5bc74c175b6fff880d70951121bcf))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** placement and the player's whereabouts read (ADR 0333, 0334) ([def69c2](https://github.com/ramsesoriginal/lorenzo/commit/def69c25c373d816f07f63a0c814de6bde3ea0bf))
* **api:** the date lens on the Locations list ([32ed7f2](https://github.com/ramsesoriginal/lorenzo/commit/32ed7f2ad9db812cfc38bd9a33ce6c4e4c7e4e6a))
* **api:** the date lens on the Maps list ([849fcf6](https://github.com/ramsesoriginal/lorenzo/commit/849fcf68c196d32abd8359bfee21836a53e5cc39))
* **api:** the distance read, a bounded route search and release format 24 ([a45e90a](https://github.com/ramsesoriginal/lorenzo/commit/a45e90a3799745ead2a787ab736e4ee72ed390f6))
* **api:** the GM's address read and the Location lint (ADR 0335) ([3e40801](https://github.com/ramsesoriginal/lorenzo/commit/3e40801df058641e95f1d5193955fa5abce683c6))
* **api:** the sphere system, a projection in a Map's view and format 21 (ADR 0357) ([6918f9e](https://github.com/ramsesoriginal/lorenzo/commit/6918f9e35884908fa50d572fff547ea50927f1a1))
* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** collaborate on Events and Facts by role and authorship ([fddf76b](https://github.com/ramsesoriginal/lorenzo/commit/fddf76b1a040f700f5e5eab0d65254fa5a6dec06))
* **calendars:** create group snapshots from all participating beings ([4275cb7](https://github.com/ramsesoriginal/lorenzo/commit/4275cb73242eb6fe4b8fb1020ad511c43a6d6f88))
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
* **writing:** add standalone manuscripts with autosave and recovery ([37fae07](https://github.com/ramsesoriginal/lorenzo/commit/37fae0704eaa479db1cd05443cb7defd7e44a02d))
* **writing:** compose books editions and nested chapters ([0c97dea](https://github.com/ramsesoriginal/lorenzo/commit/0c97dea8c1e2a8f2f387ed125c29a116b3796537))
* **writing:** extract outline elements into nested chapters ([f81efc0](https://github.com/ramsesoriginal/lorenzo/commit/f81efc0e89f3c50280f1b0188dc2ff0e381ffa47))
* **writing:** move manuscript entries atomically between outlines ([8f5c912](https://github.com/ramsesoriginal/lorenzo/commit/8f5c912384907b6baa5f7c6a95cc5143a30e7a02))
* **writing:** reuse scenes through independent tellings ([2a0c4cd](https://github.com/ramsesoriginal/lorenzo/commit/2a0c4cd88e5ff0ad86d45327b2df7cf6378b942a))
* **writing:** split manuscripts between complete syntax blocks ([c6c613a](https://github.com/ramsesoriginal/lorenzo/commit/c6c613a43b56da8e8b00e75fed166b27742d5266))
* **writing:** split saved prose at safe paragraph boundaries ([242de21](https://github.com/ramsesoriginal/lorenzo/commit/242de2175415b43fecd5fc61df8a1fc71632e7cb))


### Bug Fixes

* **api:** delete a tenant that holds Sessions ([080a07a](https://github.com/ramsesoriginal/lorenzo/commit/080a07a06cf6fc4b598a1a4fb097befc8401b85c))
* **api:** delete a tenant that holds Sessions ([1df453d](https://github.com/ramsesoriginal/lorenzo/commit/1df453dd543d6ee2da94ac9a4099a1e38391f9ea))
* **api:** mark writing response kinds for release versioning ([5fc43f2](https://github.com/ramsesoriginal/lorenzo/commit/5fc43f2c4186d90aeee34ce8578a9a06d57361d9))
* **api:** name the frame membership response so it keeps MembershipOut free ([0ccabdd](https://github.com/ramsesoriginal/lorenzo/commit/0ccabdd03ebc3184be4d00bf814adc95c8e30268))
* **api:** preserve private NPC group management and refresh contracts ([686e012](https://github.com/ramsesoriginal/lorenzo/commit/686e012158a1a7ba7ef6751423c02d752455d52e))
* **api:** record approved writing kinds in compatibility gate ([9fb7307](https://github.com/ramsesoriginal/lorenzo/commit/9fb7307c9d438e8318c4ec15607704e7d671108b))
* **api:** record the accepted Clock response kind ([83f1689](https://github.com/ramsesoriginal/lorenzo/commit/83f1689da0c90ff20ce2fd72eef8376b9c2ab216))
* **api:** serialize clock readings with endpoint deletion ([2407670](https://github.com/ramsesoriginal/lorenzo/commit/2407670e00154cafffda80f19496a2dcea935630))
* **bench:** preserve participant audiences in conflict snapshots ([5197b2e](https://github.com/ramsesoriginal/lorenzo/commit/5197b2e3973d48a1d97df041d333ac986ed4c3eb))
* carry the Locations merge through the kind matrix and ports ([86170d3](https://github.com/ramsesoriginal/lorenzo/commit/86170d3a2f6f694afe24ccb836505b1895b29797))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
* **sessions:** preserve drafts while reviewing concurrent edits ([e54bef2](https://github.com/ramsesoriginal/lorenzo/commit/e54bef29fe07b0bce18dba38a2c5db9b36472388))
* **sessions:** preserve drafts while reviewing concurrent edits ([0e11f13](https://github.com/ramsesoriginal/lorenzo/commit/0e11f13c3193650ff1a4902b4bfdd5e659ad0ac1))
* **writing:** bound split dependency scans on hostile input ([c75fb48](https://github.com/ramsesoriginal/lorenzo/commit/c75fb4816fbc96a2103aa45ae83311f77b21ebde))
* **writing:** keep split text references in sync through shared writer ([bb9be24](https://github.com/ramsesoriginal/lorenzo/commit/bb9be246f4d99a58b170b10a426cf768a7f0c7c4))
* **writing:** load knowledge grants for manuscript visibility ([d6d8ba9](https://github.com/ramsesoriginal/lorenzo/commit/d6d8ba91acc16c7f269ef5628a3b111edc975ce0))


### Performance Improvements

* **api:** use indexed Event name lookups under RLS ([ca303b0](https://github.com/ramsesoriginal/lorenzo/commit/ca303b057fb10c41c7cc0a3fb52983ec026f3a6e))


### Documentation

* **api,cli,loot-bot:** refresh READMEs against the code ([960f574](https://github.com/ramsesoriginal/lorenzo/commit/960f574809b4ea8668e90ce468003ab594addf4d))
* **api:** correct stale comments and docstrings ([1dd26dd](https://github.com/ramsesoriginal/lorenzo/commit/1dd26ddd91825f0c45da020352b294cdf3d9c788))
* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* renumber the Locations date lens ADRs to 0376 and 0377 ([108285f](https://github.com/ramsesoriginal/lorenzo/commit/108285fdb3fcbf8019091c2f57b507c64b1769be))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
* **writing:** follow composition ADR renumbering ([629cd50](https://github.com/ramsesoriginal/lorenzo/commit/629cd50fb46e6b2b29fad8b1ec74e37bcf09a8f6))
</details>

<details><summary>bench: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **bench:** preserve participant audiences in conflict snapshots ([5197b2e](https://github.com/ramsesoriginal/lorenzo/commit/5197b2e3973d48a1d97df041d333ac986ed4c3eb))
* **bench:** preserve selection while the library loads ([ce5aee3](https://github.com/ramsesoriginal/lorenzo/commit/ce5aee32610ec53d1eae6b82ea21bc8d2fb2e425))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>cli: 0.1.0</summary>

## 0.1.0 (2026-10-29)


###   BREAKING CHANGES

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
</details>

<details><summary>inventory-web: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-web-v1.1.0...inventory-web-v1.2.0) (2026-10-29)


### Features

* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>loot-bot: 0.5.0</summary>

## [0.5.0](https://github.com/ramsesoriginal/lorenzo/compare/loot-bot-v0.4.0...loot-bot-v0.5.0) (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>brand: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/brand-v1.1.0...brand-v1.2.0) (2026-10-29)


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
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>api-client: 1.0.0</summary>

## 1.0.0 (2026-10-29)


###   BREAKING CHANGES

* **api:** the via of an address step may now be frame, and a frame step carries an axis; accepted in openapi-breaking-accepted.txt.
* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364)
* **writing:** entity kind responses add scene_telling and Writing entry responses add scene, scene_telling and biography. Generated clients and exact accepted OpenAPI findings are updated together.
* **api:** the generic `kinds` responses can now carry the value `map`.
* **api:** the kinds an entry's responses carry can now include `location`.

### Features

* **api:** a stored picture fingerprint, SVG pictures and a Map's layers (ADR 0360, 0361) ([5c8f9ac](https://github.com/ramsesoriginal/lorenzo/commit/5c8f9ac649559a14f31a5f4fc367fbcbf3c75bf0))
* **api:** atomic batch placement writes and a Map's theme name (ADR 0351, 0352) ([8853de4](https://github.com/ramsesoriginal/lorenzo/commit/8853de4d5eb8e14b01e0762414cfbec591c0ec6e))
* **api:** connections, hubs and the links a Map derives from them (ADR 0363, 0364) ([d31b770](https://github.com/ramsesoriginal/lorenzo/commit/d31b77002046e108bdaf222d8ae2ead984b56347))
* **api:** frames and axes, resolved along the GM address ([0892193](https://github.com/ramsesoriginal/lorenzo/commit/0892193e1c44c60c0f9231e0d2cd5f69fde52a23))
* **api:** grid systems, a Map's view and the hex rule (ADR 0354) ([1a6b866](https://github.com/ramsesoriginal/lorenzo/commit/1a6b8662538e2476991e0a0fbc223ec1ef8b8ba8))
* **api:** Location and Map preview templates (ADR 0350) ([5234b07](https://github.com/ramsesoriginal/lorenzo/commit/5234b07edfdc15087ee72fbad682095c1cf8a1cb))
* **api:** Locations, their part-of tree and the any-kind rule (ADR 0330, 0331) ([2f4aea2](https://github.com/ramsesoriginal/lorenzo/commit/2f4aea239d323a67455ca44d544556b23fdcfc88))
* **api:** Maps and their placements (ADR 0336 to 0338) ([7489338](https://github.com/ramsesoriginal/lorenzo/commit/7489338703d5bc74c175b6fff880d70951121bcf))
* **api:** periods with coordinates, per-year period summaries and a batch write ([aba5849](https://github.com/ramsesoriginal/lorenzo/commit/aba584900997843a6214c5ae8355573f9330334b))
* **api:** periods with coordinates, per-year period summaries and a batch write ([98d4358](https://github.com/ramsesoriginal/lorenzo/commit/98d43588c2c7be53398744d8aa3da641d316c3e0))
* **api:** periods with coordinates, per-year period summaries and a batch write ([e515ff8](https://github.com/ramsesoriginal/lorenzo/commit/e515ff88219e9c616ad54ed438ad3e8a4aac9fcb))
* **api:** placement and the player's whereabouts read (ADR 0333, 0334) ([def69c2](https://github.com/ramsesoriginal/lorenzo/commit/def69c25c373d816f07f63a0c814de6bde3ea0bf))
* **api:** the date lens on the Locations list ([32ed7f2](https://github.com/ramsesoriginal/lorenzo/commit/32ed7f2ad9db812cfc38bd9a33ce6c4e4c7e4e6a))
* **api:** the date lens on the Maps list ([849fcf6](https://github.com/ramsesoriginal/lorenzo/commit/849fcf68c196d32abd8359bfee21836a53e5cc39))
* **api:** the distance read, a bounded route search and release format 24 ([a45e90a](https://github.com/ramsesoriginal/lorenzo/commit/a45e90a3799745ead2a787ab736e4ee72ed390f6))
* **api:** the GM's address read and the Location lint (ADR 0335) ([3e40801](https://github.com/ramsesoriginal/lorenzo/commit/3e40801df058641e95f1d5193955fa5abce683c6))
* **calendars:** author clocks and explicit Event readings ([cc8fd76](https://github.com/ramsesoriginal/lorenzo/commit/cc8fd76bdc7b871dcf1f6b23c5a4e00b8b70eb3a))
* **calendars:** browse Events and manage participating beings ([4ec69c7](https://github.com/ramsesoriginal/lorenzo/commit/4ec69c7e8bb54df83b05a05fbc574c0a4918a27a))
* **calendars:** collaborate on Events and Facts by role and authorship ([fddf76b](https://github.com/ramsesoriginal/lorenzo/commit/fddf76b1a040f700f5e5eab0d65254fa5a6dec06))
* **calendars:** create group snapshots from all participating beings ([4275cb7](https://github.com/ramsesoriginal/lorenzo/commit/4275cb73242eb6fe4b8fb1020ad511c43a6d6f88))
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
* **writing:** add standalone manuscripts with autosave and recovery ([37fae07](https://github.com/ramsesoriginal/lorenzo/commit/37fae0704eaa479db1cd05443cb7defd7e44a02d))
* **writing:** compose books editions and nested chapters ([0c97dea](https://github.com/ramsesoriginal/lorenzo/commit/0c97dea8c1e2a8f2f387ed125c29a116b3796537))
* **writing:** extract outline elements into nested chapters ([f81efc0](https://github.com/ramsesoriginal/lorenzo/commit/f81efc0e89f3c50280f1b0188dc2ff0e381ffa47))
* **writing:** move manuscript entries atomically between outlines ([8f5c912](https://github.com/ramsesoriginal/lorenzo/commit/8f5c912384907b6baa5f7c6a95cc5143a30e7a02))
* **writing:** reuse scenes through independent tellings ([2a0c4cd](https://github.com/ramsesoriginal/lorenzo/commit/2a0c4cd88e5ff0ad86d45327b2df7cf6378b942a))
* **writing:** split saved prose at safe paragraph boundaries ([242de21](https://github.com/ramsesoriginal/lorenzo/commit/242de2175415b43fecd5fc61df8a1fc71632e7cb))


### Bug Fixes

* **api:** delete a tenant that holds Sessions ([080a07a](https://github.com/ramsesoriginal/lorenzo/commit/080a07a06cf6fc4b598a1a4fb097befc8401b85c))
* **api:** name the frame membership response so it keeps MembershipOut free ([0ccabdd](https://github.com/ramsesoriginal/lorenzo/commit/0ccabdd03ebc3184be4d00bf814adc95c8e30268))
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>converters: 0.1.0</summary>

## 0.1.0 (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Documentation

* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* **packages:** document the calendar document module and the Python package commands ([b93e911](https://github.com/ramsesoriginal/lorenzo/commit/b93e911a8d2f48668dbe2ffd8e786265a523570c))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>inventory-names: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>brand-package: 1.2.0</summary>

## [1.2.0](https://github.com/ramsesoriginal/lorenzo/compare/brand-package-v1.1.0...brand-package-v1.2.0) (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzoscript: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzoscript-editor: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>beings: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **beings:** show ordered participating Event titles ([17c8074](https://github.com/ramsesoriginal/lorenzo/commit/17c8074e6a7b7b82e585bc8734556cec297552b4))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **sessions:** record independent lived-before participation evidence ([2320e75](https://github.com/ramsesoriginal/lorenzo/commit/2320e750381e20d606b78b6845344342329fc039))
* **sessions:** record independent lived-before participation evidence ([07f694b](https://github.com/ramsesoriginal/lorenzo/commit/07f694b285a294ddc1c30e1b9d237a59777626f5))
* **sessions:** record personal lived order with participation provenance ([8ee5328](https://github.com/ramsesoriginal/lorenzo/commit/8ee532892c2ba3add48501a49c5463d2700e2588))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>stat-values: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>inventory-mobile: 0.2.0</summary>

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-mobile-v0.1.0...inventory-mobile-v0.2.0) (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>information-editor: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
* **calendars:** create groups from all Event participants ([1764cb8](https://github.com/ramsesoriginal/lorenzo/commit/1764cb8bc9483b0700c30c8f61fc733313f4d4de))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>app-shell: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>period-picker: 1.0.0</summary>

## 1.0.0 (2026-10-29)


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

## 1.0.0 (2026-10-29)


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

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/inventory-ios-v0.1.0...inventory-ios-v0.2.0) (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzo-calendar: 0.1.0</summary>

## 0.1.0 (2026-10-29)


### Features

* **calendar-engine:** the periods that contain a date ([8c0fa7b](https://github.com/ramsesoriginal/lorenzo/commit/8c0fa7ba3d3da567a60454ffae49f8d6e3da1319))
* **calendars:** link named entries and computed calendar dates ([5c54815](https://github.com/ramsesoriginal/lorenzo/commit/5c54815dae8035191985a96dadcfb1a83c08a047))
* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Documentation

* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* **packages:** document the calendar document module and the Python package commands ([b93e911](https://github.com/ramsesoriginal/lorenzo/commit/b93e911a8d2f48668dbe2ffd8e786265a523570c))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>calendars: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([d96ad6c](https://github.com/ramsesoriginal/lorenzo/commit/d96ad6c87d22a4caff6223139f98d6e20b07e772))
* **app-shell:** one header, skip link and page frame for Calendars and Sessions ([9502064](https://github.com/ramsesoriginal/lorenzo/commit/95020642ab902847acff17bbd0002f2aa9d9ec49))
* **calendars:** add a whole-year view with shared month rendering ([80f9672](https://github.com/ramsesoriginal/lorenzo/commit/80f9672f91ac2365a3430b54e21e95e54aa352c2))
* **calendars:** add a whole-year view with shared month rendering ([499bb79](https://github.com/ramsesoriginal/lorenzo/commit/499bb7973e4c73a23429377c33cb7cb6612749a1))
* **calendars:** add live Event participant audiences ([1046bd9](https://github.com/ramsesoriginal/lorenzo/commit/1046bd95892d8aa31d40522877740feb7d3267f4))
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
* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Performance Improvements

* **calendars:** cache scoped reads and prefetch likely navigation ([dc2663c](https://github.com/ramsesoriginal/lorenzo/commit/dc2663c8366933e8a2b805a4fc76248cb1b59022))
* **calendars:** read a calendar and its entry together ([d48a57c](https://github.com/ramsesoriginal/lorenzo/commit/d48a57c4479f604d34cfa9d08b184a9833011b98))
* **calendars:** read a calendar and its entry together ([8b7f293](https://github.com/ramsesoriginal/lorenzo/commit/8b7f293d519857ec146b0b07c37104da980ef820))
</details>

<details><summary>sessions: 1.0.0</summary>

## 1.0.0 (2026-10-29)


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

<details><summary>writing: 1.0.0</summary>

## 1.0.0 (2026-10-29)


###   BREAKING CHANGES

* **writing:** entity kind responses add scene_telling and Writing entry responses add scene, scene_telling and biography. Generated clients and exact accepted OpenAPI findings are updated together.

### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))
* **writing:** add edition-scoped review access and private notes ([472ea2d](https://github.com/ramsesoriginal/lorenzo/commit/472ea2d767dd027da8b30ac17e698bd29a511b4c))
* **writing:** add standalone manuscripts with autosave and recovery ([37fae07](https://github.com/ramsesoriginal/lorenzo/commit/37fae0704eaa479db1cd05443cb7defd7e44a02d))
* **writing:** compose books editions and nested chapters ([0c97dea](https://github.com/ramsesoriginal/lorenzo/commit/0c97dea8c1e2a8f2f387ed125c29a116b3796537))
* **writing:** extract outline elements into nested chapters ([f81efc0](https://github.com/ramsesoriginal/lorenzo/commit/f81efc0e89f3c50280f1b0188dc2ff0e381ffa47))
* **writing:** move manuscript entries atomically between outlines ([8f5c912](https://github.com/ramsesoriginal/lorenzo/commit/8f5c912384907b6baa5f7c6a95cc5143a30e7a02))
* **writing:** reuse scenes through independent tellings ([2a0c4cd](https://github.com/ramsesoriginal/lorenzo/commit/2a0c4cd88e5ff0ad86d45327b2df7cf6378b942a))
* **writing:** split manuscripts between complete syntax blocks ([c6c613a](https://github.com/ramsesoriginal/lorenzo/commit/c6c613a43b56da8e8b00e75fed166b27742d5266))
* **writing:** split saved prose at safe paragraph boundaries ([242de21](https://github.com/ramsesoriginal/lorenzo/commit/242de2175415b43fecd5fc61df8a1fc71632e7cb))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>maps: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* **maps:** a Distance section and how a grid counts diagonals ([63ae9ff](https://github.com/ramsesoriginal/lorenzo/commit/63ae9ff814af58ee367cb2823fc6346a4fd1997c))
* **maps:** a read-only view of a Map in Lorenzo Maps (ADR 0340) ([6ec9346](https://github.com/ramsesoriginal/lorenzo/commit/6ec934689b2a76cf00bb0db2fc6c680f454e0945))
* **maps:** author a Map: tools, settings, the look and the legend (ADR 0353) ([dcbb6af](https://github.com/ramsesoriginal/lorenzo/commit/dcbb6af855caf8cef7cbcfe44a1138e94e337ae0))
* **maps:** author and look at a sphere (ADR 0359) ([aeb19a0](https://github.com/ramsesoriginal/lorenzo/commit/aeb19a00da9d7405ea96c62eb10a09803ae83de2))
* **maps:** author on a grid (ADR 0356) ([81df5d6](https://github.com/ramsesoriginal/lorenzo/commit/81df5d696b592f4ec7639c3798ac9ac356d06321))
* **maps:** connections on the Location page and a Map's Leads to (ADR 0365) ([34a5337](https://github.com/ramsesoriginal/lorenzo/commit/34a53377f49bc027acb40f7e8712e78d3a63f4d3))
* **maps:** look at the Locations list through a date ([f22c287](https://github.com/ramsesoriginal/lorenzo/commit/f22c287c12ef7d782424b363e7052cf73ad0b7fd))
* **maps:** look at the Maps list through a date ([42eff2e](https://github.com/ramsesoriginal/lorenzo/commit/42eff2e5d84531556ad7cba2a078b5fa5f23b45d))
* **maps:** Lorenzo Maps, a static app for the Locations of a library (ADR 0332) ([b59daed](https://github.com/ramsesoriginal/lorenzo/commit/b59daed93b195f8828d422d34f36c5a6b77734f4))
* **maps:** pictures under a Map (ADR 0362) ([5b795fc](https://github.com/ramsesoriginal/lorenzo/commit/5b795fc0feb4590803b4decf38636de822fbee3e))
* **maps:** the entry card on a mark and a row of the places list (ADR 0350) ([5e8099a](https://github.com/ramsesoriginal/lorenzo/commit/5e8099a5448a79f0fa71c25881554df710d5697d))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>lorenzo-map: 0.1.0</summary>

## 0.1.0 (2026-10-29)


### Features

* **api:** a stored picture fingerprint, SVG pictures and a Map's layers (ADR 0360, 0361) ([5c8f9ac](https://github.com/ramsesoriginal/lorenzo/commit/5c8f9ac649559a14f31a5f4fc367fbcbf3c75bf0))
* **api:** atomic batch placement writes and a Map's theme name (ADR 0351, 0352) ([8853de4](https://github.com/ramsesoriginal/lorenzo/commit/8853de4d5eb8e14b01e0762414cfbec591c0ec6e))
* **api:** grid systems, a Map's view and the hex rule (ADR 0354) ([1a6b866](https://github.com/ramsesoriginal/lorenzo/commit/1a6b8662538e2476991e0a0fbc223ec1ef8b8ba8))
* **api:** the sphere system, a projection in a Map's view and format 21 (ADR 0357) ([6918f9e](https://github.com/ramsesoriginal/lorenzo/commit/6918f9e35884908fa50d572fff547ea50927f1a1))
* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* **map-engine:** straight-line distance and a metric for square and rect grids ([c19f92f](https://github.com/ramsesoriginal/lorenzo/commit/c19f92fe2c8e5c9393480638eb46b81f390bc125))
* **map-engine:** the validator of Map systems and placement geometry (ADR 0336, 0337) ([0d175ff](https://github.com/ramsesoriginal/lorenzo/commit/0d175ffb204c8dcb4932cd3c0c3f80074234253f))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))


### Documentation

* distance in the world model, overview, setup and READMEs ([3854d4d](https://github.com/ramsesoriginal/lorenzo/commit/3854d4dd7ba263ccca2c597f6f25b3a276028fd7))
* **domain:** explain collaborative audiences and all-being groups ([2f8c17f](https://github.com/ramsesoriginal/lorenzo/commit/2f8c17f62199517719d9f6579c28496e27ef24d3))
* **packages:** document the calendar document module and the Python package commands ([b93e911](https://github.com/ramsesoriginal/lorenzo/commit/b93e911a8d2f48668dbe2ffd8e786265a523570c))
* specify scoped Session sequence and play disclosure ([b62fac7](https://github.com/ramsesoriginal/lorenzo/commit/b62fac795209311b37af6066be956cfabbd57f95))
</details>

<details><summary>map-renderer: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* **map-renderer:** draw a grid and mirror the cell functions (ADR 0355) ([a942d96](https://github.com/ramsesoriginal/lorenzo/commit/a942d96afc915963364ceeea21e57ed8de3ecc7f))
* **map-renderer:** draw the pictures under a Map (ADR 0362) ([2ab5dee](https://github.com/ramsesoriginal/lorenzo/commit/2ab5dee846a469308c926d370268aad0dc1045b2))
* **map-renderer:** project a sphere flat, as Mercator or as a globe (ADR 0358) ([1dc63ab](https://github.com/ramsesoriginal/lorenzo/commit/1dc63ab3386ea4244f9a880041c1a76697a350f4))
* **map-renderer:** the hand-written SVG drawing of a Map (ADR 0339) ([842fd2b](https://github.com/ramsesoriginal/lorenzo/commit/842fd2bf718db95c84df83c12c81ad3f87699d09))
* **map-renderer:** the plain theme, a legend and an editor interface (ADR 0352, 0353) ([5282e5a](https://github.com/ramsesoriginal/lorenzo/commit/5282e5ab0c282e904643ebac5f4f54dabf15e230))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

<details><summary>entry-preview: 1.0.0</summary>

## 1.0.0 (2026-10-29)


### Features

* Locations, Maps, connections, frames and optional dates (RFC 0048) ([5999e61](https://github.com/ramsesoriginal/lorenzo/commit/5999e61878ff62c68e75444ed24b0e8d8763275e))
* optional time on Locations, the date lens (RFC 0048 slice 14) ([a06397a](https://github.com/ramsesoriginal/lorenzo/commit/a06397a4932f1b4d0cfbc0a1aeae6126a1ac7e7d))
* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))
</details>

---
This PR was generated with [Release Please](https://github.com/googleapis/release-please). See [documentation](https://github.com/googleapis/release-please#release-please).
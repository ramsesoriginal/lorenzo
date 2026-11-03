# Changelog

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

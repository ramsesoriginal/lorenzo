# Changelog

## [2.0.0](https://github.com/ramsesoriginal/lorenzo/compare/api-client-v1.0.0...api-client-v2.0.0) (2026-11-07)


### ⚠ BREAKING CHANGES

* **api:** the `kinds` enum of entries gains `social_web`; accepted in openapi-breaking-accepted.txt (ADR 0406).
* **api:** the `kinds` enum of entries gains `relationship`; accepted in openapi-breaking-accepted.txt (ADR 0399).

### Features

* **api:** an Owner can deprecate a repository, so it keeps its updates and blocks new copies ([30a4465](https://github.com/ramsesoriginal/lorenzo/commit/30a446584bedaa674fdb58741765d0476f79cc24))
* **api:** an Owner can retire a repository (ADR 0384) ([ce5e5a9](https://github.com/ramsesoriginal/lorenzo/commit/ce5e5a987e3505006ad8818ab64aa269e9eea65a))
* **api:** bulk write of relationships and standings, and the type stats (ADR 0400) ([545ceac](https://github.com/ramsesoriginal/lorenzo/commit/545ceac1e73e2bef84d2d588c2373ed2b5b82d74))
* **api:** count the libraries that hold what is about to be deleted ([d1cd608](https://github.com/ramsesoriginal/lorenzo/commit/d1cd6083f11e91cf2ef0ccfe7348099287c21d89))
* **api:** Lorenzo Social in the registry of app links ([38ed868](https://github.com/ramsesoriginal/lorenzo/commit/38ed8689c61a5fffe1fe695c7be537f8ebfea16c))
* **api:** Lorenzo Social in the registry of app links ([7e28c77](https://github.com/ramsesoriginal/lorenzo/commit/7e28c7731e3a65a8a44056ed24f0e39b156eb291))
* **api:** optional minimum and maximum on a numeric stat (ADR 0403) ([2c293a5](https://github.com/ramsesoriginal/lorenzo/commit/2c293a5f6764f6896d61270fa8d664d453ea2427))
* **api:** optional time on a relationship and reading it as of an Event (ADR 0405) ([45952a6](https://github.com/ramsesoriginal/lorenzo/commit/45952a6c596aa9b64ad3a79d01606b107d15a48d))
* **api:** read the effective value of some stats on a page of entries ([85ed246](https://github.com/ramsesoriginal/lorenzo/commit/85ed246cbb47a1de8e71eb22356f7653e1f8640d))
* **api:** relationship through, an authored ordered chain (ADR 0402) ([f3503ea](https://github.com/ramsesoriginal/lorenzo/commit/f3503ea7130fba8367ad5055ffbcdf782b4d0392))
* **api:** relationships, the second kind joining two entries (ADR 0399) ([5594086](https://github.com/ramsesoriginal/lorenzo/commit/55940860f9f823e77aabbde042f8e699e8108c89))
* **api:** rename a stat definition and an enum value ([8262f84](https://github.com/ramsesoriginal/lorenzo/commit/8262f84f883c0d94249cef18efd599728526d482))
* **api:** the SocialWeb kind, a saved view of relationships (ADR 0406) ([c7b253d](https://github.com/ramsesoriginal/lorenzo/commit/c7b253de438f623b0ea8e5296cc1b001a4097951))
* **social:** players write their own relationships (ADR 0409) ([96b83a3](https://github.com/ramsesoriginal/lorenzo/commit/96b83a38e85a48ec01a04e366aaa7d06f4d59e2a))
* **social:** the date lens and "as read by" in the app (ADR 0405) ([73d27d9](https://github.com/ramsesoriginal/lorenzo/commit/73d27d9c4855c876893bdee6a8a96ea8054f5ce1))
* **social:** the Lorenzo Social app scaffold, relationship list and page (ADR 0408) ([cc6aa2b](https://github.com/ramsesoriginal/lorenzo/commit/cc6aa2b93687ad3598813d501a897af26a8bad33))
* **social:** the types and standings screen and the starter vocabulary (ADR 0400) ([f35ac64](https://github.com/ramsesoriginal/lorenzo/commit/f35ac6425ef1ead1fcc1cba3af4bea4deb808df0))
* **social:** the web screens and the graph view with stress and ForceAtlas2 (ADR 0407, ADR 0408) ([f6733ad](https://github.com/ramsesoriginal/lorenzo/commit/f6733ad86a4f9c37e78123b1776b3de7c20e5422))
* **writing:** add personal manuscript length targets ([a9317b6](https://github.com/ramsesoriginal/lorenzo/commit/a9317b646d1ef8c8ec03b13ec6e518633df5d3b7))
* **writing:** count manuscript words and selected passages ([23e4de7](https://github.com/ramsesoriginal/lorenzo/commit/23e4de74970d7c2c4d3b314ba6aa2a617c688d3c))
* **writing:** personal manuscript-length targets ([e55d62f](https://github.com/ramsesoriginal/lorenzo/commit/e55d62f569f16c8dcd410bb4fbfd9e22825a56b7))

## 1.0.0 (2026-10-29)


### ⚠ BREAKING CHANGES

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

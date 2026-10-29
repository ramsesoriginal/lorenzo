# Changelog

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.7.0...api-v1.0.0) (2026-10-29)


### ⚠ BREAKING CHANGES

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

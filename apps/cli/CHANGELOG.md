# Changelog

## [1.0.0](https://github.com/ramsesoriginal/lorenzo/compare/cli-v0.1.0...cli-v1.0.0) (2026-11-13)


### ⚠ BREAKING CHANGES

* **api:** the `kinds` enum of entries gains `social_web`; accepted in openapi-breaking-accepted.txt (ADR 0406).
* **api:** the `kinds` enum of entries gains `relationship`; accepted in openapi-breaking-accepted.txt (ADR 0399).

### Features

* **api:** a campaign names a game system, and the sheet reads a template (RFC 0052 Y5) ([d70b1db](https://github.com/ramsesoriginal/lorenzo/commit/d70b1db259d1af82e0fd0ebeaddf33e36267194c))
* **api:** a game system as a row, and the prefix rule (RFC 0052 Y1) ([2936ef3](https://github.com/ramsesoriginal/lorenzo/commit/2936ef324381c9890d8449cad2dc3a995e3de07d))
* **api:** a hidden entry gives its texts to the entries below it, and consent is asked once ([b7c6535](https://github.com/ramsesoriginal/lorenzo/commit/b7c6535f8c2128b9a9886878e60e4fa6bcc5ede4))
* **api:** a write of a stat or of a formula can answer with warnings (RFC 0055 V4) ([9842c53](https://github.com/ramsesoriginal/lorenzo/commit/9842c536053980b0341c70bc571c076176166dcc))
* **api:** a write of a stat or of a formula can answer with warnings (RFC 0055 V4) ([a4a8904](https://github.com/ramsesoriginal/lorenzo/commit/a4a89041f6597df42acf14a645204ef2355c24dd))
* **api:** bulk write of relationships and standings, and the type stats (ADR 0400) ([545ceac](https://github.com/ramsesoriginal/lorenzo/commit/545ceac1e73e2bef84d2d588c2373ed2b5b82d74))
* **api:** features, two kinds and what a holder has (RFC 0054 F1) ([93ffa5a](https://github.com/ramsesoriginal/lorenzo/commit/93ffa5a5cdfb1e09455d81763f5e41ce8af29d98))
* **api:** formula kind select (RFC 0053 K3) ([074b0c0](https://github.com/ramsesoriginal/lorenzo/commit/074b0c039042c207024e8cf19f8d7b0ee191c536))
* **api:** formula kinds min and max, and a bool or an enum as a number (RFC 0053 K1) ([5fe61ca](https://github.com/ramsesoriginal/lorenzo/commit/5fe61cada0b5bcb7a1f761490342c147e528a82b))
* **api:** formula kinds product and ratio (RFC 0053 K2) ([9c09f9c](https://github.com/ramsesoriginal/lorenzo/commit/9c09f9c248af0bcbb51d8bdc5d2b4b84a5b42529))
* **api:** grant records, the grants read, apply with picks and revocation (RFC 0054 F3) ([e9fa7a9](https://github.com/ramsesoriginal/lorenzo/commit/e9fa7a9eb242b7074fffdf1b74d91e0b644a6b4a))
* **api:** grant rules and the prerequisites of a feature (RFC 0054 F2) ([9ca688e](https://github.com/ramsesoriginal/lorenzo/commit/9ca688e5ea315bc3642cfa612349ed964bc20155))
* **api:** hide a source's entries (RFC 0051 H4) ([03c33b3](https://github.com/ramsesoriginal/lorenzo/commit/03c33b3a9456e39d3287968661eb32a2cead1275))
* **api:** include a repository in the release of one built on it ([ca321d1](https://github.com/ramsesoriginal/lorenzo/commit/ca321d1264ece2df99c7d315d5eeb19c48f68f6e))
* **api:** leave a public repository off Discover ([38a17a3](https://github.com/ramsesoriginal/lorenzo/commit/38a17a365afbd933f454c4dff2936642de201410))
* **api:** Lorenzo Social in the registry of app links ([38ed868](https://github.com/ramsesoriginal/lorenzo/commit/38ed8689c61a5fffe1fe695c7be537f8ebfea16c))
* **api:** Lorenzo Social in the registry of app links ([7e28c77](https://github.com/ramsesoriginal/lorenzo/commit/7e28c7731e3a65a8a44056ed24f0e39b156eb291))
* **api:** optional minimum and maximum on a numeric stat (ADR 0403) ([2c293a5](https://github.com/ramsesoriginal/lorenzo/commit/2c293a5f6764f6896d61270fa8d664d453ea2427))
* **api:** optional time on a relationship and reading it as of an Event (ADR 0405) ([45952a6](https://github.com/ramsesoriginal/lorenzo/commit/45952a6c596aa9b64ad3a79d01606b107d15a48d))
* **api:** protected repositories ([b056c03](https://github.com/ramsesoriginal/lorenzo/commit/b056c03a45a07c9a05a5bf82b4c0135ec3b0d3ba))
* **api:** relationship through, an authored ordered chain (ADR 0402) ([f3503ea](https://github.com/ramsesoriginal/lorenzo/commit/f3503ea7130fba8367ad5055ffbcdf782b4d0392))
* **api:** relationships, the second kind joining two entries (ADR 0399) ([5594086](https://github.com/ramsesoriginal/lorenzo/commit/55940860f9f823e77aabbde042f8e699e8108c89))
* **api:** repositories carry game systems and templates (RFC 0052 Y6) ([3cd9b45](https://github.com/ramsesoriginal/lorenzo/commit/3cd9b456485d55215a14dca805a9fe5b2df41c32))
* **api:** repositories carry game systems and templates (RFC 0052 Y6) ([3a2465e](https://github.com/ramsesoriginal/lorenzo/commit/3a2465e6d2fe216682f5e5ecb9fde079c521d652))
* **api:** roles - the API reads a stat by what it is for (RFC 0052 Y2) ([d2bfe98](https://github.com/ramsesoriginal/lorenzo/commit/d2bfe98b9b05c7d4bd491d0a750f17d886c8d94c))
* **api:** templates - what a sheet shows, as data (RFC 0052 Y4) ([b63212a](https://github.com/ramsesoriginal/lorenzo/commit/b63212adc825bff6579f7c5d8c8511ffca0a7bc9))
* **api:** the features slot of a template (RFC 0054 F4) ([92febd1](https://github.com/ramsesoriginal/lorenzo/commit/92febd104295f8527e5d12a120efeeb1888303d8))
* **api:** the features slot of a template (RFC 0054 F4) ([1502101](https://github.com/ramsesoriginal/lorenzo/commit/1502101575798de0af8f0f8584302f9dd6baae6b))
* **api:** the legal app and support link in the registry, and a one-time avatar copy ([a52bff0](https://github.com/ramsesoriginal/lorenzo/commit/a52bff0f54a689f601623dc586bc562f8fd91b71))
* **api:** the options of a contents formula and the active switch (RFC 0053 K4) ([38812ba](https://github.com/ramsesoriginal/lorenzo/commit/38812bae3baa0678814135e303026f08a7215ee4))
* **api:** the options of a contents formula and the active switch (RFC 0053 K4) ([ea34047](https://github.com/ramsesoriginal/lorenzo/commit/ea340474a0703c666f07f852831ad181a6f73fe2))
* **api:** the SocialWeb kind, a saved view of relationships (ADR 0406) ([c7b253d](https://github.com/ramsesoriginal/lorenzo/commit/c7b253de438f623b0ea8e5296cc1b001a4097951))
* **api:** the vocabulary check says a tie, for one entry (RFC 0055 V3) ([9b3962c](https://github.com/ramsesoriginal/lorenzo/commit/9b3962c531053f5e788df7287d5a61ac40f1f178))
* **api:** the vocabulary check says an unset input and an own value that shadows a formula (RFC 0055 V2) ([44970cd](https://github.com/ramsesoriginal/lorenzo/commit/44970cd4fab8fc544b887e9ddd7e00cd98864567))
* **api:** the vocabulary check, its route and its first findings (RFC 0055 V1) ([2115406](https://github.com/ramsesoriginal/lorenzo/commit/2115406c1f74c4a86fccbaad644bcb1b0d0f3a43))
* **calendars:** the empty calendar list uses the shared mascot state ([54f6ac6](https://github.com/ramsesoriginal/lorenzo/commit/54f6ac6aa9c9f45b35278ff2f214820205291dac))
* **loot-bot,cli:** link the legal pages ([85448dc](https://github.com/ramsesoriginal/lorenzo/commit/85448dc586edf2e9e2947f6b85e1f515a6682440))
* **social:** players write their own relationships (ADR 0409) ([96b83a3](https://github.com/ramsesoriginal/lorenzo/commit/96b83a38e85a48ec01a04e366aaa7d06f4d59e2a))
* **social:** the Lorenzo Social app scaffold, relationship list and page (ADR 0408) ([cc6aa2b](https://github.com/ramsesoriginal/lorenzo/commit/cc6aa2b93687ad3598813d501a897af26a8bad33))
* **social:** the types and standings screen and the starter vocabulary (ADR 0400) ([f35ac64](https://github.com/ramsesoriginal/lorenzo/commit/f35ac6425ef1ead1fcc1cba3af4bea4deb808df0))
* **social:** the web screens and the graph view with stress and ForceAtlas2 (ADR 0407, ADR 0408) ([f6733ad](https://github.com/ramsesoriginal/lorenzo/commit/f6733ad86a4f9c37e78123b1776b3de7c20e5422))
* **writing:** personal manuscript-length targets ([e55d62f](https://github.com/ramsesoriginal/lorenzo/commit/e55d62f569f16c8dcd410bb4fbfd9e22825a56b7))


### Bug Fixes

* **api:** accept the added hide value, ask the tenant and the gate in one statement ([a876d5a](https://github.com/ramsesoriginal/lorenzo/commit/a876d5a13e7dc7b3e0972f7681811ebe1946abaa))
* **api:** accept the added visibility value, keep the release statement bound at a fixed number ([3a79dac](https://github.com/ramsesoriginal/lorenzo/commit/3a79dac87bdfe58ec7b0c8b11155dc041dd907b2))
* **api:** answer what the API used to ignore, crash on or return out of order ([62d1cd4](https://github.com/ramsesoriginal/lorenzo/commit/62d1cd48c685003e5996ae7c43697830a5ea50f4))
* **api:** answer what the API used to ignore, crash on or return out of order ([2311c97](https://github.com/ramsesoriginal/lorenzo/commit/2311c97c9b7d4b2eb5e59d00c987846192c42c24))
* **inventory-web,cli:** read a text from a hidden entry as inherited, never as the entry's own ([ac9d751](https://github.com/ramsesoriginal/lorenzo/commit/ac9d751923e22334199f98a7e4acd5e78a2ac3a8))
* K1 follow-ups the checks found ([a66d81f](https://github.com/ramsesoriginal/lorenzo/commit/a66d81f4b597820d935aba8c3244e28be5f9c48b))
* the clients that build an item or an instance know the new fields ([d2b9008](https://github.com/ramsesoriginal/lorenzo/commit/d2b9008bf51e0dd67b55fc8ee395519649e875c8))


### Documentation

* the legal pages in the guides, v1.0 and the README; a third-party resource test ([38301d6](https://github.com/ramsesoriginal/lorenzo/commit/38301d6c56d0e21622d32ff1536848311d0142e8))

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

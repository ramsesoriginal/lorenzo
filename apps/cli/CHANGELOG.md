# Changelog

## 0.1.0 (2026-10-14)


### ⚠ BREAKING CHANGES

* **api:** campaign_name and role of GET /invites/{token}, campaign_id and role of a redemption and of a campaign's invite list and creation can now be null; accepted in openapi-breaking-accepted.txt.
* **api:** the role in GET /tenants and GET /me/managed can now be 'author'; accepted in openapi-breaking-accepted.txt.

### Features

* **account-hub,cli:** a public repository needs no invitation in the copy verdict ([00b3414](https://github.com/ramsesoriginal/lorenzo/commit/00b3414d8d076bdacb2c18aa111f403cbed633a1))
* **account-hub:** People with Authors and a panel for invite links (ADR 0212) ([945570b](https://github.com/ramsesoriginal/lorenzo/commit/945570b30ea5c58d9cdfcf036c72c8e5007542a3))
* **api-client:** getAppLinks and fill; regenerate schema and CLI models ([09ed822](https://github.com/ramsesoriginal/lorenzo/commit/09ed822c71a37dae995b1682c017c6b3036cd919))
* **api,cli:** display fields in repository copy, updates and seed ([d7c00a1](https://github.com/ramsesoriginal/lorenzo/commit/d7c00a182e5952ea8700871678a78e5aa8627cbf))
* **api:** a parent added to a copy is a warning, not a breaking change ([81a65bd](https://github.com/ramsesoriginal/lorenzo/commit/81a65bdb855aa5a2ff4c76bafc358c23e1eda032))
* **api:** a release holds a digest, and a publish says what it breaks ([cc8f901](https://github.com/ramsesoriginal/lorenzo/commit/cc8f901a0795e20eb03846eeca476a237d5704e2))
* **api:** bulk entity export with cursor pages, gzip and a per-tenant revision ETag ([3065130](https://github.com/ramsesoriginal/lorenzo/commit/3065130b6f90066510be1b6a3154d8927e40f397))
* **api:** creates take an id the client made, and a second send is a replay ([1a03c6d](https://github.com/ramsesoriginal/lorenzo/commit/1a03c6d531c6597cb0a10d48c21f9b807c0908e4))
* **api:** creates take an id the client made, and a second send is a replay ([d21ad3f](https://github.com/ramsesoriginal/lorenzo/commit/d21ad3fe0ef3931bc5d0eb7cdd63b3bdf8144e66))
* **api:** entries with kinds (RFC 0041 K2) ([8a8a6d1](https://github.com/ramsesoriginal/lorenzo/commit/8a8a6d1f7f6560bf4969e6f30f1769b4f7ba6330))
* **api:** GET /entities filters by name, kind and parent, and says what each entry is ([5d494f1](https://github.com/ramsesoriginal/lorenzo/commit/5d494f15b7404306bacc74e809dd62a20ccda7ef)), closes [#551](https://github.com/ramsesoriginal/lorenzo/issues/551)
* **api:** GET /entities filters by name, kind and parent, and says what each entry is (RFC 0041 K5) ([275ea2e](https://github.com/ramsesoriginal/lorenzo/commit/275ea2e78a63b2fabf00686a7105c983191b8de6))
* **api:** information shows who wrote it ([8aa11d5](https://github.com/ramsesoriginal/lorenzo/commit/8aa11d55f9d009914c8b15233ceb82a59c326b0b))
* **api:** link preview endpoint with per-kind templates in a registry ([168ba0f](https://github.com/ramsesoriginal/lorenzo/commit/168ba0f1a3dfc79f9e916163d5e93d9ed47fa8bd))
* **api:** make an entry with kinds, change its kinds, and publish only proven combinations ([fa50b2c](https://github.com/ramsesoriginal/lorenzo/commit/fa50b2c4897330bf4f49f4547408ae96ad41734b)), closes [#553](https://github.com/ramsesoriginal/lorenzo/issues/553)
* **api:** one invite table with kinds, role links and library-access links ([9644de9](https://github.com/ramsesoriginal/lorenzo/commit/9644de932ffe61a7621d865ac28ddcaffad48d36)), closes [#546](https://github.com/ramsesoriginal/lorenzo/issues/546)
* **api:** parent ids in the entry list ([5691ed2](https://github.com/ramsesoriginal/lorenzo/commit/5691ed27c0070272347f7581fad9f22004cc3322))
* **api:** parent ids in the entry list ([6d57bcb](https://github.com/ramsesoriginal/lorenzo/commit/6d57bcb2786076facf38c0d158dae8c5f1286cd7))
* **api:** picture payload upload and delete, main picture, information order ([77ac511](https://github.com/ramsesoriginal/lorenzo/commit/77ac5111a1c30b2005381000edcf1c1ce0c7730f))
* **api:** picture upload and delete, main picture, information order (RFC 0041 K8) ([103227a](https://github.com/ramsesoriginal/lorenzo/commit/103227a4087b8c6eb46657fade4f5290f515197b))
* **api:** PUT /entities/{id}/parents sets the parents of any entry ([6710605](https://github.com/ramsesoriginal/lorenzo/commit/67106052fbef5d203575b0d42c11401016cb070c)), closes [#552](https://github.com/ramsesoriginal/lorenzo/issues/552)
* **api:** PUT /entities/{id}/parents sets the parents of any entry (RFC 0041 K3) ([a876c6a](https://github.com/ramsesoriginal/lorenzo/commit/a876c6a2c1afd51c54cad32585a02e5ea2770226))
* **api:** retention and making a release current (ADR 0288) ([d3750a8](https://github.com/ramsesoriginal/lorenzo/commit/d3750a86fdf196e88d80fc22ae884a6f51ae5016)), closes [#710](https://github.com/ramsesoriginal/lorenzo/issues/710)
* **api:** sheet settings and the being sheet read ([12a72c9](https://github.com/ramsesoriginal/lorenzo/commit/12a72c945a0be534eacb9deaf13113cd0f6971ac))
* **api:** stat definition display fields, order and PATCH ([e32ed57](https://github.com/ramsesoriginal/lorenzo/commit/e32ed570b62c4dd116c3060c43f3042b814575d1))
* **api:** stat hints ([bf2304c](https://github.com/ramsesoriginal/lorenzo/commit/bf2304cfdc481f5d84e959e38a2e42a8f7ac264d))
* **api:** stat writes that can be checked and undone ([f135b7c](https://github.com/ramsesoriginal/lorenzo/commit/f135b7c47ed235039c547e1a4d18dc6ad7110990))
* **api:** stat writes that can be checked and undone ([abc4ae7](https://github.com/ramsesoriginal/lorenzo/commit/abc4ae79d0e4a16e7244c99a18f2958a9be84b2a))
* **api:** the author role, an admin gate and a table-driven route audit ([f25f832](https://github.com/ramsesoriginal/lorenzo/commit/f25f83225ffe1ee4223996c0c556dfa27ae23542)), closes [#545](https://github.com/ramsesoriginal/lorenzo/issues/545)
* **api:** the device-code flow sends devices to the hub the app-links registry names ([abd9410](https://github.com/ramsesoriginal/lorenzo/commit/abd94102b1500fd8b58512df65ef994f44ab512d))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([956fbf0](https://github.com/ramsesoriginal/lorenzo/commit/956fbf0586997e18595924f6f5054c8af7ef63f6))
* **api:** the flip rules and the bridge-skew gate (ADR 0289) ([7f83b56](https://github.com/ramsesoriginal/lorenzo/commit/7f83b56f500155d9d862c2e34bc2a822ec11396d)), closes [#711](https://github.com/ramsesoriginal/lorenzo/issues/711)
* **api:** the flips as routes (ADR 0290) ([f576dbf](https://github.com/ramsesoriginal/lorenzo/commit/f576dbf6b4aac96ad98250c7ba9dba572c2be248))
* **api:** the flips as routes (ADR 0290) ([88a5248](https://github.com/ramsesoriginal/lorenzo/commit/88a524842773779c3ea8adc40568410bcb4d57b7)), closes [#718](https://github.com/ramsesoriginal/lorenzo/issues/718)
* **api:** the release digest and the breaking-change detector (ADR 0208) ([0742ebb](https://github.com/ramsesoriginal/lorenzo/commit/0742ebb5e0a8ed734d43dc782e808aa1f0502ed8))
* **api:** the release ledger, publishing makes a release (ADR 0207) ([d58f904](https://github.com/ramsesoriginal/lorenzo/commit/d58f904d5389b0628f90f1400dd2471b5478ee7f))
* **api:** the repository profile, its cover and the source of a grant ([88c42ed](https://github.com/ramsesoriginal/lorenzo/commit/88c42edcd297b57f09d85dce7fa745330adab735)), closes [#548](https://github.com/ramsesoriginal/lorenzo/issues/548)
* **api:** where a stat value comes from, and why ([4e1f892](https://github.com/ramsesoriginal/lorenzo/commit/4e1f89219bb1eca3bb91109e0a86c60e83432880))
* **api:** who may read a public repository (ADR 0287) ([574108a](https://github.com/ramsesoriginal/lorenzo/commit/574108acc8dcd75c1621cec57d7b26682bd42e38))
* **api:** who may read a public repository (ADR 0287) ([15869f2](https://github.com/ramsesoriginal/lorenzo/commit/15869f2a6d2fae77df6de21edd73e23d3afd6fc8)), closes [#702](https://github.com/ramsesoriginal/lorenzo/issues/702)
* **beings:** Lorenzo Beings, a new app for characters and NPCs (ADR 0270-0272) ([26f7b8f](https://github.com/ramsesoriginal/lorenzo/commit/26f7b8f63eef01898a6ff14dc7c58129aca5e71c))
* **bench:** the main picture - show, choose, replace, remove (B8) ([c19d639](https://github.com/ramsesoriginal/lorenzo/commit/c19d6391da96ed3c44fb6928b309dfd21fb58004))
* **cli:** --replace leaves alone what is tied up with someone else's ([3800dbc](https://github.com/ramsesoriginal/lorenzo/commit/3800dbca30cf872812c4fbcea34f28e4b5568b58))
* **cli:** import for any being, --replace, and a progress display ([26b99c0](https://github.com/ramsesoriginal/lorenzo/commit/26b99c008576c9a9da3230ee8131ca9aeb4e0d02))
* **cli:** import for any being, --replace, and a progress display ([a8dd836](https://github.com/ramsesoriginal/lorenzo/commit/a8dd8361f4200891aa3d810275ba4ade7558da08))
* **cli:** lorenzo login --token connects with a personal access token ([cb77ff2](https://github.com/ramsesoriginal/lorenzo/commit/cb77ff2ce7000571c2862057dff2c4b1aa28b399))
* **cli:** read and write the LorenzoLedger, with descriptions ([222f0ad](https://github.com/ramsesoriginal/lorenzo/commit/222f0adc41a7ddbe8062002b38d75f0f14b3f293))
* **cli:** read and write the LorenzoLedger, with descriptions ([0e00e96](https://github.com/ramsesoriginal/lorenzo/commit/0e00e96e1f10ea0e5e54eb5b92b712b205085946))
* **converters:** lorenzo-convert sheet, an Excel or CSV inventory as a ledger ([2fb5db7](https://github.com/ramsesoriginal/lorenzo/commit/2fb5db7652b94949cec8de76259ef83477784b09))
* **converters:** lorenzo-convert sheet, an Excel or CSV inventory as a ledger ([da9c1fc](https://github.com/ramsesoriginal/lorenzo/commit/da9c1fc18acd5b48ba8558f02ae7819afb12547d))
* **inventory-names:** share the importer's spelling table with the Unsorted view ([3e075a0](https://github.com/ramsesoriginal/lorenzo/commit/3e075a0e52f40d8de05c50489cb43c6a4e983234))
* **inventory-names:** share the importer's spelling table with the Unsorted view ([d6ffadd](https://github.com/ramsesoriginal/lorenzo/commit/d6ffadd8306302f4bdd8e7cc28e558492607306c))
* **inventory-web:** edit an item's stat values ([3ec929a](https://github.com/ramsesoriginal/lorenzo/commit/3ec929a96bd80fac962a40790d427638271868c4))


### Bug Fixes

* **cli:** stat-write ops return EntityStatWriteOut ([8a75644](https://github.com/ramsesoriginal/lorenzo/commit/8a756448e6a8efe719ddc7387ae247f5fc8fa09a))
* **converters:** keep the golden ledgers as .ledger, not Markdown ([84e0d77](https://github.com/ramsesoriginal/lorenzo/commit/84e0d77b7dd327f6f153194935352c5a60bb63ab))


### Performance Improvements

* **cli:** `seed` reads the items it finds from the listing, not one by one ([3d198d3](https://github.com/ramsesoriginal/lorenzo/commit/3d198d39cbc8dd499c8527eeaedbdffea2ed1f2b))
* **cli:** a faster end-to-end suite (copies, parallel workers) and a bulk read in seed ([81f4786](https://github.com/ramsesoriginal/lorenzo/commit/81f4786fc3ecb00e777b7f295070dd8029baa9bf))


### Documentation

* **adr:** ADR 0148 addendum, a profile of the end-to-end suites and what it led to ([f239127](https://github.com/ramsesoriginal/lorenzo/commit/f23912730e3aaf9ea97041f962b4324cb725b3f0))
* ADRs 0268 and 0269 for personal access tokens, and the places that list them ([4ba44fa](https://github.com/ramsesoriginal/lorenzo/commit/4ba44fa0cc68d080d3d8d10b9e80205a797115c6))
* point at lorenzo-beyond, now on PyPI ([ccc930a](https://github.com/ramsesoriginal/lorenzo/commit/ccc930a9a3c68fe16db7a9a20fd6eebce39f293e))
* point at lorenzo-beyond, now on PyPI ([f07ced6](https://github.com/ramsesoriginal/lorenzo/commit/f07ced6bbd5da9a2af2670e463e2977ef2cb73c0))
* the being sheet as built ([782ac03](https://github.com/ramsesoriginal/lorenzo/commit/782ac0332cba4b2b92d315ede0b82951804558db))

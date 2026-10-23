# Changelog

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

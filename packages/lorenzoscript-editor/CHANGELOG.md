# Changelog

## [1.1.0](https://github.com/ramsesoriginal/lorenzo/compare/lorenzoscript-editor-v1.0.0...lorenzoscript-editor-v1.1.0) (2026-11-20)


### Features

* **api:** undo a Scene extraction (ADR 0517) ([1e772cd](https://github.com/ramsesoriginal/lorenzo/commit/1e772cd85572fd81451909002e8da9b2a7d38c65))
* **lorenzoscript-editor:** [[ name completion (B3) ([8ea7090](https://github.com/ramsesoriginal/lorenzo/commit/8ea7090289626a26abc3e5c108d6f74cf4fca603))
* **lorenzoscript-editor:** paste from Word and find and replace ([766d8fc](https://github.com/ramsesoriginal/lorenzo/commit/766d8fc82630139687fc5633d14d0d69c0a7f179))
* **lorenzoscript-editor:** quiet highlighting of the markers (B4) ([a0b24df](https://github.com/ramsesoriginal/lorenzo/commit/a0b24dfd003fbd888f36987ed619b807bb6addcf))
* **lorenzoscript:** block ranges, and the editor's keys as a pure function ([564b02b](https://github.com/ramsesoriginal/lorenzo/commit/564b02b1926ffb06dc03485771e1547f19468b53))


### Bug Fixes

* **lorenzoscript-editor:** read pasted HTML with a small linear reader, not the DOM ([1da7a1a](https://github.com/ramsesoriginal/lorenzo/commit/1da7a1ac08745ec29babb5bc84295439087aa0b1))
* **lorenzoscript-editor:** reduce pasted HTML to a safe set before parsing it ([ad4f576](https://github.com/ramsesoriginal/lorenzo/commit/ad4f5768dae5fe3f44814b30005d7a546fb1720a))
* **lorenzoscript-editor:** the highlighter scans by hand, with no backtracking patterns ([f6f6844](https://github.com/ramsesoriginal/lorenzo/commit/f6f6844d46de021b8932f578b33f82a9eb35c4b9))

## 1.0.0 (2026-10-29)


### Features

* **sessions:** connect reusable Scenes and Session world references ([0969e58](https://github.com/ramsesoriginal/lorenzo/commit/0969e5858bb7e6264e57b5d37667c024cfc55b63))


### Bug Fixes

* **sessions:** preserve drafts while reviewing concurrent edits ([2430b39](https://github.com/ramsesoriginal/lorenzo/commit/2430b394c279ca9d05087c53f527c1674f990173))

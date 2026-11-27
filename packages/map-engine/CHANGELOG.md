# Changelog

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/lorenzo-map-v0.1.0...lorenzo-map-v0.2.0) (2026-11-27)


### Features

* **maps,map-engine:** cells are written as merged outlines, and a drawing may be larger ([d8c8774](https://github.com/ramsesoriginal/lorenzo/commit/d8c877491dab58dccd20aa9851814b230f2af89c))
* **maps,map-renderer:** the Height brush raises and lowers the land of an entry's height lines ([c95715e](https://github.com/ramsesoriginal/lorenzo/commit/c95715e38abc20dfa1443366b677c660c602dad6))
* **maps:** the Height brush draws its lines as smooth curves (ADR 0491) ([a2531e2](https://github.com/ramsesoriginal/lorenzo/commit/a2531e207d793e304503eb6a1619d5a89ce06ca5))


### Bug Fixes

* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([4f9f113](https://github.com/ramsesoriginal/lorenzo/commit/4f9f113f41773c5ea37e25f60e044c79e82febaf))
* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([c999469](https://github.com/ramsesoriginal/lorenzo/commit/c99946948d328af2fd5d9de32373ad2abd61d03a)), closes [#1255](https://github.com/ramsesoriginal/lorenzo/issues/1255)


### Documentation

* cite ADR 0479 in the collapse golden file ([eadb261](https://github.com/ramsesoriginal/lorenzo/commit/eadb261bd3905e35b6fca9d845ba0aa74faabbc9))
* **map-engine:** its exports, golden files and how it is run ([7ac80cc](https://github.com/ramsesoriginal/lorenzo/commit/7ac80ccfa08f600bc9bc94f03b17b7cfe663bcdc))
* stale ADR numbers and comments in code ([764e439](https://github.com/ramsesoriginal/lorenzo/commit/764e439f1492a07a2a8078942b4f5172acd4db33))

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

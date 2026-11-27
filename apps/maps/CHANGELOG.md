# Changelog

## [1.1.0](https://github.com/ramsesoriginal/lorenzo/compare/maps-v1.0.0...maps-v1.1.0) (2026-11-27)


### Features

* **maps,map-engine:** cells are written as merged outlines, and a drawing may be larger ([d8c8774](https://github.com/ramsesoriginal/lorenzo/commit/d8c877491dab58dccd20aa9851814b230f2af89c))
* **maps,map-renderer:** the Height brush raises and lowers the land of an entry's height lines ([c95715e](https://github.com/ramsesoriginal/lorenzo/commit/c95715e38abc20dfa1443366b677c660c602dad6))
* **maps:** a Location's drawing of several parts is split into places inside it ([d5d9975](https://github.com/ramsesoriginal/lorenzo/commit/d5d9975cfdb35934c6a711e26426a9f27bcf2487))
* **maps:** an area along the grid keeps its points, the area a fill works in is not a tile, and the docs say so ([62b31bd](https://github.com/ramsesoriginal/lorenzo/commit/62b31bd539a892c8ede91a73ed21cf54ce0bc90d))
* **maps:** mirror, turn and copy a drawing about the sheet's middle ([5fb2b82](https://github.com/ramsesoriginal/lorenzo/commit/5fb2b8241431bbe9c21b72205cf81d0d057f8de8))
* **maps:** the Height brush draws its lines as smooth curves ([118d565](https://github.com/ramsesoriginal/lorenzo/commit/118d56509f1ec98e8c604572ff20571acfe8215e))
* **maps:** the Height brush draws its lines as smooth curves (ADR 0491) ([a2531e2](https://github.com/ramsesoriginal/lorenzo/commit/a2531e207d793e304503eb6a1619d5a89ce06ca5))


### Bug Fixes

* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([4f9f113](https://github.com/ramsesoriginal/lorenzo/commit/4f9f113f41773c5ea37e25f60e044c79e82febaf))
* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([c999469](https://github.com/ramsesoriginal/lorenzo/commit/c99946948d328af2fd5d9de32373ad2abd61d03a)), closes [#1255](https://github.com/ramsesoriginal/lorenzo/issues/1255)
* **maps:** the command line keeps its width when it has answered ([19f49cb](https://github.com/ramsesoriginal/lorenzo/commit/19f49cb96e986dabac1a42dce0bb1a4d419519c0))

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

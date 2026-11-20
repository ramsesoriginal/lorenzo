# Changelog

## [1.1.0](https://github.com/ramsesoriginal/lorenzo/compare/maps-v1.0.0...maps-v1.1.0) (2026-11-20)


### Features

* **api,maps:** a Location's Map count, the Maps it is on and where each character says it is ([#1214](https://github.com/ramsesoriginal/lorenzo/issues/1214)) ([4656234](https://github.com/ramsesoriginal/lorenzo/commit/465623443b61820f280f505dbcb9832dd7783a5b))
* **api,maps:** the Locations pages' Map count, On these Maps and Where is… ([#1214](https://github.com/ramsesoriginal/lorenzo/issues/1214)) ([1fadc57](https://github.com/ramsesoriginal/lorenzo/commit/1fadc57e48473b2619231f764d9825d28b021c9e))
* **maps,map-engine:** cells are written as merged outlines, and a drawing may be larger ([d8c8774](https://github.com/ramsesoriginal/lorenzo/commit/d8c877491dab58dccd20aa9851814b230f2af89c))
* **maps,map-renderer:** Fill by wave function collapse, learned from the cells drawn on the Map ([e490180](https://github.com/ramsesoriginal/lorenzo/commit/e490180421363d079e1c30aa2ee7862d4a9921af))
* **maps,map-renderer:** the Height brush raises and lowers the land of an entry's height lines ([c95715e](https://github.com/ramsesoriginal/lorenzo/commit/c95715e38abc20dfa1443366b677c660c602dad6))
* **maps,map-renderer:** the Height brush raises and lowers the land of an entry's height lines ([fbe79c8](https://github.com/ramsesoriginal/lorenzo/commit/fbe79c86b14d5755f42dfec70b7b83f36ac85784))
* **maps,map-renderer:** the Height line tool, and a line says the value it carries ([99c8e9d](https://github.com/ramsesoriginal/lorenzo/commit/99c8e9d57463b55f816f30adcc3a805672d17be9))
* **maps,map-renderer:** what the generators share: the validator mirrored, a seed, a region and a filled overlay ([56b8ea2](https://github.com/ramsesoriginal/lorenzo/commit/56b8ea2ebacc82a2dc78dfc304bad7530c6d6843))
* **maps:** a drawing of several parts, or an area with holes, is changed a part at a time ([eadc071](https://github.com/ramsesoriginal/lorenzo/commit/eadc071a3c34da30ee783e06af949b3f91febf90))
* **maps:** a height line of a fill ends at the edge of its region ([9d893ec](https://github.com/ramsesoriginal/lorenzo/commit/9d893ecf517129918f75324e43b1415d570cfc4c))
* **maps:** a Location's drawing of several parts is split into places inside it ([d5d9975](https://github.com/ramsesoriginal/lorenzo/commit/d5d9975cfdb35934c6a711e26426a9f27bcf2487))
* **maps:** a phone reads in full and makes small changes (UI-E Maps, M4; ADR 0462) ([e70a891](https://github.com/ramsesoriginal/lorenzo/commit/e70a891b02b95170deb6e9e848b5dd0bcfdb4d17))
* **maps:** a tool declares its options, drawn in the Options tab and set on the command line ([c7c96b8](https://github.com/ramsesoriginal/lorenzo/commit/c7c96b8cb715e1323b798794839601dcc3e494b9))
* **maps:** an area along the grid keeps its points, the area a fill works in is not a tile, and the docs say so ([62b31bd](https://github.com/ramsesoriginal/lorenzo/commit/62b31bd539a892c8ede91a73ed21cf54ce0bc90d))
* **maps:** Fill by wave function collapse learns from another Map of the library ([e289c73](https://github.com/ramsesoriginal/lorenzo/commit/e289c732421deb4fc6ca19850ed29f03b49362e7))
* **maps:** Locations and a Location's page in the new frame (UI-E Maps, M2; ADR 0462) ([f1d99a7](https://github.com/ramsesoriginal/lorenzo/commit/f1d99a711027c969249fb4c4054c5f087019fa51))
* **maps:** mirror, turn and copy a drawing about the sheet's middle ([5fb2b82](https://github.com/ramsesoriginal/lorenzo/commit/5fb2b8241431bbe9c21b72205cf81d0d057f8de8))
* **maps:** remappable tool keys and the Shortcuts dialog (UI-E Maps M5d) ([2457261](https://github.com/ramsesoriginal/lorenzo/commit/24572619dd9be98b49de9dbe5469439347f67df0))
* **maps:** the Cave system generator, previewed, compared and applied as one step ([066599a](https://github.com/ramsesoriginal/lorenzo/commit/066599a1da6204b4d0a7e840693594c1368d5e98))
* **maps:** the cells beside a cell, and wave function collapse learned from an example ([5c53482](https://github.com/ramsesoriginal/lorenzo/commit/5c53482bac2fe2fa3871585461d6808c5e0700de))
* **maps:** the command line takes the points of a drawing (UI-E Maps M6) ([7c7e1e0](https://github.com/ramsesoriginal/lorenzo/commit/7c7e1e0485847cfb5630f780881acb55594e4168))
* **maps:** the command line under the Map (UI-E Maps M5c) ([168d135](https://github.com/ramsesoriginal/lorenzo/commit/168d135fb4fb3930590de392b97167b8f039064e))
* **maps:** the Fill by marching squares generator, with height lines that need their heights ([23ab5f6](https://github.com/ramsesoriginal/lorenzo/commit/23ab5f6f88eb64a8c44731f98226a79da46f3715))
* **maps:** the Freehand tool, a dragged stroke simplified into a line ([415fc40](https://github.com/ramsesoriginal/lorenzo/commit/415fc40fde989fee912994ad4d1f6527d09ed7bf))
* **maps:** the gallery of Maps with small drawings (UI-E Maps, M1; ADR 0462) ([b07b25b](https://github.com/ramsesoriginal/lorenzo/commit/b07b25b33947b426ce49c11ee3eaa1e44f995344))
* **maps:** the Height brush draws its lines as smooth curves ([118d565](https://github.com/ramsesoriginal/lorenzo/commit/118d56509f1ec98e8c604572ff20571acfe8215e))
* **maps:** the Height brush draws its lines as smooth curves (ADR 0491) ([a2531e2](https://github.com/ramsesoriginal/lorenzo/commit/a2531e207d793e304503eb6a1619d5a89ce06ca5))
* **maps:** the Map fills the page, with floating controls and a slide-over panel (UI-E Maps, M3; ADR 0462) ([d53561d](https://github.com/ramsesoriginal/lorenzo/commit/d53561d46398264bd8308c422319f0091829372e))
* **maps:** the options bar is the sidebar's Options tab, beside the Map (UI-E Maps M6) ([d7aed01](https://github.com/ramsesoriginal/lorenzo/commit/d7aed019899024154653f852a5e0b66069c9edc1))
* **maps:** the outliner and PLACE take any entry, not only places (UI-E Maps M6) ([72570ea](https://github.com/ramsesoriginal/lorenzo/commit/72570ea809053cc505a824b6502fba5bc2de724b))
* **maps:** the outliner, dragging onto the Map and History (UI-E Maps M5b) ([13b1dcf](https://github.com/ramsesoriginal/lorenzo/commit/13b1dcfb5cdb3cd8264f3fb562560b9a66364cc7))
* **maps:** the Spline tool, a curve through points written as one bezier part ([a8d6e20](https://github.com/ramsesoriginal/lorenzo/commit/a8d6e20739fae1e3d8f74fcd22fca72e29efcb4f))
* **maps:** the Spline tool, a curve through points written as one bezier part (ADR 0471) ([bc0ce6d](https://github.com/ramsesoriginal/lorenzo/commit/bc0ce6d54c49257e2eb7698a3aa10e7ccfcc4f86))
* **maps:** the tones of a fill's tiles are spread over the whole range ([3c47df1](https://github.com/ramsesoriginal/lorenzo/commit/3c47df1a69c12a1d516882ffd13c3a763950de92))
* **maps:** the toolbox is drawn from a tool registry, one key a tool (UI-E Maps, M5a; ADR 0462) ([031ed0d](https://github.com/ramsesoriginal/lorenzo/commit/031ed0dcda2e7741bec10fc49cd1f8bd42f020ff))


### Bug Fixes

* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([4f9f113](https://github.com/ramsesoriginal/lorenzo/commit/4f9f113f41773c5ea37e25f60e044c79e82febaf))
* **map-engine,maps:** a number is read as its nearest six decimals in its own scale ([c999469](https://github.com/ramsesoriginal/lorenzo/commit/c99946948d328af2fd5d9de32373ad2abd61d03a)), closes [#1255](https://github.com/ramsesoriginal/lorenzo/issues/1255)
* **maps:** an edit keeps the value and unit a part carries ([2a03975](https://github.com/ramsesoriginal/lorenzo/commit/2a039755352b1f416352589d7742cce67f6e37da))
* **maps:** caves on a very small or a very large sheet are ones the API takes ([1bbee85](https://github.com/ramsesoriginal/lorenzo/commit/1bbee8537717c5f22676b942fa194d54ffb987fb))
* **maps:** the command line keeps its width when it has answered ([19f49cb](https://github.com/ramsesoriginal/lorenzo/commit/19f49cb96e986dabac1a42dce0bb1a4d419519c0))
* **maps:** the command line keeps its width when it has answered ([a5fd1de](https://github.com/ramsesoriginal/lorenzo/commit/a5fd1de6ab002f1bf2fd2ebc448a2f35ae73c132))
* **maps:** the panel takes no press while a write is on its way ([95cf14e](https://github.com/ramsesoriginal/lorenzo/commit/95cf14e7d6848cb8ffbc78464875f7730dd65952))
* **maps:** the role's comment stands above the role again ([0db7141](https://github.com/ramsesoriginal/lorenzo/commit/0db71413ea38129572793539295b2e981a632725))
* **maps:** the tools wrap inside the card and the command line takes its width (UI-E Maps) ([92b3892](https://github.com/ramsesoriginal/lorenzo/commit/92b3892bad7287e67f5c84e3cc908e093c03dbdf))

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

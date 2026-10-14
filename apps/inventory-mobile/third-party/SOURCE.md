# Asset provenance

- Geist and Newsreader: converted to unmodified OpenType glyphs from `apps/brand/fonts` using fontTools (WOFF2 container to TTF container). SIL Open Font License 1.1; see adjoining license files. Source: [Geist](https://github.com/google/fonts/tree/main/ofl/geist) and [Newsreader](https://github.com/google/fonts/tree/main/ofl/newsreader).
- UI icons: Android VectorDrawable conversions of Lorenzo's shared Tabler atlas at `apps/brand/icons.svg`. Back, being, container, expand (rotated), search, refresh, logout. Tabler MIT license retained. Source: [Tabler icons](https://github.com/tabler/tabler-icons).
- Brand mark: exact master path from `docs/brand/assets/brand_mark.svg`, retaining its even-odd knockout. Launcher and app header use the same artwork.
- Captured from Lorenzo main `126e959` on 2026-10-14. Refresh copied assets deliberately when the brand changes; do not invent a second icon system.
- Dependencies declared in Gradle keep their upstream licenses. Markwon is Apache-2.0; Kotlin/coroutines/serialization, AndroidX, and OkHttp are Apache-2.0.

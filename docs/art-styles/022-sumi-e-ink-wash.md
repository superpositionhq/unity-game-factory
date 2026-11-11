# Sumi-e ink wash

Reference works: Okami.

## References

- *Okami* (2006), Clover Studio, video game. https://en.wikipedia.org/wiki/Ōkami
- *Okamiden* (2010), Capcom, video game. https://en.wikipedia.org/wiki/Ōkamiden
- *Pine Trees* (1595), Hasegawa Tohaku, ink on paper folding screens. https://en.wikipedia.org/wiki/Shōrin-zu_byōbu
- *The Tale of the Princess Kaguya* (2013), Studio Ghibli (Isao Takahata), animated film. https://en.wikipedia.org/wiki/The_Tale_of_the_Princess_Kaguya_(film)

## Visual definition

- **Shape language and proportions:** Simplified, flowing forms. Trees, hills and clouds are stylised into curls and sweeping curves; characters are compact with expressive silhouettes.
- **Line and outline:** Black brush line with strong calligraphic variation: thick in the middle of a stroke, thin and dry at the ends, with breaks. Lines overshoot corners.
- **Shading model:** Two tones: base wash and a slightly darker wash. No smooth light gradient.
- **Palette:** `#1c1a17` `#f3ead7` `#b23a2e` `#6f8f5e` `#d9a441` `#5b6f8c` `#e9c9b1`. Warm paper ground, ink black, and thin washes of vermilion, moss green, ochre and indigo.
- **Lighting:** None in the physical sense. A soft directional wash only.
- **Texture and surface:** Paper fibre over everything. Colour sits as uneven wash with darker pooled edges. Dry-brush streaks in strokes.
- **Atmosphere and post-processing:** Full-frame paper texture multiply, slight edge darkening, ink-bleed blur on lines.
- **Camera and framing:** Wide landscape views with large empty paper areas; 35 mm equivalent.
- **UI and typography:** Panels are paper scrolls with torn or brushed edges; icons are round ink-seal stamps and small brush drawings, and counters are rows of ink pots. Headings and numerals are hand-lettered brush script. Text is ink black `#1c1a17` on paper `#f3ead7`, with vermilion `#b23a2e` for seals and health.
- **VFX and motion:** Effects are brush strokes: a slash is one sweeping black stroke that fades dry, hits burst into ink splashes, and flowers and petals bloom along the hero's path. Animation is flowing, with trailing ink lines behind fast motion.

## Fits

- **Genres:** `action-adventure`, `exploration`, `rpg`, `puzzle`, `hack-and-slash`, `soulslike`
- **Moods:** serene, mythic, playful
- **Settings:** mythic Japan, mountain villages, misty pine forests, spirit shrines

## Unity recipe

### Assets

Simple flowing models: compact characters with expressive silhouettes, trees, hills and clouds stylised into curls. Build scenery from scratch where possible; store models need their textures removed and colours reduced to thin washes of vermilion, moss, ochre and indigo. Generate by script: a tileable paper-fibre texture, a dry-brush stroke texture with broken ends, and a wash-variation noise with darker pooled edges. Leave large parts of each scene empty so the paper shows.

### Materials

Write `Style/InkWash`. `UniversalForward` outputs the base wash and one slightly darker wash chosen by a soft directional term from `GetMainLight()`, both multiplied by the wash-variation noise in screen or triplanar space; darken the wash near silhouette edges (`1 - NdotV`) to imitate pooled pigment. Alpha toward the paper colour at low coverage so objects fade into the ground. Brush lines cannot come from a constant hull: use an `SRPDefaultUnlit` hull pass whose width is modulated by a low-frequency noise along the surface and by view angle (thick mid-stroke, thin ends) and whose alpha is cut by the dry-brush texture to create breaks. Passes `DepthOnly` and `DepthNormals`; a `ShadowCaster` pass is optional because shadows are not drawn.

### Lighting and atmosphere

One directional light as a direction for the wash only, shadows off. Flat ambient. No fog component: the camera background and far planes are the paper colour `#f3ead7`, and distant objects lerp toward it. No SSAO, no probes, no skybox.

### Post-processing

Two fullscreen passes. Before post-processing: an ink line pass from depth and normals whose line colour is blurred slightly (sample the edge mask with a small disc) to imitate bleed, and whose sample position is displaced by noise so lines overshoot corners. After post-processing: multiply the paper-fibre texture over the whole frame and darken the frame edges slightly. Tonemapping None; no Bloom.

### UI and effects

Panels are paper scroll sprites with torn or brushed edges; icons are round vermilion seal stamps and small brush drawings; counters are rows of ink pots. Use a brush-lettered face such as Yuji Boku or Kaushan Script for headings and numerals. Effects are strokes: a slash is one `TrailRenderer` or mesh ribbon with the dry-brush texture that fades from the tail, hits spawn ink-splash flipbooks, and petals bloom along the hero's path with small mesh particles.

## Do / Do not

Do:

- Vary stroke width from zero to very thick.
- Leave large areas of bare paper.
- Multiply a paper texture over the full frame.
- Let lines break and overshoot.

Do not:

- Do not use even-width outlines with flat clean fills; that reads as `082` or `011`.
- Do not drop line work and rely on soft watercolour shapes; that reads as `025`.
- Do not add three bands with pen hatching; that reads as `001`.
- Do not use saturated opaque colour.

## Nearest styles

- `082` Ukiyo-e woodblock: lines here swell, dry out and break like brush strokes, and colour pools unevenly in two wash tones; `082` has an even, fine carved keyline around clean flat printed colour.
- `025` Watercolour wash minimal: here almost every form is drawn with a black brush line; `025` is mostly lineless, built from soft pale wash shapes.
- `007` Rubber-hose 1930s cartoon: the line here runs from hair-thin to very thick over uneven washes on bare paper; `007` uses a thick outline of even weight around flat fills, with aged film grain.

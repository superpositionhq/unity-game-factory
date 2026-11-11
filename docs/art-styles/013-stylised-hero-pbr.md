# Stylised hero PBR

Reference works: Overwatch.

## References

- *Overwatch* (2016), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/Overwatch_(2016_video_game)
- *Overwatch 2* (2022), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/Overwatch_(2023_video_game)
- *Valorant* (2020), Riot Games, video game. https://en.wikipedia.org/wiki/Valorant
- *Fortnite* (2017), Epic Games, video game. https://en.wikipedia.org/wiki/Fortnite
- *Big Hero 6* (2014), Walt Disney Animation Studios, animated film. https://en.wikipedia.org/wiki/Big_Hero_6_(film)

## Visual definition

- **Shape language and proportions:** Heroic, slightly exaggerated proportions with clean large forms, chamfered hard-surface armour and readable silhouettes. Small detail is grouped into a few areas.
- **Line and outline:** No outline.
- **Shading model:** Full PBR with smooth gradients, simplified: broad clean roughness regions, soft ambient occlusion and bright rim light.
- **Palette:** `#f79e1b` `#2d9cdb` `#f2f2f2` `#3c4654` `#e74c3c` `#7ed6a5` `#ffd66b`. Bright, optimistic: clean white and grey armour with orange, blue and teal accents; emissive strips.
- **Lighting:** Sunny key, strong coloured fill and bounce; environments are evenly lit and airy.
- **Texture and surface:** Clean material definition with hand-painted gradients inside PBR maps; little noise or grime.
- **Atmosphere and post-processing:** Bloom on emissives, mild colour grade toward warm highlights and cool shadows, anti-aliased.
- **Camera and framing:** Third or first person, 40 to 50 mm equivalent, heroic low angles.
- **UI and typography:** Slanted, semi-transparent dark panels with chamfered corners and thin white edges; icons are flat white glyphs in circles or hexagons. Text is a bold italic condensed sans in white, with orange for the player and blue or red for teams. Damage numbers and ability counters are large slanted white numerals that pop and fade, with yellow for critical hits.
- **VFX and motion:** Effects are clean, bright shapes colour-coded per character: thick tracer streaks, soft-edged energy shields, chunky sparks and a short shaped flash on hit. Animation is snappy with strong anticipation, slight squash and stretch and a clear held pose at the end of each move.

## Fits

- **Genres:** `fps`, `third-person-shooter`, `top-down-shooter`, `tower-defense`, `vehicle-combat`, `sports`
- **Moods:** optimistic, energetic, heroic
- **Settings:** near-future city, sunny Mediterranean town, high-tech laboratory, moon base

## Unity recipe

### Assets

Hero-shooter style packs: slightly heroic proportions, chamfered hard-surface armour, clean large forms. Store PBR packs are a good base because the style keeps PBR. Clean them in an editor step: remove grime and noise from albedo with a strong blur plus palette remap, add a soft top-to-bottom gradient, and rebuild the smoothness map as a few broad flat regions instead of scratches. Keep normal maps for bevels and panel breaks only. Add emissive strips as separate thin meshes or an emission mask painted by script.

### Materials

`Universal Render Pipeline/Lit` (metallic workflow) is the right shader; no custom lighting is needed. The editor step sets `_BaseMap`, a reduced `_BumpScale`, `_Metallic`, `_Smoothness`, the occlusion map, and enables `_EMISSION` with an HDR `_EmissionColor` of 2 to 4 for strips. For the bright rim, either place rim lights or write a thin variant shader that fills `SurfaceData`, calls `UniversalFragmentPBR` and adds a Fresnel term to emission; that variant needs the same passes as Lit (`UniversalForward`, `ShadowCaster`, `DepthOnly`, `DepthNormals`, `Meta`). Use `Universal Render Pipeline/Complex Lit` with clear coat for lacquered armour if wanted.

### Lighting and atmosphere

A sunny mixed directional key with soft shadows, four cascades, 120 m. Strong coloured fill is the signature: bake indirect light with Adaptive Probe Volumes and lightmaps on static scenery, raise indirect intensity, and add a few baked area or point lights in accent colours. Baked reflection probes with box projection per room. SSAO on with low intensity and a wide radius. Thin, bright fog only for depth; a clear procedural sky.

### Post-processing

ACES or Neutral tonemapping with post exposure tuned so whites stay clean. Bloom with threshold about 1, moderate intensity, for emissives. Split Toning or Shadows Midtones Highlights for warm highlights and cool shadows; saturation +10. Anti-aliasing by TAA or SMAA, MSAA optional. No grain, outline or vignette. HDR on, render scale 1.

### UI and effects

Font asset from a bold italic condensed sans such as Barlow Condensed Bold Italic or Saira Condensed, white. Panels are semi-transparent dark slanted shapes with chamfered corners and thin white edges; icons are white glyphs in circles or hexagons. Damage numbers pop to 130 percent then fade, `#ffd66b` for critical hits. Effects are clean and colour-coded per character: thick stretched-billboard tracers, Fresnel-shaded shield spheres, chunky spark meshes and a short shaped additive flash. Keep lifetimes brief.

## Do / Do not

Do:

- Bevel every hard edge.
- Group detail into a few clusters and leave large clean areas.
- Add emissive accents with bloom.
- Keep roughness regions broad and distinct.

Do not:

- Do not add photographic grime and noise; that reads as `032` or `030`.
- Do not paint heavy detail into albedo with little PBR response; that reads as `023`.
- Do not mute the palette and tint the terminator; that reads as `005`.
- Do not add outlines or bands.

## Nearest styles

- `005` Rim-lit illustrative caricature: `005` uses muted, earthy colours with a warm tint where light turns to shadow; this style is bright and clean with white armour and vivid accent colours.
- `023` Chunky hand-painted fantasy: `023` paints highlights, shadows and wear directly into its textures; this style keeps surfaces clean and lets real light show metal, plastic and cloth.
- `006` Glossy ink-splat pop: `006` covers the scene in wet, glossy splats of two opposing ink colours; this style spreads many accent colours over clean white and grey surfaces.

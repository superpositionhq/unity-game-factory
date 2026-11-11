# Brush-block martial painterly

Reference works: Sifu.

## References

- *Sifu* (2022), Sloclap, video game. https://en.wikipedia.org/wiki/Sifu_(video_game)
- *Absolver* (2017), Sloclap, video game. https://en.wikipedia.org/wiki/Absolver
- *Hero* (2002), Zhang Yimou, live-action film. https://en.wikipedia.org/wiki/Hero_(2002_film)

## Visual definition

- **Shape language and proportions:** Realistic proportions with simplified planes. Faces, cloth and furniture are reduced to broad, slightly angular surfaces as if blocked in with a wide brush.
- **Line and outline:** No outline.
- **Shading model:** Three to five broad tone steps with soft but visible boundaries, like a gouache study. No fine gradient, no sharp specular.
- **Palette:** `#c94f3d` `#e8c9a0` `#2f4858` `#6b8f71` `#f2a65a` `#3b2f2f` `#d8d2c4`. Each location has one dominant hue (red club, teal museum, warm wood dojo) with skin and cloth in muted complementary tones.
- **Lighting:** Strong coloured key light per room, large soft shadows, practical lamps as flat glowing shapes.
- **Texture and surface:** Low detail. Surfaces show large brush patches and soft tonal blocks; no pores, no grain, no small scratches.
- **Atmosphere and post-processing:** Mild bloom on lamps, light atmospheric haze tinted with the room colour, soft vignette.
- **Camera and framing:** Third-person at shoulder height, 35 mm equivalent, corridors and rooms framed in one-point perspective.
- **UI and typography:** Almost frameless UI: bars drawn as single thin brush strokes and round ink-seal icons, with no bevelled panels. Labels use a clean condensed sans; chapter cards and counters use brush-lettered numerals. Bone `#d8d2c4` text sits on dark brown `#3b2f2f`, with red `#c94f3d` for damage and alerts.
- **VFX and motion:** Snappy martial-arts animation: fast strikes with a short held pose on each impact and slow motion on finishing blows. Hits show a brief flat brush-smear flash and a small dust puff; no spark showers or flying debris.

## Fits

- **Genres:** `fighting`, `hack-and-slash`, `action-adventure`, `stealth`, `roguelike`, `soulslike`
- **Moods:** focused, vengeful, stylish
- **Settings:** kung fu dojo, neon nightclub, art museum, Chinese city back streets

## Unity recipe

### Assets

Realistic-proportion characters and interiors (clubs, dojos, museums, corridors) with simplified planes. Reduce pack meshes slightly with flat, broad surfaces; a light decimation pass in Blender can help faces and cloth read as planes. Remove normal maps and all small detail. Blur and posterise each albedo in an editor step into large soft patches, 512 px is enough. Lamps are simple shapes with a flat emissive face.

### Materials

Write `Style/BrushBlock`. `UniversalForward` sums `GetMainLight(shadowCoord)` and additional lights into a diffuse value, then quantises it into three to five steps with soft but visible boundaries: `floor(v * n) / n` blended with a short `smoothstep` at each step. Perturb the value before quantising with a large, low-contrast brush-patch noise in object space so step boundaries look blocked in with a wide brush, not computed. No specular highlight; no outline. Tint the darker steps toward the room's dominant hue using a global colour. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`, and `Meta` for baking.

### Lighting and atmosphere

Each room has one strong coloured key (spot or directional through a window) with large soft shadows: soft shadows at high quality. Practical lamps are emissive shapes plus a point light. Bake Adaptive Probe Volumes so the room hue fills the shadows. Light exponential fog tinted with the room colour. SSAO on at low intensity, wide radius. Reflection probes can be left at low strength.

### Post-processing

A light Kuwahara-style Full Screen Pass Renderer Feature before post-processing with a small radius (3 to 4 px) merges remaining detail into tone blocks. Mild Bloom on lamps, soft Vignette, Neutral tonemapping, and a per-room Volume with a Color Adjustments filter in that room's hue. SMAA.

### UI and effects

Nearly frameless UI: bars are single thin brush-stroke sprites, icons are round ink-seal stamps. Labels from a clean condensed sans such as Barlow Condensed; chapter cards and counters from a brush face such as Yuji Boku or Permanent Marker. `#d8d2c4` text on `#3b2f2f`, red `#c94f3d` for damage. Hit effects: a flat brush-smear sprite for two or three frames and a small dust puff; no sparks or debris. Add a short hold on impact and slow motion through `Time.timeScale` on finishers.

## Do / Do not

Do:

- Give each room one dominant light colour.
- Keep tone steps broad and few.
- Simplify surfaces into large planes.
- Remove small-scale surface detail.

Do not:

- Do not add outlines or hard two-band cel edges; that reads as `015`.
- Do not add dense brush-stroke texture and painted highlights; that reads as `024`.
- Do not use full photoreal materials; that reads as `029`.
- Do not use flat unlit colour layers; that reads as `060`.

## Nearest styles

- `024` Brush-textured 3D drama: this style keeps surfaces as large soft tone blocks with no small marks; `024` shows individual brush strokes and painted highlight marks on every surface.
- `026` Oily concept-art realism: here light falls in three to five visible steps and each room is bright and strongly coloured; `026` has smooth gradients and darker, grey rooms with little colour.
- `060` Layered flat-colour wilderness: forms here are shaded as rounded volumes in muted colours; `060` is stacked flat colour layers with no volume, in vivid sunset colours.

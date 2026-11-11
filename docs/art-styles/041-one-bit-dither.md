# One-bit dither

Reference works: Return of the Obra Dinn.

## References

- *Return of the Obra Dinn* (2018), Lucas Pope, video game. https://en.wikipedia.org/wiki/Return_of_the_Obra_Dinn
- *Dark Castle* (1986), Silicon Beach Software, video game. https://en.wikipedia.org/wiki/Dark_Castle
- *Shadowgate* (1987), ICOM Simulations, video game. https://en.wikipedia.org/wiki/Shadowgate
- *World of Horror* (2023), Panstasz, video game. https://en.wikipedia.org/wiki/World_of_Horror

## Visual definition

- **Shape language and proportions:** Realistic 3D forms at modest polygon counts; ships, rooms, figures. The form is described entirely by dither density and edge lines.
- **Line and outline:** One-pixel lines on silhouettes and creases, drawn in the dark value on light areas and in the light value on dark areas.
- **Shading model:** Continuous light is converted to two values by dithering. Three or four dither densities are visible as distinct tone steps.
- **Palette:** `#333319` `#e5ffff` `#000000` `#ffffff` `#2b2b26`. Exactly two values: a dark and a light. Either pure black and white or a tinted pair such as dark olive and pale cyan-white.
- **Lighting:** Strong single light so forms split clearly into light, dithered midtone and dark.
- **Texture and surface:** Dither is the texture: ordered Bayer pattern on smooth surfaces, blue-noise pattern on organic ones.
- **Atmosphere and post-processing:** Low output resolution (about 640x360 to 800x450), nearest upscale, dither pattern stabilised against camera motion.
- **Camera and framing:** First-person, 60 to 70 degree field of view.
- **UI and typography:** Plain boxes with one-pixel ruled borders, like early desktop windows and the pages of a ship's ledger; icons are small two-value pictograms. Text is a serif book face or a hand-written ledger script drawn as crisp bitmap, with plain tabular figures for counts and times. The UI uses only the same two values and inverts them to mark a selection.
- **VFX and motion:** Particles are single pixels or small dithered clusters: dust, sparks, sea spray, gun smoke. An impact shows as a white flash or a brief inversion of the whole frame. Motion is sparse, with frozen tableaux, a slow camera and held poses of a few frames.

## Fits

- **Genres:** `detective-mystery`, `exploration`, `puzzle`, `survival-horror`
- **Moods:** eerie, austere, mysterious
- **Settings:** 19th-century sailing ship, haunted castle, cursed coastal town

## Unity recipe

### Assets

Realistic forms at modest polygon counts: ships, rooms, furniture, figures. Any realistic pack works, since only form survives. Remove colour and keep a greyscale albedo with strong value differences between materials, so objects separate. Keep normals smooth; remove normal maps or keep them weak. Tag materials as smooth or organic so the shader can choose a Bayer or blue-noise pattern. Generate an 8x8 Bayer matrix texture and a 64x64 blue-noise texture by script (point filtered, repeat).

### Materials

Models can stay on `Universal Render Pipeline/Lit` or Simple Lit with grey albedo and low smoothness; the look comes from the fullscreen pass. To stabilise the dither against camera motion, a custom shader is better: `Style/DitherSurface` computes luminance from `GetMainLight(shadowCoord)` in `UniversalForward` and thresholds it against the dither texture sampled with UVs derived from a sphere-mapped or object-space projection instead of raw screen pixels, then writes only 0 or 1. Quantise luminance first to three or four levels so distinct dither densities are visible. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`.

### Lighting and atmosphere

One strong directional or point light with hard shadows, so forms split into light, dithered midtone and dark. Ambient very low. No fog, GI or SSAO.

### Post-processing

Render at 640x360 to 800x450 (low-resolution target or render scale, Point upscaling). A fullscreen pass with depth and normals draws one-pixel edge lines, choosing the light value over dark areas and the dark value over light areas. A final pass maps 0 and 1 to the chosen pair, for example `#333319` and `#e5ffff`. Tonemapping None, HDR off, no anti-aliasing, no Bloom.

### UI and effects

Plain boxes with one-pixel ruled borders, like early desktop windows or ledger pages; two-value pictogram icons; selection by inversion. Use a serif book face or a ledger script rendered as crisp bitmap: create the TextMeshPro asset in raster mode at the exact pixel size, for example from IM Fell English or a pixel serif. Tabular figures for counts and times. Particles are single pixels or tiny dithered clusters; impacts are a white flash or a one-frame inversion. Keep the camera slow and hold poses.

## Do / Do not

Do:

- Output exactly two colours.
- Dither with a stable ordered or blue-noise pattern.
- Draw one-pixel edges that invert against the local tone.
- Render at low resolution with nearest upscale.

Do not:

- Do not use round print dots and pen-weight outlines on white; that reads as `020`.
- Do not use four shades; that reads as `038`.
- Do not build tone from parallel engraved lines; that reads as `072`.
- Do not let the dither pattern swim with camera rotation.

## Nearest styles

- `020` Manga screentone monochrome: `020` is mostly white paper with round print dots and pen-weight outlines; this style is mostly dark, with pixel-scale dither patterns and one-pixel lines.
- `072` Engraved crosshatch print: `072` builds tone from parallel engraved lines on bright paper and outlines almost every form; this style is darker, builds tone from pixel dither and leaves some edges without a line.
- `038` Game Boy four-shade green: `038` shows four shades of green; this style shows only two values, one dark and one light.

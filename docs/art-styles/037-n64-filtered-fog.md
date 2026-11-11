# N64 filtered fog

Reference works: Super Mario 64; Ocarina of Time.

## References

- *Super Mario 64* (1996), Nintendo EAD, video game. https://en.wikipedia.org/wiki/Super_Mario_64
- *The Legend of Zelda: Ocarina of Time* (1998), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Ocarina_of_Time
- *Banjo-Kazooie* (1998), Rare, video game. https://en.wikipedia.org/wiki/Banjo-Kazooie_(video_game)
- *GoldenEye 007* (1997), Rare, video game. https://en.wikipedia.org/wiki/GoldenEye_007

## Visual definition

- **Shape language and proportions:** Low polygon counts with rounded, friendly forms: characters built from smooth-shaded segments, large simple hills, blocky castles.
- **Line and outline:** No outline.
- **Shading model:** Smooth per-vertex (Gouraud) shading with vertex-colour gradients baked into geometry.
- **Palette:** `#3a7fd5` `#4caf50` `#e53935` `#fdd835` `#8d6e63` `#b0bec5` `#f5f5f5`. Bright primary colours: blue sky, green grass, red and yellow accents.
- **Lighting:** Simple directional light plus ambient; fake shadows as dark round blobs.
- **Texture and surface:** Very small textures stretched over large surfaces and blurred by bilinear filtering; visible repetition.
- **Atmosphere and post-processing:** 320x240 output with soft blur from filtering and anti-aliasing; distance fog in a flat colour; no dither pattern.
- **Camera and framing:** Third-person follow camera, 45 to 60 degree field of view.
- **UI and typography:** Chunky rounded icons that look like small rendered 3D objects, with no panel frames around them. Titles use thick bubbly display lettering with a dark outline and drop shadow; text is a rounded bold sans. Counters are an icon, a cross and big outlined numerals in yellow `#fdd835` or white `#f5f5f5`.
- **VFX and motion:** A few large soft-edged sprites: star sparkles, round dust clouds, smoke balls and a simple coloured flash on a hit. Animation is bouncy and exaggerated, with squash and stretch on jumps and simple, readable run cycles.

## Fits

- **Genres:** `platformer`, `action-adventure`, `exploration`, `racing`, `fps`, `sports`
- **Moods:** cheerful, playful, nostalgic
- **Settings:** castle grounds, green fields and villages, tropical islands, snowy mountains

## Unity recipe

### Assets

Low-poly but rounded and friendly: characters built from separate smooth-shaded segments (no skin deformation needed), large simple hills, blocky castles. Reduce store models and smooth their normals. Rebake textures to 32 or 64 px and import them with bilinear filtering and wrap repeat so they stretch and blur over large surfaces. Bake gradients into vertex colour in an editor step: darker at the base of walls and under overhangs, lighter on top.

### Materials

Write `Style/SoftVertexLit`: `UniversalForward` with per-vertex Lambert from `GetMainLight()` plus ambient, multiplied by vertex colour and the bilinear-filtered texture; fog computed per vertex with `ComputeFogFactor` and applied with `MixFog`. No vertex snapping and no affine warping: geometry is steady. No specular, no normal maps. Add `DepthOnly`. Shadows are not cast: characters get a dark round blob quad projected on the ground.

### Lighting and atmosphere

One directional light and bright flat ambient; shadows disabled in the URP asset. Linear fog in a flat colour that matches the sky (pale blue or white), starting at mid distance, with the far clip plane at the fog end. Sky is a flat colour or simple two-colour gradient. No SSAO, GI or probes.

### Post-processing

Render at 320x240 and upscale with bilinear filtering so the image is soft, the opposite of a sharp pixel look: use a low-resolution `RenderTexture` with `FilterMode.Bilinear`, or render scale near 0.25 with the Linear upscaling filter. Add a slight horizontal blur pass on the low-resolution target to imitate the console's edge smoothing. No dither pattern. Tonemapping None, no Bloom, saturation +10 for bright primaries. HDR off.

### UI and effects

No panel frames. Icons look like small rendered 3D objects: render them from the models with an editor step camera. Titles use thick bubbly lettering such as Chewy or Luckiest Guy with a dark outline and drop shadow (TextMeshPro outline and underlay); text in a rounded bold sans such as Baloo 2. Counters read icon, cross, numeral in `#fdd835` or white. Effects are a few large soft-edged sprites: star sparkles, round dust clouds, smoke balls, a coloured flash on hit. Animate with bounce and squash on jumps.

## Do / Do not

Do:

- Blur small textures with bilinear filtering.
- Paint gradients with vertex colours.
- Use blob shadows and flat distance fog.
- Render at low resolution with linear upscale.

Do not:

- Do not use nearest filtering, dither or vertex wobble; that reads as `036`.
- Do not use hard two-band toon shading; that reads as `003`.
- Do not add glossy plastic with depth-of-field blur; that reads as `057`.
- Do not use crisp high-resolution textures.

## Nearest styles

- `036` PS1 low-poly wobble: textures here are smeared soft, geometry is steady and colours are bright; `036` has sharp square texels, jittering polygons and a dark, muddy, dithered image.
- `057` Toy-diorama tilt-shift: this style has angular low-polygon silhouettes with blurry stretched textures and a matte finish; `057` has smooth rounded glossy plastic forms and blurs the top and bottom of the frame like a photographed miniature.
- `003` Flat-shape ocean toon: surfaces here carry smooth gradients; `003` splits each surface into two flat tones with a razor-sharp boundary.

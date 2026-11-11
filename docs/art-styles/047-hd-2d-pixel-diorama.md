# HD-2D pixel diorama

Reference works: Octopath Traveler.

## References

- *Octopath Traveler* (2018), Square Enix and Acquire, video game. https://en.wikipedia.org/wiki/Octopath_Traveler
- *Triangle Strategy* (2022), Square Enix and Artdink, video game. https://en.wikipedia.org/wiki/Triangle_Strategy
- *Dragon Quest III HD-2D Remake* (2024), Square Enix and Artdink, video game. https://en.wikipedia.org/wiki/Dragon_Quest_III
- *Live A Live* (2022), Square Enix and Historia, video game. https://en.wikipedia.org/wiki/Live_A_Live
- *Final Fantasy VI* (1994), Square, video game. https://en.wikipedia.org/wiki/Final_Fantasy_VI

## Visual definition

- **Shape language and proportions:** 16-bit style pixel-art characters (about 24x40 px) as flat sprites standing in a 3D diorama built from blocky geometry covered with pixel-art textures.
- **Line and outline:** Sprites have a dark one-pixel outline. Environment has none.
- **Shading model:** Environment is lit with modern smooth lighting, shadows and point lights; sprites are evenly lit and receive scene tint.
- **Palette:** `#2b2a33` `#6b5b45` `#a8895c` `#3f6b4f` `#4a6fa5` `#e8c170` `#c44d3a` `#f4e9c9`. Earthy mid-tones with warm lamp light and cool shadow; richer than true 16-bit palettes.
- **Lighting:** Dramatic point lights (torches, windows), light shafts, bright specular sparkle on water.
- **Texture and surface:** Pixel-art textures with visible square texels on walls and ground; sprites unfiltered.
- **Atmosphere and post-processing:** Strong tilt-shift depth of field, bloom, vignette, particles (dust, embers, snow).
- **Camera and framing:** Fixed side-on or slightly raised view with a long lens and a narrow focus band.
- **UI and typography:** Dark semi-transparent panels with thin gold filigree borders and parchment-toned `#f4e9c9` windows; item icons are small pixel-art pictures. Headings and dialogue use an elegant book serif drawn crisp at full resolution, not pixelated. Damage numbers are large bold serif digits in white, with warm gold `#e8c170` for critical hits and red `#c44d3a` for weakness hits.
- **VFX and motion:** Spells combine pixel-sprite flares with modern glow: fire that blooms and lights the set, sparkling particles, light shafts, drifting embers. Sprites animate in a few snappy frames with held poses and quick hit flashes, while the camera drifts and zooms slowly.

## Fits

- **Genres:** `rpg`, `strategy`, `tower-defense`, `exploration`, `roguelike`
- **Moods:** nostalgic, wistful, epic
- **Settings:** medieval kingdoms, torch-lit towns, snowy mountain villages, castle battlefields

## Unity recipe

### Assets

Two kinds of asset. Characters are pixel-art sprite sheets of about 24x40 px with a dark one-pixel outline, in several facing directions, drawn or adapted from a CC0 pack; import with point filtering, no compression, a fixed pixels-per-unit value. The diorama is blocky 3D geometry built with ProBuilder's API or from simple modular packs, covered in pixel-art textures: repaint pack textures by downscaling to a fixed texel density (for example 16 or 32 texels per metre), remapping to the earthy palette and importing with point filtering.

### Materials

Environment: `Universal Render Pipeline/Lit` with the pixel textures, smoothness low, no normal maps or only blocky ones; this gives modern smooth lighting on square texels. Water uses Lit with high smoothness and a scrolling point-filtered normal for sparkle. Sprites need a custom shader, `Style/DioramaSprite`: a camera-facing quad with alpha clip that is evenly lit, sampling only ambient (`SampleSH`) and the main light colour without NdotL so the sprite takes the scene tint; it includes a `ShadowCaster` pass so sprites cast shadows onto the set, plus `DepthOnly` so Depth Of Field treats them correctly.

### Lighting and atmosphere

Dramatic local light: warm point lights at torches and windows with soft shadows, a dim cool directional light, and Forward+ for light counts. Bake Adaptive Probe Volumes for cool ambient fill. Light shafts are additive quads. Reflection probes for water. Soft shadows on, 3 cascades, 60 m. Light fog in a cool tint. SSAO on, medium.

### Post-processing

Full resolution, not a low-resolution target: the sprites are pixel art but the rendering is modern. Tilt-shift blur comes from Depth Of Field in Bokeh mode with a short focus range around the characters, viewed from a raised camera with a long lens. Bloom with a moderate threshold, Vignette 0.3, ACES or Neutral tonemapping, warm highlights and cool shadows through Split Toning. TAA is risky on point-filtered sprites; prefer SMAA.

### UI and effects

Dark semi-transparent panels with thin gold filigree borders and `#f4e9c9` parchment windows; item icons are small pixel pictures. Text is not pixelated: a book serif such as Cormorant Garamond or EB Garamond as an SDF font asset at full resolution. Damage numbers are large bold serif digits in white, `#e8c170` for critical hits, `#c44d3a` for weakness. Spells mix pixel-sprite flipbooks with HDR emission, a brief point light that lights the set, and particles of dust, embers or snow.

## Do / Do not

Do:

- Combine flat pixel sprites with lit 3D blocks.
- Blur foreground and background with tilt-shift.
- Add bloom, light shafts and particles.
- Keep all textures unfiltered.

Do not:

- Do not render at low resolution without modern lighting; that reads as `042` or `046`.
- Do not replace pixel art with smooth glossy toys; that reads as `057`.
- Do not use polygonal characters; that reads as `036`.
- Do not filter textures.

## Nearest styles

- `057` Toy-diorama tilt-shift: `057` is smooth, glossy plastic toys; this style has square-texel pixel textures on every surface and dark-outlined sprite characters.
- `042` NES 8-bit tile: `042` is flat and unlit with only a few colours; this style adds smooth lighting, shadows, glow and a rich range of colours.
- `046` Low-res sprite 2.5D shooter: `046` is darker, with sprites that have no outline and light that drops in steps; this style is brighter, with dark-outlined sprites, smooth light and bloom.

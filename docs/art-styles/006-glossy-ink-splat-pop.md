# Glossy ink-splat pop

Reference works: Splatoon.

## References

- *Splatoon* (2015), Nintendo EAD, video game. https://en.wikipedia.org/wiki/Splatoon_(video_game)
- *Splatoon 2* (2017), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Splatoon_2
- *Splatoon 3* (2022), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Splatoon_3
- *De Blob* (2008), Blue Tongue Entertainment, video game. https://en.wikipedia.org/wiki/De_Blob

## Visual definition

- **Shape language and proportions:** Stylised teen characters with large heads; urban props with rounded, toy-like simplification. Ink splats are thick, blobby pools with raised edges.
- **Line and outline:** No outlines.
- **Shading model:** Smooth PBR-like shading. Ink is glossy with sharp bright specular highlights; base surfaces are matte.
- **Palette:** `#f02d7d` `#19d719` `#603bff` `#ff8a00` `#1ad6c5` `#2b2b33` `#f5f5f0`. Two opposing neon ink colours (for example pink against green) covering neutral grey concrete and white.
- **Lighting:** Bright overcast-sun mix with a clear environment reflection in the ink.
- **Texture and surface:** Base surfaces have simple material detail (concrete speckle, painted metal). Ink has glitter flecks and a visible thickness.
- **Atmosphere and post-processing:** Light bloom on ink highlights; colours stay clean.
- **Camera and framing:** Third-person, slightly above, 35 mm equivalent.
- **UI and typography:** Sticker-like panels tilted off axis with rounded, wobbly edges, in the two ink colours on dark grey (`#2b2b33`) or white. Type is a chunky rounded display face with a hand-cut look, and icons are flat splat-shaped badges. Counters are big bold numerals that bounce when they change.
- **VFX and motion:** Ink flies as thick glossy blobs and droplets that land as splats with a raised rim; hits burst in the attacker's ink colour with glitter flecks. Animation is quick and bouncy, with squash and stretch on characters and wobble on ink.

## Fits

- **Genres:** `third-person-shooter`, `sports`, `platformer`, `top-down-shooter`, `puzzle`
- **Moods:** playful, energetic, upbeat
- **Settings:** city plaza, skate park, shopping district, rooftop arena

## Unity recipe

### Assets

Stylised urban packs with rounded, toy-like props and teen-proportioned characters. Keep the pack's PBR maps but simplify: flatten albedos to concrete grey and white, keep a light concrete speckle, set smoothness low. Ink is built from scratch: generate splat masks and a matching height map by script, and thick blob meshes (metaball-like lumps with a raised rim) in Blender background mode for pools and projectiles.

### Materials

Base surfaces use `Universal Render Pipeline/Lit` with low smoothness. Ink surfaces need a custom shader, for example `Style/InkCoat`, built on URP's PBR functions: fill `SurfaceData` and `InputData` and call `UniversalFragmentPBR`. A world-space splat mask (a render texture painted at runtime, sampled by world XZ) selects ink colour and sets smoothness to 0.95; derive a normal from the mask's height so the edge looks raised. Add glitter by thresholding a high-frequency noise against the view direction into emission. Include every Lit pass type: `UniversalForward`, `ShadowCaster`, `DepthOnly`, `DepthNormals`, plus `Meta` if baking. The two ink colours are global properties set with `Shader.SetGlobalColor` so teams can be swapped.

### Lighting and atmosphere

Bright directional sun with soft shadows mixed with a strong sky ambient. Reflection probes matter here: place baked probes with box projection so ink shows clear environment reflections. Four cascades, 100 m. SSAO on at low intensity. No fog.

### Post-processing

Neutral tonemapping keeps the neons clean; ACES would dull them. Bloom with threshold near 1.1 and low intensity so only ink highlights and glitter bloom. Small saturation lift. No grain, no vignette. MSAA 4x, HDR on.

### UI and effects

Use a chunky rounded display face such as Lilita One. Panels are sticker sprites with wobbly rounded edges, rotated off axis, in the two ink colours on `#2b2b33` or white; icons sit on splat-shaped badges. Counters bounce with a scale curve when they change. Ink shots are mesh particles (the blob mesh) with the ink shader, stretched along velocity, that spawn a splat stamp on collision; hits burst in the attacker's colour with small additive glitter sprites.

## Do / Do not

Do:

- Limit ink to two opposing hues per scene.
- Make ink clearly glossier than the base surface.
- Give ink pools a raised rounded rim.
- Cover large parts of the floor with ink and leave bare ground visible between the pools.

Do not:

- Do not add black outlines or flat bands; that reads as `004`.
- Do not use many unrelated hues; that reads as `013`.
- Do not make every surface hard glossy plastic with studs; that reads as `052`.
- Do not leave ink flat without specular.

## Nearest styles

- `013` Stylised hero PBR: this style lets two neon ink hues dominate neutral grey and white ground, with glossy ink on matte surfaces; `013` spreads many softer hues across the scene with an even material finish.
- `052` Brick toy: this style shows concrete speckle and painted metal on base surfaces and keeps gloss for the ink; `052` makes everything clean glossy plastic with studs and seams.
- `004` Graffiti street cel: this style has no outline and smooth shading with glossy highlights; `004` puts a black outline on every silhouette and shades in two flat tone steps.

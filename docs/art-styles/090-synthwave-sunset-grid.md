# Synthwave sunset grid

Reference works: Far Cry 3: Blood Dragon; Out Run.

## References

- *Far Cry 3: Blood Dragon* (2013), Ubisoft Montreal, video game. https://en.wikipedia.org/wiki/Far_Cry_3:_Blood_Dragon
- *Out Run* (1986), Sega AM2 (Yu Suzuki), arcade video game. https://en.wikipedia.org/wiki/Out_Run
- *Hotline Miami* (2012), Dennaton Games, video game. https://en.wikipedia.org/wiki/Hotline_Miami
- *Kung Fury* (2015), David Sandberg, live-action short film. https://en.wikipedia.org/wiki/Kung_Fury
- *Drive* (2011), Nicolas Winding Refn, live-action film. https://en.wikipedia.org/wiki/Drive_(2011_film)

## Visual definition

- **Shape language and proportions:** A flat plain covered by a perspective grid running to the horizon, a huge striped sun, jagged wireframe or flat mountains, palm tree silhouettes, a low wedge sports car, chrome lettering.
- **Line and outline:** No dark outline. Bright neon lines form the grid and edge the mountains.
- **Shading model:** Mostly unlit gradients. Chrome objects use a stylised horizon reflection (dark below, bright sky above with a sharp line).
- **Palette:** `#12002b` `#ff2fd1` `#19f0ff` `#ff9a1f` `#6a1bff` `#ffe14d` `#2a0a4a`. Deep purple-black ground and sky, hot magenta, cyan, orange-to-yellow sun gradient, violet.
- **Lighting:** Self-lit. The sun is a graphic disc, not a light source.
- **Texture and surface:** Grid lines, sun stripes (horizontal gaps that widen toward the bottom), star dots, scanlines.
- **Atmosphere and post-processing:** Bloom, scanlines, chromatic aberration, slight VHS noise and vignette.
- **Camera and framing:** Low, centred, looking down the grid at the sun; wide field of view with forward motion.
- **UI and typography:** Titles are chrome-gradient lettering with a sharp horizon line; panels are thin neon outlines in magenta and cyan on purple-black, and icons are simple neon line shapes. Body text is a wide italic sans or a neon-tube script. Counters are slanted arcade numerals, yellow for score and magenta for damage, under the scanlines.
- **VFX and motion:** Neon sparks, laser bolts with long glowing streaks, and explosions as flat rings in magenta and orange; a hit flashes one colour-split glitch frame. Motion is constant forward speed with grid lines rushing past, and characters move in snappy arcade poses.

## Fits

- **Genres:** `racing`, `fps`, `top-down-shooter`, `vehicle-combat`, `fighting`, `third-person-shooter`
- **Moods:** nostalgic, energetic, campy
- **Settings:** 1980s Miami, neon highway, retro-future wasteland

## Unity recipe

### Assets

A small fixed kit built from scratch by script: a flat plain with a perspective grid, a huge sun disc, jagged mountain ranges (wireframe or flat triangles with neon edges), palm tree silhouettes, a low wedge sports car, chrome lettering meshes. Store models are needed only for the car and palms; strip textures. Generate a star-dot texture and a chrome gradient ramp (dark ground band, sharp horizon line, bright sky gradient above).

### Materials

Mostly unlit and custom. `Style/SunsetGrid` for the ground: purple-black base with procedural anti-aliased magenta or cyan grid lines that scroll toward the camera, HDR emission. `Style/StripedSun`: a disc with a vertical orange-to-yellow gradient and horizontal gaps cut by `step` on a stripe function whose gap width grows toward the bottom. Sky: an unlit gradient dome from `#12002b` to violet and magenta at the horizon, with star dots. Mountains: flat dark fill with emissive edge lines from a barycentric or UV-border mask. Chrome: `Style/ChromeRamp`, which looks up the ramp texture by the reflected view direction's Y component, giving the stylised horizon reflection without any probe. Passes: `UniversalForward` and `DepthOnly`; no shadow passes.

### Lighting and atmosphere

Self-lit: no lights are needed and shadows are off. The sun is a graphic disc, not a light. Fog in deep purple (`#2a0a4a`), linear, so the grid fades at the horizon. No SSAO, GI or reflection probes.

### Post-processing

Bloom with threshold 0.9 and high intensity. Chromatic Aberration at 0.3 to 0.5. Vignette 0.3. A Full Screen Pass Renderer Feature after post-processing adds scanlines (darken alternate rows at a fixed pitch) and slight VHS noise: a thin horizontal jitter band that drifts upward and low-level chroma noise. A one-frame glitch on hits splits the colour channels horizontally. Neutral tonemapping, HDR on.

### UI and effects

Titles use the chrome ramp as a TextMeshPro face texture on a heavy italic display face such as Russo One or Monoton for neon-tube titles; a neon script such as Yellowtail for accents. Panels are thin neon outlines in magenta and cyan on purple-black. Counters are slanted arcade numerals, yellow for score, magenta for damage. Effects: neon sparks, laser bolts with long stretched additive streaks, explosions as flat expanding rings in magenta and orange. Keep constant forward speed with grid lines rushing past.

## Do / Do not

Do:

- Run a neon grid to the horizon.
- Place a large striped gradient sun at the centre.
- Use magenta, cyan and purple with bloom.
- Add scanlines and chromatic aberration.

Do not:

- Do not use only one or two line colours on pure black; that reads as `040` or `088`.
- Do not add rain, grime and realistic city detail; that reads as `089`.
- Do not use a naturalistic orange desert with teal sky; that reads as `033`.
- Do not use flat layered mountains without neon; that reads as `060`.

## Nearest styles

- `088` Neon grid cyberspace: this style has a bright gradient sky, a striped sun and several neon colours together; `088` is near-black with one or two line colours on solid glossy objects.
- `060` Layered flat-colour wilderness: this style has neon lines, bloom and hot magenta and cyan on a dark ground; `060` is a lighter picture of flat layered landscape shapes with no neon or glow.
- `040` Vector display glow: this style has filled gradients in the sky and sun; `040` is only glowing lines on black.

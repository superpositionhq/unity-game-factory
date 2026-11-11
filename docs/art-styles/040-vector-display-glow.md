# Vector display glow

Reference works: Asteroids; Battlezone.

## References

- *Asteroids* (1979), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Asteroids_(video_game)
- *Battlezone* (1980), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Battlezone_(1980_video_game)
- *Tempest* (1981), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Tempest_(video_game)
- *Star Wars* (1983), Atari, Inc., arcade video game. https://en.wikipedia.org/wiki/Star_Wars_(1983_video_game)
- *Vectrex* (1982), Smith Engineering, vector display game console. https://en.wikipedia.org/wiki/Vectrex

## Visual definition

- **Shape language and proportions:** Wireframe only. Objects are minimal edge sets: a tank is about 30 lines, a mountain range one polyline. No filled surfaces.
- **Line and outline:** Bright glowing lines of constant width on black. Line ends and corners are brighter dots where the beam dwells.
- **Shading model:** None. Brightness varies only per line (beam intensity).
- **Palette:** `#000000` `#39ff14` `#ffffff` `#00e5ff` `#ff2a2a` `#ffe600`. One phosphor colour (green or white) on black, or a few pure colours for colour vector monitors.
- **Lighting:** None.
- **Texture and surface:** None.
- **Atmosphere and post-processing:** Phosphor glow around lines, short persistence trails on motion, slight flicker.
- **Camera and framing:** First-person or top-down; perspective lines converge to a flat horizon.
- **UI and typography:** The UI is drawn with the same glowing strokes as the world: no panels or fills, only thin line brackets, a line crosshair and wireframe icons such as small ship outlines for lives. Type is a monospaced stroke face in capitals, built from straight segments. Scores are large segment numerals at the top in phosphor green `#39ff14` or white, with red `#ff2a2a` for warnings on colour displays.
- **VFX and motion:** A destroyed object breaks into its separate line segments, which fly apart, spin and fade; shots are bright dots and short dashes, and a big hit flashes the whole screen for a moment. Motion is smooth and rigid: objects drift and rotate with inertia and never deform.

## Fits

- **Genres:** `top-down-shooter`, `vehicle-combat`, `fps`, `racing`, `simulation`
- **Moods:** stark, tense, hypnotic
- **Settings:** deep space, wireframe battlefield, geometric tunnel, trench run

## Unity recipe

### Assets

Build everything from scratch as line sets; store models do not fit. An editor step creates each object as a `Mesh` with `MeshTopology.Lines`, or as quads generated along edges for controllable width: a tank is about 30 segments, a mountain range one polyline. Author edge lists by hand in code or extract feature edges (boundary and sharp edges above an angle) from simple models. Store per-vertex brightness in vertex colour. No textures.

### Materials

Write `Style/VectorBeam`, an unlit additive shader: `Blend One One`, `ZWrite Off`, `ZTest Always` or off so objects are see-through wireframes with no hidden-line removal. For constant-width lines, expand each segment into a camera-facing quad in the vertex stage using the neighbouring endpoint stored in a UV channel; the fragment stage shapes a soft-edged beam profile across the quad. Output HDR colour: phosphor green `#39ff14` or white at intensity 2 to 3, with brighter round dots at segment ends and corners (a second small quad per vertex) where the beam dwells. One pass, `UniversalForward` or `SRPDefaultUnlit`; no depth or shadow passes.

### Lighting and atmosphere

None. No lights, no shadows, no fog, no skybox: camera clear colour is pure black. Disable SSAO and depth texture.

### Post-processing

Bloom is the phosphor glow: threshold about 0.9, intensity 1.5 to 3, scatter 0.6, tinted slightly toward the beam colour. A custom ScriptableRendererFeature keeps a history texture across frames with the RenderGraph API: each frame it outputs `max(current, history * decay)` with decay around 0.8, giving short persistence trails on motion. A small random brightness flicker (2 to 3 percent) is applied in the same pass. Tonemapping Neutral, HDR on. MSAA 4x or 8x helps thin lines; render scale 1.

### UI and effects

UI uses the same strokes: thin line brackets, a line crosshair, wireframe ship icons for lives, no panels or fills. Use a single-stroke monospaced face; a segment-style or stroke-style font such as Major Mono Display works as a TextMeshPro asset, or build numerals as line meshes for an exact match. Scores are large at the top; `#ff2a2a` for warnings on colour displays. A destroyed object splits into its segments, each given a velocity and spin and faded over a second. Shots are bright dots and short dashes; big hits flash the screen briefly.

## Do / Do not

Do:

- Draw edges only, on pure black.
- Add glow and short persistence trails.
- Brighten vertices where lines meet.
- Hide back edges with a black occluder mesh.

Do not:

- Do not fill surfaces with dark colour and emissive trim; that reads as `088`.
- Do not add a gradient sunset and filled mountains; that reads as `090`.
- Do not draw white lines on blue with dimension marks; that reads as `062`.
- Do not use pixel-stepped raster lines at low resolution.

## Nearest styles

- `088` Neon grid cyberspace: only lines exist here, so objects are see-through wireframes; `088` has solid dark glossy surfaces that carry light strips and reflect their glow.
- `062` Blueprint technical drawing: this style is glowing lines on pure black; `062` is crisp white lines without glow on a blue paper ground, with dimension marks.
- `090` Synthwave sunset grid: this style uses one phosphor colour or a few pure line colours and fills nothing; `090` has a gradient sky, a large striped sun and magenta and cyan fills.

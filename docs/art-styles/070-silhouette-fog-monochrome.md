# Silhouette fog monochrome

Reference works: Limbo.

## References

- *Limbo* (2010), Playdead, video game. https://en.wikipedia.org/wiki/Limbo_(video_game)
- *Inside* (2016), Playdead, video game. https://en.wikipedia.org/wiki/Inside_(video_game)
- *Nosferatu* (1922), F. W. Murnau, silent film. https://en.wikipedia.org/wiki/Nosferatu

## Visual definition

- **Shape language and proportions:** A small child figure and simple hazards (spider legs, saws, crates, ropes) as solid black silhouettes. Forest, industrial and rooftop scenery in layered silhouette planes.
- **Line and outline:** No line. Foreground objects are solid black shapes.
- **Shading model:** None on the foreground. Background layers are flat greys that get lighter and blurrier with distance.
- **Palette:** `#000000` `#1c1c1c` `#5a5a5a` `#9a9a9a` `#d8d8d8` `#ffffff`. Greyscale only. The only pure white is the figure's eyes and a few light sources.
- **Lighting:** Back-lit fog: a soft bright area behind the scene; light shafts between trees.
- **Texture and surface:** Film grain and soft dust. No surface texture on silhouettes.
- **Atmosphere and post-processing:** Heavy vignette, grain, flicker, depth blur on near and far layers, soft glow in the light area.
- **Camera and framing:** Side-on, orthographic or long lens, with parallax layers.
- **UI and typography:** No HUD panels. Prompts are small soft-edged white text or a single white glyph in the fog. Type is a thin plain sans or a slightly worn light serif in white `#ffffff` or light grey `#d8d8d8`, with the same blur and flicker as the frame; counters, if any, are small white tally marks or numerals.
- **VFX and motion:** Dust motes, falling ash, water splashes and sparks appear as black or soft white specks; deaths are abrupt breaks of the silhouette with no colour. Motion is weighty and physical, with realistic ragdoll and rope swing, and long stillness broken by sudden lethal snaps.

## Fits

- **Genres:** `platformer`, `puzzle`, `survival-horror`, `stealth`, `exploration`, `soulslike`
- **Moods:** bleak, eerie, lonely
- **Settings:** dark forest, abandoned factory, rain-swept rooftops, flooded ruins

## Unity recipe

### Assets

Everything in the play plane is a silhouette, so models need a readable outline and nothing else: a small child figure, spider legs, saws, crates, ropes, trees, machinery, rooftops. Any pack works once materials are replaced by black. Build background planes as layered silhouettes at increasing depth. Ropes and ragdolls need real physics set-ups (joints, a rope of linked rigidbodies). Add two small emissive white eyes to the figure.

### Materials

Foreground and gameplay objects use `Universal Render Pipeline/Unlit`, pure black. Background layers use a second unlit material whose grey value is set per layer, lighter with distance (`#1c1c1c`, `#5a5a5a`, `#9a9a9a`, `#d8d8d8`). The fog backdrop is an unlit HDR gradient with a soft bright area. Light shafts between trees are soft additive quads in grey-white. Eyes and the few light sources are unlit white above the bloom threshold. No lighting functions, no shadow passes; keep `DepthOnly` so Depth Of Field has depth.

### Lighting and atmosphere

No lights and no shadows. Depth comes from layer grey values, optionally reinforced with `RenderSettings` linear fog in light grey so mid layers fade automatically (Unlit supports fog). No SSAO or probes. Side-on camera with slow drift.

### Post-processing

The frame treatment is heavy and is what separates this from a clean cut-out look. Depth Of Field in Bokeh mode focused on the play plane so near and far layers blur. Film Grain at high intensity. Vignette 0.5 to 0.6. Bloom with low threshold and high scatter for a soft glow in the light area. Color Adjustments saturation -100 as a guard. A small Full Screen Pass Renderer Feature after post-processing adds exposure flicker of a few percent at irregular intervals and drifting soft dust specks. Tonemapping Neutral. SMAA.

### UI and effects

No HUD panels. Prompts are small soft-edged white text or one white glyph in the fog: a font asset from a thin plain sans or a light worn serif such as Cormorant Light, with softness raised in the TextMeshPro material so it shares the frame's blur. Counters, if any, are tally marks. Particles are black or soft white specks: dust motes, ash, water splashes, sparks. Deaths break the silhouette into physics pieces with no colour. Use ragdoll and rope physics and long stillness.

## Do / Do not

Do:

- Render the play layer as solid black.
- Lighten and blur layers with distance.
- Add grain, flicker and a heavy vignette.
- Keep eyes and lamps as the only pure white.

Do not:

- Do not add a coloured glowing backdrop; that reads as `058`.
- Do not light surfaces with modelled grey gradients; that reads as `068`.
- Do not use hard two-value threshold with a colour accent; that reads as `069`.
- Do not add coloured glows and painted detail; that reads as `027`.

## Nearest styles

- `058` Shadow-puppet cut-out: `058` sets black cut-outs against a glowing coloured backdrop; this style has only grey fog behind them, with grain and blur and no colour.
- `068` Film noir hard light: `068` lights real surfaces, so brick, faces and wet streets show in greys; this style keeps every foreground object a solid black shape with no interior detail.
- `065` Flat-vector stage light: `065` has clean hard-edged flat shapes in blue-grey darkness with yellow light; this style is colourless, soft and grainy, with blurred fog layers and a paler background.

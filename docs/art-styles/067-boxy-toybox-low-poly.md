# Boxy toybox low-poly

Reference works: Katamari Damacy.

## References

- *Katamari Damacy* (2004), Namco, video game. https://en.wikipedia.org/wiki/Katamari_Damacy
- *We Love Katamari* (2005), Namco, video game. https://en.wikipedia.org/wiki/We_Love_Katamari
- *Noby Noby Boy* (2009), Namco Bandai Games (Keita Takahashi), video game. https://en.wikipedia.org/wiki/Noby_Noby_Boy
- *Wattam* (2019), Funomena (Keita Takahashi), video game. https://en.wikipedia.org/wiki/Wattam

## Visual definition

- **Shape language and proportions:** Everyday objects reduced to naive boxy models: a cow is a box with four box legs, a person is a rectangular block with a cylinder head, trees are a cone on a stick. Hundreds of small objects scattered densely.
- **Line and outline:** No outline.
- **Shading model:** Simple two- or three-step shading with little contrast. Objects look evenly lit.
- **Palette:** `#ff6fae` `#ffd400` `#3ec1ff` `#7be04a` `#ff8a1f` `#ffffff` `#8a4fff` `#5a3a2a`. Many bright candy colours at once: pink, yellow, sky blue, lime, orange, with white and brown.
- **Lighting:** Flat, bright, shadowless; small blob shadows only.
- **Texture and surface:** Simple flat decals: stripes, dots, checks, faces made of two dots and a line, product labels as plain rectangles.
- **Atmosphere and post-processing:** None. Rainbow or flat pastel backgrounds.
- **Camera and framing:** Low third-person behind a rolling ball, wide angle; scale changes from tabletop to city.
- **UI and typography:** Round bubbles, rainbow arcs and thick circular gauges in candy fills, with icons that are tiny boxy objects or faces made of two dots and a line. Text is a chunky rounded sans mixed with wobbly hand-drawn lettering, in white `#ffffff` or brown `#5a3a2a` on pink, yellow and sky blue; counters are big numerals that bounce when they change.
- **VFX and motion:** Flat stars, hearts, sparkles and plain puffs pop out on pickups and bumps, with no smoke or realistic debris. Animation is stiff and toy-like: objects wobble, hop and spin as whole pieces, characters waddle through a few rigid poses, and everything pops in with squash and stretch.

## Fits

- **Genres:** `puzzle`, `platformer`, `simulation`, `sports`, `racing`, `exploration`
- **Moods:** playful, silly, cheerful
- **Settings:** cluttered living room, suburban town, toy city, playground

## Unity recipe

### Assets

Naive boxy models, hundreds of them: a cow is a box with four box legs, a person a block with a cylinder head, a tree a cone on a stick. Generate the whole object library by script from boxes, cylinders and cones with slightly bevelled edges; this is faster and more consistent than adapting packs. Decals are simple textures drawn by script: stripes, dots, checks, faces of two dots and a line, plain-rectangle product labels. Scatter objects densely with a placement step.

### Materials

`Universal Render Pipeline/Simple Lit` with specular highlights off, or a tiny custom shader `Style/Toybox`: half-Lambert from `GetMainLight()` quantised to two or three steps with low contrast (for example 0.8, 0.9, 1.0), times `_BaseColor`, with a decal texture blended by alpha from a second UV set. No shadow receiving. Passes `UniversalForward` and `DepthOnly`. Use one material per candy colour with GPU instancing, and vary colour per instance through a `MaterialPropertyBlock` so hundreds of objects batch.

### Lighting and atmosphere

Flat, bright and shadowless: one directional light for the gentle step, shadows off in the URP asset, strong white flat ambient. Each object gets a small dark blob quad beneath it. No fog, SSAO or probes. Background is a flat pastel or a rainbow gradient drawn by a simple unlit sky shader.

### Post-processing

None. Tonemapping None so candy colours stay pure; no Bloom, Depth Of Field or vignette, and the whole frame stays sharp. MSAA 4x. HDR can be off.

### UI and effects

Round bubbles, rainbow arcs and thick circular gauges (radial-fill images) in candy fills; icons are tiny boxy objects or two-dot faces. Mix a chunky rounded sans such as Fredoka Bold with a wobbly hand face such as Gochi Hand or Chewy, white or `#5a3a2a` on pink, yellow and sky blue. Counters bounce when they change. Effects are flat sprites or flat meshes: stars, hearts, sparkles and plain puffs that pop out on pickups and bumps, no smoke or debris. Objects wobble, hop and spin as whole rigid pieces and pop in with a squash-and-stretch scale tween; characters waddle through a few rigid poses.

## Do / Do not

Do:

- Reduce every object to a few boxes and cylinders.
- Scatter objects densely.
- Use many bright colours with flat lighting.
- Use stripe, dot and simple-face decals.

Do not:

- Do not round and gloss the forms with tilt-shift blur; that reads as `057`.
- Do not use sharp light-and-shadow toon shading on smooth caricatured characters; that reads as `003`.
- Do not use irregular triangulated terrain; that reads as `066`.
- Do not limit colours to three primaries with geometric purity; that reads as `098`.

## Nearest styles

- `003` Flat-shape ocean toon: `003` has smooth curved caricature characters with crisp toon shadows in a sea-and-sky colour scheme; this style has crude boxy objects, almost no shadow and candy colours everywhere.
- `098` Bauhaus primary geometry: `098` uses pure circles, squares and triangles in red, yellow and blue with black and white, in sparse ordered layouts; this style crowds the frame with naive boxy objects in every candy colour.
- `057` Toy-diorama tilt-shift: `057` has rounded glossy toy forms with soft shading and a blurred top and bottom of frame, like a miniature photograph; this style is matte, boxy and sharp across the whole frame.

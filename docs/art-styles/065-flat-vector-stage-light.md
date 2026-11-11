# Flat-vector stage light

Reference works: Kentucky Route Zero.

## References

- *Kentucky Route Zero* (2013), Cardboard Computer, video game. https://en.wikipedia.org/wiki/Kentucky_Route_Zero
- *Nighthawks* (1942), Edward Hopper, oil painting. https://en.wikipedia.org/wiki/Nighthawks_(Hopper)
- *Night in the Woods* (2017), Infinite Fall, video game. https://en.wikipedia.org/wiki/Night_in_the_Woods
- *Oxenfree* (2016), Night School Studio, video game. https://en.wikipedia.org/wiki/Oxenfree

## Visual definition

- **Shape language and proportions:** Simple flat-faced geometry seen side-on like a stage set: buildings with one wall removed, long horizontal roads, thin poles and wires, small faceless figures built from a few polygons.
- **Line and outline:** No outline.
- **Shading model:** Flat colour per face. Light appears as hard-edged geometric shapes: cones from lamps, rectangles from doorways.
- **Palette:** `#0d1117` `#1f2a36` `#e8d9a8` `#3a6f7a` `#c2543c` `#56616e`. Near-black and deep blue-grey with a pale yellow light colour and one muted accent.
- **Lighting:** Night. Isolated practical lights cut clear shapes out of darkness; most of the frame is dark.
- **Texture and surface:** None. Pure flat vector fills.
- **Atmosphere and post-processing:** None, or a very faint glow on light shapes.
- **Camera and framing:** Side-on, distant, slow horizontal moves; long lens or orthographic. Subjects small with much negative space.
- **UI and typography:** Dialogue and menus are plain text on the dark ground with no frame, or inside a thin 1 px ruled box; icons are simple flat geometric shapes. Text is a small monospaced or plain grotesque sans in pale yellow `#e8d9a8`, with unselected choices in grey `#56616e` and highlights in teal `#3a6f7a` or rust `#c2543c`; numerals are plain and the same size as the text.
- **VFX and motion:** Few particles. Effects are flat shapes: a light cone that switches on, a rectangle of light that slides across a floor, flat dots for fireflies and dust. Motion is slow and theatrical, with gentle eases, sets that slide or rotate like stage flats, and figures that walk with simple unexaggerated steps.

## Fits

- **Genres:** `detective-mystery`, `exploration`, `puzzle`, `stealth`
- **Moods:** melancholic, quiet, eerie
- **Settings:** rural highway at night, small-town America, abandoned mine, roadside gas station

## Unity recipe

### Assets

Simple flat-faced geometry staged side-on: buildings with one wall removed, long horizontal roads, thin poles and wires, small faceless figures of a few polygons. Build it with ProBuilder's API or the Mesh API; store packs need all textures removed and small detail deleted. Light shapes are geometry too: cones under lamps and rectangles from doorways are authored as meshes or computed by the shader, never left to soft falloff.

### Materials

Write `Style/StageFlat`. `UniversalForward` outputs one flat colour per face in two states: unlit (near-black `#0d1117` or deep blue-grey `#1f2a36`) and lit (`#e8d9a8` tinted by the surface's own muted colour). The lit state is decided with a hard `step`: loop additional lights, and for spot lights test whether the point is inside the cone and not in shadow (`light.distanceAttenuation * light.shadowAttenuation > threshold`), ignoring NdotL falloff so the light shape has a clean geometric edge. Compile `_ADDITIONAL_LIGHTS` and `_ADDITIONAL_LIGHT_SHADOWS`. Passes `ShadowCaster`, `DepthOnly`. Visible light cones in air are transparent unlit meshes with a flat low-alpha yellow.

### Lighting and atmosphere

Night, with most of the frame dark. Isolated practical lights: spot lights with hard shadows at lamps, and box-shaped light through doorways made with a spot light and a rectangular cookie. Additional light shadows enabled in the URP asset, soft shadows off. No directional light, near-black ambient, no fog, no SSAO, no GI. Background flat `#0d1117`.

### Post-processing

None, or Bloom at very low intensity for a faint glow on light shapes. Tonemapping None. No grain, blur or fog effects: edges must stay clean and hard, which separates this from a grey fog look. MSAA 4x or 8x. Camera is orthographic or a long lens, side-on.

### UI and effects

Dialogue and menus are plain text on the dark ground with no frame, or inside a 1 px ruled box; icons are flat geometric shapes. Font asset from a small monospaced or plain grotesque face such as IBM Plex Mono or Space Mono, `#e8d9a8`; unselected choices `#56616e`, highlights `#3a6f7a` or `#c2543c`; numerals the same size as the text. Effects: lights switch on in one frame, a rectangle of light slides across a floor as a door opens, flat dots for fireflies and dust. Sets slide or rotate like stage flats with gentle eases.

## Do / Do not

Do:

- Draw light as hard-edged geometric shapes.
- Keep most of the frame dark and empty.
- Stage sets side-on with a wall removed.
- Keep figures small and featureless.

Do not:

- Do not use soft gradients and fog; that reads as `070`.
- Do not use bright graded sunset layers; that reads as `060`.
- Do not fill the frame with red and jagged shapes; that reads as `008`.
- Do not add outlines or texture.

## Nearest styles

- `070` Silhouette fog monochrome: `070` is pure greyscale with soft fog, blur and film grain; this style has blue-grey darkness, a yellow light colour and clean hard-edged shapes.
- `060` Layered flat-colour wilderness: `060` is a bright landscape of graded colour layers; this style is night, mostly near-black, with a few small lit shapes.
- `058` Shadow-puppet cut-out: `058` puts black cut-out figures in front of a glowing coloured screen that fills the frame; this style has no glowing backdrop, only isolated lamps and doorways that cut shapes out of the dark.

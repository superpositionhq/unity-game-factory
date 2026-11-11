# Expressionist painted set

Reference works: The Cabinet of Dr. Caligari.

## References

- *The Cabinet of Dr. Caligari* (1920), Robert Wiene (sets by Hermann Warm, Walter Reimann and Walter Rohrig), silent film. https://en.wikipedia.org/wiki/The_Cabinet_of_Dr._Caligari
- *Metropolis* (1927), Fritz Lang, silent film. https://en.wikipedia.org/wiki/Metropolis_(1927_film)
- *The Golem: How He Came into the World* (1920), Paul Wegener and Carl Boese, silent film. https://en.wikipedia.org/wiki/The_Golem:_How_He_Came_into_the_World
- *Vincent* (1982), Tim Burton, stop-motion short film. https://en.wikipedia.org/wiki/Vincent_(1982_film)

## Visual definition

- **Shape language and proportions:** Stage sets with no right angles: walls lean, doors are trapezoids, windows are jagged shards, chimneys and lamp posts bend, paths zig-zag. Flat scenery panels with forced perspective.
- **Line and outline:** Bold painted black lines on set surfaces: outlines of windows, spiky grass, radiating floor stripes.
- **Shading model:** Light and shadow are painted on the sets as hard-edged black and white shapes; real lighting is flat and frontal. Faces are white with dark eye make-up.
- **Palette:** `#0c0c0c` `#f1ead6` `#6b6b63` `#2f3a35` `#b5a878` `#3a2f2a`. Black, white and grey, optionally tinted per scene in one colour (sepia, green or blue) like tinted film stock.
- **Lighting:** Flat front light; the drama comes from painted shadow wedges and painted light pools.
- **Texture and surface:** Painted cloth flats and plaster with visible rough brush strokes; film scratches and flicker.
- **Atmosphere and post-processing:** Monochrome with a single tint, iris vignette, grain, flicker, low frame rate.
- **Camera and framing:** Static, frontal, theatrical framing; often an iris mask.
- **UI and typography:** Silent-film intertitle cards: black panels with a jagged hand-painted white border, text in a crooked, angular hand-lettered display face whose letters lean and vary in size. Counters use the same uneven painted numerals in bone white `#f1ead6`, icons are spiky painted silhouettes, and the whole UI takes the scene's single tint.
- **VFX and motion:** Effects are painted or theatrical: jagged white starburst shapes on impact, flat cut-out smoke, iris-in and iris-out transitions, film scratches and flicker. Characters move like stage actors at a low frame rate, creeping along walls with long held poses and sudden jerky gestures.

## Fits

- **Genres:** `survival-horror`, `detective-mystery`, `stealth`, `puzzle`, `exploration`
- **Moods:** uneasy, feverish, theatrical
- **Settings:** crooked hill town, asylum, travelling fairground, rooftops at night

## Unity recipe

### Assets

Build sets from scratch as painted stage flats: an editor step generates wall, door and window panels as skewed quads and trapezoids with no right angles, jagged window shards, bent chimneys and lamp posts, zig-zag paths, arranged with forced perspective. Paint their textures by script: rough brush-stroked plaster in greys, bold black outlines round windows, spiky grass, radiating floor stripes, and, most important, hard-edged painted shadow wedges and white light pools. Characters are ordinary rigged models with white faces and dark eye make-up painted into the face texture.

### Materials

Sets use `Universal Render Pipeline/Unlit` with the painted textures: light and shadow are paint, so the surface must not respond to real light. Characters use Simple Lit or a flat custom shader with very low contrast under frontal light, with `_ReceiveShadows` off. No real cast shadows on the sets. Keep textures at 2048 px, bilinear, so brush strokes show.

### Lighting and atmosphere

Flat front light only: one directional light from the camera direction for characters, shadows off in the URP asset, bright flat ambient. No fog, SSAO, GI or probes. Stage the camera frontally, as in a theatre.

### Post-processing

Monochrome with one tint: Color Adjustments saturation -100, then a colour filter per scene (sepia, green or blue) through a per-scene Volume. Film Grain high. An iris vignette: Vignette with high intensity, low smoothness and rounded on, so a dark circular mask closes the corners; animate its intensity for iris-in and iris-out transitions. A Full Screen Pass Renderer Feature after post-processing adds scratches and brightness flicker. Low frame rate: step character animation to 12 to 16 poses per second with manual `Animator.Update` ticks, and optionally hold the whole rendered frame with a history texture.

### UI and effects

Intertitle cards: black panels with a jagged hand-painted white border. Lettering from a crooked angular display face such as Butcherman or New Rocker, with per-character rotation and size variation applied through TextMeshPro vertex edits; numerals in `#f1ead6`. Icons are spiky painted silhouettes. The UI takes the scene tint. Effects are theatrical: jagged white starburst sprites on impact, flat cut-out smoke on quads. Actors creep along walls, hold poses and gesture abruptly.

## Do / Do not

Do:

- Lean and skew every wall and opening.
- Paint shadows and light shapes onto the sets.
- Keep real lighting flat and frontal.
- Tint the monochrome image with one colour.

Do not:

- Do not use real hard-light photography on normal architecture; that reads as `068`.
- Do not use 3D puppets with smooth shading and colour accents; that reads as `049`.
- Do not threshold to two values with a colour spot; that reads as `069`.
- Do not fragment objects into overlapping transparent planes; that reads as `078`.

## Nearest styles

- `068` Film noir hard light: this style paints its shadows and bold black lines onto crooked flat sets under flat front light; `068` photographs normal, upright architecture with real hard light, real cast shadows and no drawn lines.
- `049` Gothic stop-motion puppet: this style is tinted black and white with flat painted scenery and live actors in white make-up; `049` shows solid miniature puppets and sets in blue-violet with orange or green accents, lit by real stage light with smooth shading.
- `078` Analytic cubist facets: here objects stay whole, only leaning and skewed, with painted light and shadow shapes on them; `078` breaks each object into overlapping ochre-grey facets seen from several viewpoints.

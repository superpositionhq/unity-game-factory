# Graphite pencil sketch

Reference works: Take On Me (a-ha music video).

## References

- *Take On Me (music video)* (1985), Steve Barron (animation by Michael Patterson and Candace Reckinger), rotoscoped pencil animation. https://en.wikipedia.org/wiki/Take_On_Me
- *Hotel Dusk: Room 215* (2007), Cing, video game. https://en.wikipedia.org/wiki/Hotel_Dusk:_Room_215
- *Drawing Hands* (1948), M. C. Escher, lithograph. https://en.wikipedia.org/wiki/Drawing_Hands

## Visual definition

- **Shape language and proportions:** Observed, natural proportions drawn loosely. Forms are found with several overlapping searching lines rather than one clean contour.
- **Line and outline:** Grey graphite lines, 1 to 2 px, doubled or tripled along contours, with gaps and overshoot. Lines redraw slightly differently every few frames (boiling).
- **Shading model:** Three to five tone levels of diagonal pencil shading: light scribble, denser scribble, cross layer. Shading strokes are short and at a consistent hand angle.
- **Palette:** `#f7f5ef` `#4a4a4a` `#8c8c8c` `#c8c6c0` `#2e2e2e`. White paper and graphite greys. No black darker than soft pencil.
- **Lighting:** Simple single light so shading falls on one side.
- **Texture and surface:** Paper tooth showing through pencil; smudges; construction lines left in place.
- **Atmosphere and post-processing:** Line boil at 8 to 12 changes per second; paper texture.
- **Camera and framing:** Any; hand-held feel suits the look.
- **UI and typography:** UI looks drawn in a sketchbook: panels are loose hand-ruled pencil boxes with overshooting corners on white paper `#f7f5ef`, and icons are quick pencil doodles. Text is casual pencil handwriting, numbers are scribbled and circled or underlined for emphasis, and everything stays in graphite greys with selected items shaded darker.
- **VFX and motion:** Effects are drawn marks: scribbled dust clouds, speed lines, short radiating pencil dashes on impact and eraser smears for fades. Animation is rotoscoped, lifelike motion held on twos or threes, with every line boiling between drawings.

## Fits

- **Genres:** `detective-mystery`, `puzzle`, `exploration`, `racing`, `platformer`
- **Moods:** intimate, wistful, playful
- **Settings:** old roadside hotel, sketchbook pages, 1980s diner, city backstreets

## Unity recipe

### Assets

Natural, observed proportions: everyday objects, people, rooms, streets. Realistic or lightly stylised packs work, with colour textures removed. Leave construction marks in place: add a few guide lines and ellipses as extra line meshes on key props. Generate by script: a paper-tooth texture, three or four scribble-shading tiles of short diagonal strokes at one hand angle (about 45 degrees) in rising density, and three variants of each so they can be cycled for boiling.

### Materials

Write `Style/Pencil`. `UniversalForward` computes a tone from `GetMainLight(shadowCoord)` and quantises it to three to five levels; each level blends in a scribble tile sampled in screen space at a fixed angle, multiplied by the paper tooth so paper shows through. The darkest output is graphite `#2e2e2e`, never black. A global `_BoilFrame` integer, advanced 8 to 12 times per second by a script, switches the tile variant and offsets the UVs. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`. A smudge mask can grey the paper lightly near dark areas.

### Lighting and atmosphere

A simple single directional light with soft shadows so shading falls on one side. Ambient ignored. No fog, SSAO or probes. Background is paper `#f7f5ef`.

### Post-processing

The line pass carries the style. A Full Screen Pass Renderer Feature before post-processing, using depth and normals, draws grey 1 to 2 px contours two or three times: each copy samples the edge mask with a different noise-displaced offset (a few pixels), so lines are doubled, leave gaps and overshoot corners. The noise seed changes with `_BoilFrame`, which makes every line redraw slightly differently. A final pass multiplies the paper texture. Tonemapping None, no Bloom. Keep lines grey and soft-edged, unlike an ink look. SMAA.

### UI and effects

Sketchbook UI: loose hand-ruled pencil boxes with overshooting corners, pencil-doodle icons. Font asset from casual pencil handwriting such as Patrick Hand or Caveat, in graphite greys; numbers scribbled and circled or underlined for emphasis (a drawn ring sprite). Selected items are shaded darker with a scribble fill. Effects are drawn marks from flipbooks: scribbled dust clouds, speed lines, short radiating dashes on impact, and an eraser-smear wipe for fades. Hold character animation on twos or threes.

## Do / Do not

Do:

- Draw contours with two or three overlapping loose lines.
- Shade with short diagonal strokes at one hand angle.
- Keep the darkest value a soft grey.
- Re-seed line wobble several times per second.

Do not:

- Do not use pure black ink and precise hatching; that reads as `072`.
- Do not use dot screentone; that reads as `020`.
- Do not leave the frame nearly empty white with black splats; that reads as `074`.
- Do not use one clean constant-width contour; that reads as `011`.

## Nearest styles

- `072` Engraved crosshatch print: this style is soft grey pencil on white paper with loose, doubled contours and scribbled shading; `072` is pure black ink with firm contours and dense, precise hatching.
- `074` White void ink-splat: here every object is outlined and shaded in pencil; `074` leaves the world blank white with no lines and shows form only where black paint splats land.
- `020` Manga screentone monochrome: this style uses soft graphite greys and scribbled shading; `020` is strict black and white with clean inked lines and dot screens.

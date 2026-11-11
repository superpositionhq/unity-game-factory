# Blueprint technical drawing

Reference works: Cyanotype blueprints.

## References

- *Cyanotype process* (1842), John Herschel, photographic printing process. https://en.wikipedia.org/wiki/Cyanotype
- *Blueprint* (19th century), after John Herschel's cyanotype process, reprographic drawing process. https://en.wikipedia.org/wiki/Blueprint
- *Photographs of British Algae: Cyanotype Impressions* (1843), Anna Atkins, cyanotype book. https://en.wikipedia.org/wiki/Anna_Atkins
- *Vitruvian Man* (c. 1490), Leonardo da Vinci, pen and ink drawing. https://en.wikipedia.org/wiki/Vitruvian_Man

## Visual definition

- **Shape language and proportions:** Objects shown as technical drawings: precise edges, visible hidden lines, centre lines, construction circles. Mechanical and architectural subjects.
- **Line and outline:** White or pale blue lines of two weights (visible edges 2 px, hidden and construction lines 1 px dashed) on blue. No dark lines.
- **Shading model:** None. Surfaces are transparent or the flat blue ground; section cuts are hatched with thin diagonal white lines.
- **Palette:** `#0b3d91` `#1f5fbf` `#ffffff` `#bcd4f6` `#082a66`. Prussian blue ground with white line work; pale blue for secondary lines.
- **Lighting:** None.
- **Texture and surface:** Faint paper grain and uneven blue wash; a light grid; fold creases. Dimension lines with arrowheads and tick marks.
- **Atmosphere and post-processing:** Slight blur and bleed on lines, edge darkening of the sheet.
- **Camera and framing:** Orthographic: front, side, top or isometric projection.
- **UI and typography:** Panels are thin white ruled boxes like a drawing title block, with corner ticks and leader lines that point to objects; icons are single-weight white line symbols. Text is an all-caps single-stroke drafting hand or a monospaced technical sans in white `#ffffff`, with secondary labels in pale blue `#bcd4f6`; numbers appear as dimension call-outs with arrowheads and units.
- **VFX and motion:** Effects are line work: impacts are expanding construction circles with radiating tick marks, trails are dashed paths, and destroyed objects separate into an exploded view. Motion is precise and mechanical, with linear moves, rotations that snap in fixed steps and lines that draw themselves on.

## Fits

- **Genres:** `puzzle`, `strategy`, `tower-defense`, `simulation`, `stealth`
- **Moods:** precise, calm, cerebral
- **Settings:** engineering workshop, factory floor plan, machine interior, heist floor plan

## Unity recipe

### Assets

Mechanical and architectural models with precise edges; CAD-like packs or models built with ProBuilder's API. Textures are discarded. An editor step extracts feature edges (boundaries and creases above an angle) and builds a line mesh per object, plus construction geometry made from scratch: centre lines, construction circles, dimension lines with arrowheads and tick marks, leader lines. Generate a paper texture (grain, uneven blue wash, light grid, fold creases) and a diagonal hatch tile for section cuts.

### Materials

Surfaces are not shaded. Write `Style/BlueprintSurface`: a depth-only style material that writes depth (and `DepthNormals`) but outputs the paper colour or nothing in `UniversalForward`, so it can hide or reveal lines behind it. Lines use `Style/BlueprintLine`, an unlit shader that expands segments to a constant 2 px width; a second pass or second material draws the same lines with `ZTest Greater` at 1 px with a dash pattern from the segment's length coordinate, which gives dashed hidden lines. Section-cut faces use the hatch tile in screen space. Colours: white for visible edges, `#bcd4f6` for hidden and construction lines. No shadows.

### Lighting and atmosphere

None. No lights, shadows, fog or probes. The camera is orthographic and the clear colour is Prussian blue `#0b3d91`.

### Post-processing

One Full Screen Pass Renderer Feature after the scene: composite the paper texture (multiply the uneven wash and grid over the blue), apply a very small blur to the line layer to imitate bleed, and darken the sheet edges. No Bloom or glow: lines must look printed, not emitted. Tonemapping None. MSAA 8x or SMAA for crisp thin lines.

### UI and effects

Panels are thin white ruled boxes like a drawing title block, with corner ticks and leader lines pointing to objects; icons are single-weight line symbols. Font asset from a single-stroke drafting hand such as Architects Daughter in capitals or a monospaced technical sans such as Share Tech Mono, white with `#bcd4f6` for secondary labels. Numbers appear as dimension call-outs with units. Effects are line work: expanding construction circles with tick marks on impact, dashed trail paths, lines that draw on by animating a length cutoff, and destroyed objects separating along axes into an exploded view. Rotations snap in fixed steps.

## Do / Do not

Do:

- Draw white lines on a blue ground.
- Show hidden edges as dashed lines.
- Use orthographic projection with dimension lines.
- Hatch section cuts.

Do not:

- Do not use glowing lines on black; that reads as `040`.
- Do not fill surfaces with shaded colour.
- Do not add neon glow and a floor grid in perspective; that reads as `088`.
- Do not use dark lines on white paper; that reads as `073`.

## Nearest styles

- `040` Vector display glow: `040` draws glowing lines on a black screen; this style draws crisp white lines with no glow on a Prussian blue paper ground.
- `088` Neon grid cyberspace: `088` is a dark space in perspective with neon trim, a receding floor grid and bloom; this style is a flat blue sheet in orthographic view with plain white lines.
- `073` Graphite pencil sketch: `073` is grey pencil strokes on white paper; this style is the reverse, white lines on deep blue with no dark lines.

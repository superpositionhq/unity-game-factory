# Embroidered tapestry

Reference works: Bayeux Tapestry.

## References

- *Bayeux Tapestry* (1070s), Anglo-Norman embroiderers, wool embroidery on linen. https://en.wikipedia.org/wiki/Bayeux_Tapestry
- *The Lady and the Unicorn* (c. 1500), Flemish workshops, wool and silk tapestry. https://en.wikipedia.org/wiki/The_Lady_and_the_Unicorn
- *The Hunt of the Unicorn* (1495-1505), South Netherlandish workshops, wool and silk tapestry. https://en.wikipedia.org/wiki/The_Unicorn_Tapestries
- *Apocalypse Tapestry* (1377-1382), Nicolas Bataille workshop (after Jean Bondol), wool tapestry. https://en.wikipedia.org/wiki/Apocalypse_Tapestry

## Visual definition

- **Shape language and proportions:** Flat, frieze-like figures in profile or three-quarter view, with long limbs and simple gestures. Buildings, ships and trees are schematic symbols. No perspective; size shows importance.
- **Line and outline:** Every shape is outlined in dark stem stitch. Folds and features are single stitched lines.
- **Shading model:** None. Areas are filled with one thread colour laid in parallel stitches.
- **Palette:** `#d8c9a3` `#8a3b2a` `#2f4a5a` `#b58a2f` `#4f6b3a` `#3a2a22` `#c9a57a`. Natural linen ground with a few plant-dyed wools: terracotta, blue-green, old gold, olive, dark blue-black.
- **Lighting:** None in the image. Real light may rake across the raised thread.
- **Texture and surface:** Visible thread everywhere: parallel laid stitches in filled areas, couching lines across them, plain-weave linen showing between shapes.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Flat, frontal, wide strip format with decorative borders above and below.
- **UI and typography:** Panels are strips of bare linen with stitched borders of running animals, leaves and chevrons, like the tapestry margins, and icons are small embroidered emblems. Type is a hand-stitched Latin capital with uneven uncial letters in dark wool, like the captions above the Bayeux scenes. Numbers are stitched Roman numerals in terracotta or blue-black.
- **VFX and motion:** Effects are stitched symbols: arrows, flames, waves and stars appear as thread shapes sewn in stitch by stitch, and a hit pulls threads loose or leaves a frayed gap. Figures move through a few held poses with jerky limb swings and slide along the baseline.

## Fits

- **Genres:** `strategy`, `tower-defense`, `rpg`, `action-adventure`, `puzzle`
- **Moods:** solemn, archaic, wry
- **Settings:** Norman conquest, medieval court, castle siege, hunting forest

## Unity recipe

### Assets

Flat, frieze-like art: figures in profile or three-quarter view with long limbs, schematic buildings, ships and trees. Build scenes as flat layers or very shallow relief on a linen plane; no perspective, with size showing importance. Draw shapes as vector outlines by script, then run a stitch generator: fill each area with parallel laid stitches in one thread colour, add couching lines across them, and outline every shape in dark stem stitch. Output albedo, a thread normal map and a height map at 2048 px or more. Generate a plain-weave linen tile for the ground.

### Materials

`Universal Render Pipeline/Lit` or Simple Lit with the thread normal map, smoothness near 0.15 and no metallic: the image itself has no shading, and real light only rakes across raised thread. A custom shader is useful for the sewing-in effect: `Style/Stitch` adds a `_Progress` value compared against a per-stitch order stored in a texture channel, clipping stitches not yet sewn; it needs `UniversalForward`, `DepthOnly` and `ShadowCaster` only if relief shadows are wanted. Colours stay within the five wool hues on linen `#d8c9a3`.

### Lighting and atmosphere

A single soft directional light at a low grazing angle to the cloth so thread relief shows; flat warm ambient. No cast shadows across the picture beyond thread self-shadow from the normal map. No fog, no SSAO, no probes. Use an orthographic camera facing the cloth; scroll sideways along the frieze.

### Post-processing

None. Tonemapping None or Neutral, no Bloom, no Depth Of Field, no vignette. MSAA 4x; render scale 1 so individual threads resolve.

### UI and effects

Panels are strips of bare linen with stitched borders of running animals, leaves and chevrons; icons are small embroidered emblems, all made with the stitch generator. Lettering is stitched uneven capitals: use an uncial face such as Uncial Antiqua and pass titles through the stitch generator; small text uses the font asset in dark wool colour `#3a2a22`. Numbers are Roman numerals in terracotta or blue-black. Effects are stitched symbols that sew in by animating `_Progress`: arrows, flames, waves, stars. A hit removes stitches in a frayed patch and spawns loose thread strands. Figures swap between a few held poses and slide along the baseline.

## Do / Do not

Do:

- Outline every shape with dark stitches.
- Fill areas with parallel laid stitches.
- Keep figures flat on one baseline without perspective.
- Leave linen ground visible.

Do not:

- Do not build soft 3D stuffed forms in bright pastels; that reads as `051`.
- Do not use smooth flat ink colour without thread texture; that reads as `082`.
- Do not use dense interlaced ornament and gold; that reads as `086`.
- Do not add shading or perspective.

## Nearest styles

- `051` Felt and yarn: this style is a flat stitched picture on bare linen in muted wool colours; `051` builds plump, softly shaded stuffed forms in bright pastels.
- `086` Insular illuminated manuscript: here a few muted wools sit on plain linen that stays open between sparse figures; `086` fills the page with rich colour, gold and dense knotwork.
- `082` Ukiyo-e woodblock: every filled area here shows parallel thread and the linen weave; `082` has smooth flat printed colour on paper with only a faint wood grain, and fine flowing black line.

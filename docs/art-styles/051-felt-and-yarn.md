# Felt and yarn

Reference works: Kirby's Epic Yarn.

## References

- *Kirby's Epic Yarn* (2010), Good-Feel, video game. https://en.wikipedia.org/wiki/Kirby's_Epic_Yarn
- *Yoshi's Woolly World* (2015), Good-Feel, video game. https://en.wikipedia.org/wiki/Yoshi's_Woolly_World
- *Unravel* (2016), Coldwood Interactive, video game. https://en.wikipedia.org/wiki/Unravel_(video_game)
- *LittleBigPlanet* (2008), Media Molecule, video game. https://en.wikipedia.org/wiki/LittleBigPlanet_(2008_video_game)

## Visual definition

- **Shape language and proportions:** Soft, stuffed, slightly lumpy forms. Characters are yarn outlines or plush shapes; scenery is fabric patches, buttons, zips and pompoms.
- **Line and outline:** Visible stitching: dashed thread lines along every seam and patch border, in a darker or contrasting thread.
- **Shading model:** Smooth and very soft; fabric fuzz brightens grazing angles.
- **Palette:** `#f48fb1` `#81d4fa` `#fff59d` `#a5d6a7` `#ce93d8` `#ffab91` `#f5f0e6`. Bright nursery pastels: pink, sky blue, lemon, mint, lilac, on a cream fabric ground.
- **Lighting:** Soft, even craft-table lighting with gentle contact shadows.
- **Texture and surface:** Dense fibre detail: knit loops, felt fuzz, woven cloth grain, twisted yarn strands.
- **Atmosphere and post-processing:** Mild depth of field; nothing else.
- **Camera and framing:** Side-on or slightly raised, close enough to read the fabric weave.
- **UI and typography:** Panels are felt patches with dashed stitch borders, buttons are sewn-on buttons and icons are appliqué shapes or embroidered badges. Type is a soft rounded sans that looks stitched in yarn or cut from felt. Counters are chunky rounded numerals in pink, sky blue and lemon on cream fabric.
- **VFX and motion:** Particles are yarn puffs, loose threads, pompoms and popping buttons, never sparks or smoke. A hit unravels a strand or bursts a seam with a puff of stuffing. Motion is bouncy with squash and stretch, and yarn outlines whip loose and re-form into new shapes.

## Fits

- **Genres:** `platformer`, `puzzle`, `exploration`, `action-adventure`
- **Moods:** cosy, playful, gentle
- **Settings:** craft-table world, patchwork countryside, toy bedroom, knitted seaside

## Unity recipe

### Assets

Soft, stuffed, slightly lumpy forms: plush characters, fabric-patch scenery, buttons, zips, pompoms. Inflate and round store models in Blender background mode and add seams. Generate fabric maps by script or take CC0 fabric scans: knit loops, felt, woven cloth and twisted yarn as albedo plus normal, tiled finely. Stitching is a dashed thread texture laid along seams and patch borders through a second UV set or as thin tube meshes built along edge loops. Yarn outlines are tube meshes swept along curves.

### Materials

Fabric needs a fuzz term that plain Lit lacks. Write `Style/Felt`: fill `SurfaceData` with the fabric albedo and normal, call `UniversalFragmentPBR` with smoothness near 0, then add a sheen: `pow(1 - NdotV, 3)` times a pale tint of the base colour, scaled by the main light and ambient, so grazing angles brighten. Wrap the diffuse term slightly for softness. Include the full Lit pass set (`UniversalForward`, `ShadowCaster`, `DepthOnly`, `DepthNormals`, `Meta`). For close-ups add short shell layers: a few extra draws of the mesh pushed along the normal with an alpha-clipped fibre noise, done with extra materials on the renderer. Buttons use ordinary Lit plastic.

### Lighting and atmosphere

Soft, even craft-table light: a broad directional light with very soft shadows at reduced strength, strong flat ambient in warm white. Short shadow distance. SSAO on, gentle, small radius. No fog. Background is cream fabric (`#f5f0e6`) with its own weave.

### Post-processing

Mild Depth Of Field in Bokeh mode and nothing else of note: Neutral tonemapping, no Bloom, no grain, no vignette. SMAA; keep render scale at 1 so fibre detail holds.

### UI and effects

Panels are felt patches with dashed stitch borders, buttons are sewn-on buttons, icons are appliqué shapes or embroidered badges, all as sprites rendered from the 3D materials. Font asset from a soft rounded sans such as Baloo 2 or Fredoka; add a dashed-stitch outline sprite behind headings. Chunky numerals in pink, sky blue and lemon on cream. Particles are mesh puffs of yarn, loose threads (short `TrailRenderer` strands with the yarn texture), pompoms and popping buttons; never sparks or smoke. A hit unravels a strand or bursts a seam with white stuffing tufts.

## Do / Do not

Do:

- Put a stitch line on every seam.
- Use sheen for fabric fuzz.
- Give every surface a knit, felt or weave pattern.
- Inflate forms like stuffed cushions.

Do not:

- Do not leave surfaces smooth; that reads as `048` or `057`.
- Do not flatten the scene into a long band of stitched figures on linen; that reads as `056`.
- Do not use flat paper sheets; that reads as `050`.
- Do not use hard plastic gloss.

## Nearest styles

- `056` Embroidered tapestry: this style builds plump, softly shaded stuffed forms in bright nursery pastels; `056` is a flat stitched picture on bare linen in muted plant-dyed wools, with no shading or depth.
- `048` Claymation: every surface here shows knit loops, felt fuzz and dashed stitch lines; `048` is smooth matte clay with thumb marks and no stitching.
- `050` Papercraft: forms here are inflated cushions covered in thick fuzzy fibre; `050` is built from flat folded paper sheets with crisp creases and only a faint paper grain.

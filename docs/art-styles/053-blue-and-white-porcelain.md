# Blue-and-white glazed porcelain

Reference works: Jingdezhen porcelain; Delftware.

## References

- *The David Vases* (1351), Jingdezhen kilns, Yuan dynasty, blue-and-white porcelain. https://en.wikipedia.org/wiki/David_Vases
- *Delftware* (17th century), Delft potteries, tin-glazed earthenware tradition. https://en.wikipedia.org/wiki/Delftware
- *Willow pattern* (c. 1790), English potteries (attributed to Thomas Minton), transfer-printed ceramic design. https://en.wikipedia.org/wiki/Willow_pattern

## Visual definition

- **Shape language and proportions:** Wheel-thrown forms: vases, jars, bowls, plates, tiles and figurines with smooth continuous curves and thickened rims and feet. Whole scenes are made of the same glazed ceramic.
- **Line and outline:** No outline on the forms. The decoration contains painted cobalt contour lines.
- **Shading model:** Smooth, glossy glaze with sharp specular highlights and soft reflections.
- **Palette:** `#fbfcfa` `#1a3a8a` `#2f5fc4` `#8fa9dc` `#dfe6ee` `#0f2460`. White glaze and cobalt blue only, the blue ranging from pale wash to nearly black-blue.
- **Lighting:** Soft museum or daylight setting with clear window-like reflections.
- **Texture and surface:** Hand-painted cobalt decoration: scrolling vines, lotus and peony, wave and lappet borders, cloud bands, landscapes in panels. Brush washes with uneven density; faint glaze pooling and pinholes.
- **Atmosphere and post-processing:** None, or slight depth of field.
- **Camera and framing:** Product-style three-quarter view, 50 to 85 mm equivalent.
- **UI and typography:** Panels are white glazed plaques or tiles framed with cobalt wave, lappet or scroll borders, and icons are small brush-painted motifs in round medallions. Type is brush-painted lettering with thick and thin strokes, in dark cobalt on white. Numbers are brush-drawn numerals, with pale blue wash for inactive states.
- **VFX and motion:** Hits craze the glaze with fine dark cracks and break objects into curved white shards, each with a piece of blue painting on it. Particles are cobalt ink blooms, brush-stroke swirls and painted clouds that spread like wash on glaze. Bodies are rigid ceramic that glides, spins and rocks, never bends.

## Fits

- **Genres:** `puzzle`, `exploration`, `strategy`, `platformer`
- **Moods:** serene, delicate, contemplative
- **Settings:** imperial China, Dutch canal town, tea house, willow garden

## Unity recipe

### Assets

Wheel-thrown forms: build vases, jars, bowls, plates, tiles and figurines as lathe meshes (a profile curve revolved by script) with thickened rims and feet. Scenery uses the same ceramic. Store models can be used if smooth and closed; remove their textures. The decoration is the main work: generate cobalt motifs by script (scrolling vines, lotus and peony, wave and lappet borders, cloud bands, panelled landscapes) as greyscale brush-density maps with uneven wash, mapped in cylindrical UVs so borders ring the vessel. 2048 px, bilinear.

### Materials

A glaze shader built on PBR: `Style/Porcelain` fills `SurfaceData` and calls `UniversalFragmentPBR`. Albedo is white glaze `#fbfcfa` lerped to cobalt by the decoration map through a three-stop ramp (`#8fa9dc` pale wash, `#2f5fc4`, `#0f2460` at full density); smoothness 0.9 everywhere since the paint lies under the glaze; a faint low-frequency normal for glaze pooling and tiny pinholes. Add a soft wrap to the diffuse for the slight translucency of porcelain. Standard Lit pass set. `Universal Render Pipeline/Complex Lit` with clear coat is an alternative that needs no custom code. Crack overlays blend in through a mask property.

### Lighting and atmosphere

Soft museum or daylight setting: a soft directional key, bright neutral ambient, and above all a reflection probe showing window-like bright rectangles so highlights read as windows. Build a small emissive window set and bake the probe, or use a studio HDRI. Soft shadows, short distance. SSAO light. No fog.

### Post-processing

Nearly none: Neutral tonemapping, optional slight Depth Of Field. No Bloom, grain or vignette. Check that no warm cast enters the whites: White Balance neutral. MSAA 4x.

### UI and effects

Panels are white glazed plaques or tiles with cobalt wave, lappet or scroll borders as 9-sliced sprites; icons are brush motifs in round medallions. Font asset from a brush face with thick and thin strokes such as Yuji Syuku or Kaushan Script, dark cobalt on white; pale blue wash for inactive states. Hits blend in a crack mask, then break objects into pre-fractured curved shards that keep their UVs, so each carries part of the painting. Particles are cobalt ink blooms that spread and fade, and brush-stroke swirls. Bodies glide, spin and rock; nothing bends.

## Do / Do not

Do:

- Use only white and cobalt blue.
- Organise decoration in horizontal bands with borders.
- Make the glaze glossy with clear reflections.
- Round every edge as if glazed.

Do not:

- Do not add other colours or gold; that reads as `100` or `055`.
- Do not use matte, unglazed surfaces.
- Do not use geometric star tiling; that reads as `100`.
- Do not leave the white undecorated; that reads as `091`.

## Nearest styles

- `100` Islamic geometric tile: this style has only cobalt on white, with freely brushed vines, flowers and landscapes on curved vessels; `100` uses several glaze colours in strict repeating star-and-polygon tiling that covers flat walls.
- `091` Clinical white space-age: white surfaces here are covered in painted cobalt decoration; `091` leaves its white surfaces plain and undecorated.
- `055` Mosaic tessera: this style is one continuous glossy glaze in blue and white; `055` is thousands of small tiles in many colours with dark grout between them.

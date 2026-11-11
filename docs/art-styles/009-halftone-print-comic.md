# Halftone print comic

Reference works: Spider-Man: Into the Spider-Verse.

## References

- *Spider-Man: Into the Spider-Verse* (2018), Sony Pictures Animation, animated film. https://en.wikipedia.org/wiki/Spider-Man:_Into_the_Spider-Verse
- *Spider-Man: Across the Spider-Verse* (2023), Sony Pictures Animation, animated film. https://en.wikipedia.org/wiki/Spider-Man:_Across_the_Spider-Verse
- *The Mitchells vs. the Machines* (2021), Sony Pictures Animation, animated film. https://en.wikipedia.org/wiki/The_Mitchells_vs._the_Machines
- *Marvel's Spider-Man: Miles Morales* (2020), Insomniac Games, video game. https://en.wikipedia.org/wiki/Marvel's_Spider-Man:_Miles_Morales

## Visual definition

- **Shape language and proportions:** Semi-realistic 3D forms with slightly stylised proportions. City geometry is dense and angular.
- **Line and outline:** Selective ink: drawn lines on key contours and on faces, not on every edge. Line weight varies.
- **Shading model:** Two or three bands where the midtone is rendered with halftone dots and the shadow with parallel hatch lines.
- **Palette:** `#e23636` `#1b1b3a` `#25c4f2` `#ff4fa3` `#f7d038` `#7b3fe4` `#f2f2f2`. Saturated magenta, cyan, yellow and red over deep blue-violet night tones.
- **Lighting:** Strong coloured key and opposite coloured rim (for example pink and cyan).
- **Texture and surface:** Print artefacts everywhere: Ben-Day dots, line screens, and colour layers printed slightly out of register.
- **Atmosphere and post-processing:** Chromatic offset that grows away from the focus point in place of lens blur; bloom rendered as dot patterns; occasional graphic bursts.
- **Camera and framing:** Dynamic, tilted, wide angle; strong foreshortening.
- **UI and typography:** Panels are comic caption boxes and speech balloons: yellow (`#f7d038`) or white boxes with a thin black border and a slightly offset colour layer behind. Type is comic hand-lettering in bold italic capitals. Hit words and numbers are large outlined display letters filled with dots, in magenta, cyan and yellow.
- **VFX and motion:** Impacts show drawn burst shapes, action lines, lettered sound effects and a brief split of the colour layers. Characters animate on twos with crisp held poses against smooth camera motion; glows and sparks break up into dot patterns.

## Fits

- **Genres:** `action-adventure`, `fighting`, `hack-and-slash`, `platformer`, `third-person-shooter`
- **Moods:** energetic, vibrant, youthful
- **Settings:** New York City at night, neon rooftops, subway, glitching multiverse

## Unity recipe

### Assets

Semi-realistic city and character packs with dense angular geometry work well; keep their 3D form. Remove smoothness and metallic maps, keep albedo simplified to palette flats, and keep normal maps only at reduced strength so the bands follow the form. Generate by script: a Ben-Day dot tile, a parallel line-screen tile and burst shapes. Ink lines on faces are painted into the face texture by the editor step, not left to an edge detector.

### Materials

Write `Style/HalftonePrint`. `UniversalForward` reads `GetMainLight(shadowCoord)` plus one opposite coloured rim light from the additional-light loop. Split NdotL into three zones: lit is flat colour, the midtone is flat colour multiplied by screen-space dots whose radius grows toward shadow (rotate the grid 45 degrees), the shadow zone is deep blue-violet with parallel hatch lines. Give the rim a second dot screen in its own colour. Passes: `ShadowCaster`, `DepthOnly`, `DepthNormals`. No hull outline; selective lines come from post.

### Lighting and atmosphere

Two realtime lights with strong complementary colours, for example a pink key and a cyan rim, hard shadows. Dark blue-violet flat ambient. No fog, no SSAO. Emissive signs feed the bloom dot effect.

### Post-processing

Chain three fullscreen passes with the RenderGraph API. First, before post-processing, an edge pass using depth and normals with a high threshold so only key contours get ink, with thickness varied by depth. Second, Bloom from the Volume profile at moderate intensity. Third, after post-processing, a print pass: it multiplies bright bloom regions by a dot pattern, then offsets the red and blue channels in opposite directions by an amount that grows with distance from a focus point passed from gameplay (this replaces Depth Of Field), and adds a faint paper tint. Tonemapping Neutral, HDR on, SMAA.

### UI and effects

Caption boxes and speech balloons: yellow (`#f7d038`) or white sprites with a thin black border and a duplicate colour layer offset a few pixels behind. Use a comic lettering face such as Bangers or Comic Neue Bold Italic in capitals. Hit words are large outlined TextMeshPro letters with a dot-pattern face texture. Impact effects are sprite bursts, action lines and lettered sound words; push the channel offset up for a few frames on each hit. Step character animation to twos while the camera stays smooth.

## Do / Do not

Do:

- Render midtones with dots and shadows with lines.
- Offset colour channels more with distance from the focus plane.
- Use complementary key and rim colours.
- Keep some contours unlined.

Do not:

- Do not use large uniform dots with thick outlines and primaries only; that reads as `081`.
- Do not replace screens with hand hatching and full outlines; that reads as `001`.
- Do not use Gaussian depth of field.
- Do not drop colour for black and white screens; that reads as `020`.

## Nearest styles

- `081` Ben-Day pop art: this style draws lines only on key contours and puts small dots in the midtones of shaded 3D forms, in many colours; `081` puts a thick outline around every form and fills flat areas with large uniform dots in a few primaries.
- `001` Ink-outline comic cel: this style leaves some contours unlined and uses vivid magenta, cyan and yellow with dot and line screens; `001` inks every silhouette, hatches by hand and uses dusty earth colours.
- `017` Neon megacity 1980s anime: this style is brighter and covers the frame with print dots, line screens and colour offset; `017` is darker, with a clean thin line and detail painted by hand.

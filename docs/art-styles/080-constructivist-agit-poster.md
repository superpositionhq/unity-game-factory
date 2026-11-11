# Constructivist agit poster

Reference works: El Lissitzky; Rodchenko.

## References

- *Beat the Whites with the Red Wedge* (1919), El Lissitzky, lithographic poster. https://en.wikipedia.org/wiki/Beat_the_Whites_with_the_Red_Wedge
- *Books (Please)! In All Branches of Knowledge* (1924), Alexander Rodchenko, poster. https://en.wikipedia.org/wiki/Alexander_Rodchenko
- *Monument to the Third International* (1920), Vladimir Tatlin, architectural model. https://en.wikipedia.org/wiki/Tatlin's_Tower
- *Black Square* (1915), Kazimir Malevich, oil painting. https://en.wikipedia.org/wiki/Black_Square
- *Battleship Potemkin* (1925), Sergei Eisenstein, silent film. https://en.wikipedia.org/wiki/Battleship_Potemkin

## Visual definition

- **Shape language and proportions:** Pure geometric elements in dynamic diagonal arrangements: wedges, circles, bars, arcs, megaphone cones, spiral towers and scaffolds. Compositions thrust along one strong diagonal.
- **Line and outline:** Thin ruled black lines and arcs as construction elements. No outline around colour shapes.
- **Shading model:** None. Flat ink. Photographic elements appear as grey halftone cut-outs.
- **Palette:** `#d7261e` `#111111` `#efe6d0` `#8a8a8a` `#f4f0e4`. Red, black and unbleached paper, with grey. No other colours.
- **Lighting:** None.
- **Texture and surface:** Print texture: slightly uneven ink coverage, paper fibres and yellowing, coarse halftone dots inside photomontage pieces, slight misregistration.
- **Atmosphere and post-processing:** Paper overlay; optional 1 px offset of the red plate.
- **Camera and framing:** Flat poster view, or steep diagonal low angle on 3D structures.
- **UI and typography:** UI is poster layout: solid red `#d7261e` and black `#111111` bars, wedges and circles on unbleached paper `#efe6d0`, often set on a diagonal, with thin ruled lines. Text is a heavy condensed all-capitals grotesque sans, set large and sometimes rotated to follow the diagonal; numbers are big block numerals in red or black, and icons are flat geometric pictograms.
- **VFX and motion:** Effects are flat graphic shapes: red wedges that stab in on impact, expanding black rings, radiating ruled lines and megaphone-style cones. Motion is fast and mechanical along diagonals, with hard cuts, snap zooms and stamped-on shapes in the manner of Eisenstein's montage; photomontage pieces move as stiff cut-outs.

## Fits

- **Genres:** `strategy`, `tower-defense`, `top-down-shooter`, `vehicle-combat`, `fighting`, `platformer`
- **Moods:** urgent, militant, bold
- **Settings:** revolutionary city, factory floor, battleship harbour, rally square

## Unity recipe

### Assets

Pure geometric elements built by script: wedges, circles, bars, arcs, megaphone cones, spiral towers, scaffolds. Arrange every scene along one strong diagonal, rotating the layout 20 to 35 degrees. Photomontage pieces are the one use for realistic assets: render characters, machines or crowds from 3D models to greyscale cut-out sprites with an editor step camera, with hard cut edges. Thin ruled lines and arcs are line meshes. Generate a paper texture with fibres and yellowing and an uneven ink-coverage noise.

### Materials

Colour shapes use `Universal Render Pipeline/Unlit` in red `#d7261e` or black `#111111`, with no outline. A small custom unlit shader, `Style/AgitInk`, multiplies the ink-coverage noise so flats are slightly uneven and lets paper show through at low coverage. Photomontage sprites use a shader that converts the sprite to grey and then to coarse halftone dots (screen-space grid, dot radius from luminance) in black on paper. No lighting functions and no shadow passes.

### Lighting and atmosphere

None. No lights, shadows, fog, SSAO or probes. Orthographic camera; the clear colour is unbleached paper `#efe6d0`. For 3D play spaces, keep an orthographic or long-lens view so shapes read as flat print.

### Post-processing

One Full Screen Pass Renderer Feature after post-processing: multiply the paper texture, and offset the red plate by 1 px by sampling the red-ink mask (pixels close to the red hue) at a shifted position, which gives slight misregistration. Tonemapping None. No Bloom, grain overlays beyond paper, or blur. MSAA 8x for ruled edges.

### UI and effects

The UI is poster layout: solid red and black bars, wedges and circles on paper, set on the diagonal with thin ruled lines. Font asset from a heavy condensed grotesque in capitals such as Anton, Oswald Bold or Bebas Neue, set large and sometimes rotated to follow the diagonal; big block numerals in red or black; flat geometric pictograms. Effects are stamped shapes: red wedges that stab in on impact, expanding black rings, radiating ruled lines, megaphone cones. Use hard cuts between shots, keep zooms short, and move montage pieces as stiff cut-outs with linear motion.

## Do / Do not

Do:

- Compose along one strong diagonal.
- Use red, black and paper only.
- Use ruled geometric wedges, circles and bars.
- Include a halftone photomontage element.

Do not:

- Do not use hand-cut crooked shapes with orange or blue fields; that reads as `064`.
- Do not restrict to horizontals and verticals with yellow and blue; that reads as `079`.
- Do not darken the frame with jagged anime shapes; that reads as `008`.
- Do not use balanced primary solids; that reads as `098`.

## Nearest styles

- `064` Mid-century cut-paper poster: this style places ruled, exact wedges, circles and bars in red and black on bare paper; `064` fills the frame with a strong orange, red or blue field and crooked scissor-cut shapes.
- `008` Red-black pop-punk graphic cel: this style is a light paper-coloured frame with unlined geometric shapes; `008` is mostly red and black, with outlined anime characters and jagged torn shapes.
- `098` Bauhaus primary geometry: this style is flat red and black ink on paper, composed on a diagonal; `098` uses red, blue and yellow solids with soft shading in a balanced arrangement.

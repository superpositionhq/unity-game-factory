# Primary grid neoplasticism

Reference works: Piet Mondrian; Rietveld Schroder House.

## References

- *Composition with Red, Blue and Yellow* (1930), Piet Mondrian, oil painting. https://en.wikipedia.org/wiki/Composition_with_Red,_Blue_and_Yellow
- *Broadway Boogie Woogie* (1943), Piet Mondrian, oil painting. https://en.wikipedia.org/wiki/Broadway_Boogie_Woogie
- *Rietveld Schroder House* (1924), Gerrit Rietveld, architecture. https://en.wikipedia.org/wiki/Rietveld_Schröder_House
- *Red and Blue Chair* (1918), Gerrit Rietveld, furniture. https://en.wikipedia.org/wiki/Red_and_Blue_Chair

## Visual definition

- **Shape language and proportions:** Only horizontals and verticals: rectangular planes and straight bars meeting at right angles. Planes slide past one another and overhang rather than joining at closed corners. No curves, no diagonals.
- **Line and outline:** Thick black bars of constant width separate colour fields; in 3D, black linear members (rails, mullions, frame bars).
- **Shading model:** None. Every plane is one flat colour.
- **Palette:** `#f7f5ee` `#111111` `#d21f1f` `#1f3fa8` `#f2cc1f` `#bdbdbd`. White dominates, with small areas of pure red, blue and yellow, black bars, and occasionally grey.
- **Lighting:** Even, shadowless.
- **Texture and surface:** None. Smooth opaque paint.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Frontal or axonometric (orthographic), aligned to the grid.
- **UI and typography:** UI is the grid itself: white rectangular panels `#f7f5ee` divided by thick black bars, with one small red, blue or yellow block to mark the active item, health or score. Text is an all-capitals geometric sans built from straight strokes, close to De Stijl block lettering; numbers are square block numerals, and icons are made only of rectangles.
- **VFX and motion:** No particles, glow or blur. Effects are flat rectangles that flash a primary colour, slide along the grid, extend or pop in and out, in the stepping rhythm of Broadway Boogie Woogie; motion is straight-line and snappy, with instant starts and stops.

## Fits

- **Genres:** `puzzle`, `strategy`, `tower-defense`, `platformer`, `simulation`, `racing`
- **Moods:** orderly, crisp, upbeat
- **Settings:** modernist house, city street grid, abstract board, gallery

## Unity recipe

### Assets

Only rectangles. Build everything with the Mesh API or ProBuilder's API from axis-aligned rectangular planes and straight bars meeting at right angles; planes slide past one another and overhang instead of closing corners. Black linear members (rails, mullions, frame bars) of one constant thickness divide colour fields. No curves, no diagonals, no store packs. Characters are assemblies of rectangular blocks. Snap every position and size to a grid in the editor step.

### Materials

`Universal Render Pipeline/Unlit` with six materials only: white `#f7f5ee`, black `#111111`, red `#d21f1f`, blue `#1f3fa8`, yellow `#f2cc1f` and grey `#bdbdbd`. No textures, no lighting function, no shadow passes. Keep white dominant: assign primaries to a small share of planes (roughly one in six by area), chosen by the layout script. A flash effect swaps a plane's material to a primary for a few frames.

### Lighting and atmosphere

None: no lights, shadows off in the URP asset, no fog, SSAO or probes. Because surfaces are unlit, depth is read only through overlap and the black bars, so use an orthographic camera or a mild perspective with strictly level horizon; never tilt or roll. Background white.

### Post-processing

None. Tonemapping None so the primaries are exact; no Bloom, grain, blur or vignette. MSAA 8x: straight edges at slight angles in perspective need clean anti-aliasing. HDR off.

### UI and effects

The UI is the grid: white rectangular panels divided by thick black bars, with one small red, blue or yellow block marking the active item, health or score. Lettering is all-capitals built from straight strokes: use a rectilinear face such as Major Mono Display or a blocky square face, or build letters from rectangles with a script; square block numerals. Icons are made only of rectangles. No particles. Effects are flat rectangles that flash a primary, slide along grid lines, extend or pop in and out on a stepped rhythm tied to a beat timer. Movement is straight-line with instant starts and stops: use linear interpolation, no easing.

## Do / Do not

Do:

- Use only horizontal and vertical elements.
- Separate fields with thick black bars.
- Keep white dominant with a few primary rectangles.
- Let planes overlap and extend past junctions.

Do not:

- Do not add circles, triangles or diagonals; that reads as `098` or `080`.
- Do not back-light coloured panes; that reads as `054`.
- Do not add any shading, gradient or texture.
- Do not use thin lines; bars are thick.

## Nearest styles

- `098` Bauhaus primary geometry: this style is flat rectangles divided by thick black bars, with no shading; `098` has no bars and builds its scenes from softly shaded spheres, cones and cylinders.
- `054` Stained glass: this style is a bright, mostly white surface under even light with a few plain primary rectangles; `054` is dark, with glowing back-lit panes of deep red and blue between curved lead lines.
- `080` Constructivist agit poster: this style is strictly horizontal and vertical, with thick black bars and clean smooth paint; `080` thrusts along diagonals, has no bars around its shapes, and shows paper grain and uneven ink.

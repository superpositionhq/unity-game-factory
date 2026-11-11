# Heavy-black gothic comic

Reference works: Hellboy (Mike Mignola).

## References

- *Hellboy: Seed of Destruction* (1994), Mike Mignola (Dark Horse Comics), comic book. https://en.wikipedia.org/wiki/Hellboy:_Seed_of_Destruction
- *Hellboy* (1993), Mike Mignola (Dark Horse Comics), comic book series. https://en.wikipedia.org/wiki/Hellboy
- *Batman: The Animated Series* (1992), Warner Bros. Animation, animated TV series. https://en.wikipedia.org/wiki/Batman:_The_Animated_Series
- *Darkest Dungeon* (2016), Red Hook Studios, video game. https://en.wikipedia.org/wiki/Darkest_Dungeon
- *The Amazing Screw-On Head* (2002), Mike Mignola (Dark Horse Comics), comic book. https://en.wikipedia.org/wiki/The_Amazing_Screw-On_Head

## Visual definition

- **Shape language and proportions:** Blocky, angular simplification. Figures have heavy torsos, small legs and squared hands. Architecture is slabs, arches and broken statues.
- **Line and outline:** Medium-weight angular outline; many edges vanish into black shadow shapes instead of being drawn.
- **Shading model:** Two bands: flat colour and solid black. Black shadow covers 40 to 60% of each form with a jagged, designed edge.
- **Palette:** `#0b0b0c` `#b3261e` `#4a5a63` `#c8a45a` `#2f3b2f` `#d9d2c0`. Muted slate, olive and ochre flats with one strong red accent. Black dominates.
- **Lighting:** Single hard light from above or the side; no fill, no bounce.
- **Texture and surface:** None. Colour areas are perfectly flat. Detail is suggested with a few small black notches.
- **Atmosphere and post-processing:** None. Optional very light paper tint.
- **Camera and framing:** Static, formal compositions; figures small against large black architecture.
- **UI and typography:** Plain black panels with a thin bone-coloured (`#d9d2c0`) rule and squared corners, like comic gutters and caption boxes. Type is angular hand-lettered capitals with uneven, chiselled strokes; icons are flat black-and-ochre silhouettes. Numbers are blocky bone digits, with red (`#b3261e`) kept for damage and warnings.
- **VFX and motion:** Effects are flat designed shapes: jagged black smoke, angular flame in ochre and red, and hard-edged white flash cuts on impact. Motion is sparse and heavy: strong poses held long, few in-between frames and no soft trails.

## Fits

- **Genres:** `survival-horror`, `roguelike`, `detective-mystery`, `action-adventure`, `soulslike`, `hack-and-slash`
- **Moods:** ominous, brooding, pulpy
- **Settings:** ruined abbey, gothic crypt, haunted castle, art deco night city

## Unity recipe

### Assets

Choose blocky, angular models: heavy-torso figures, slab architecture, arches, broken statues. Simplify pack meshes with flat-shaded faces where possible and remove all textures. Assign one muted flat colour per surface from slate, olive, ochre and bone, with `#b3261e` on one element per scene. Build architecture from scratch with ProBuilder's API as large plain slabs; add detail only as small black notch meshes or decals.

### Materials

Write `Style/HeavyBlack`. The `UniversalForward` pass computes `NdotL * shadowAttenuation` from `GetMainLight(shadowCoord)` and compares it against a threshold raised until 40 to 60 percent of each form is shadow; shadow outputs pure `#0b0b0c`, light outputs the flat base colour with no gradient, ambient or specular. Break the boundary into a jagged, designed edge by adding a blocky world-space noise (large cells, hard `floor`) to the comparison. Additional lights are ignored. Add `ShadowCaster`, `DepthOnly` and `DepthNormals`. Outline: a hull pass tagged `SRPDefaultUnlit` at about 3 px, which naturally disappears where it meets black shadow.

### Lighting and atmosphere

A single hard directional or spot light from above or the side. Hard shadows, soft shadows off, shadow resolution 4096, strength 1 so cast shadows merge with the black band. Ambient black. No fog, no GI, no SSAO, no reflection probes. The background is black or one flat colour.

### Post-processing

Nearly empty profile: Tonemapping None, no Bloom. Optionally a Full Screen Pass Renderer Feature after post-processing that multiplies the frame by a pale paper tint. MSAA 4x for clean shape edges. Keep cameras static and formal with figures small in frame.

### UI and effects

Black panels with a thin `#d9d2c0` rule and square corners. Use an angular, chiselled display face such as New Rocker or Metamorphous in capitals; numbers are blocky bone digits and red only marks damage. Icons are two-colour silhouettes. Effects are flat designed shapes as alpha-clipped sprites or meshes: jagged black smoke, angular ochre and red flame, and a one-frame hard-edged white flash on impact. Use few frames and hold them long; no trails, no soft fades.

## Do / Do not

Do:

- Let black shadow shapes cover about half of each form.
- Use flat normals so shadow edges are angular.
- Keep one saturated accent colour.
- Leave colour areas completely flat.

Do not:

- Do not add hatching or wear textures; that reads as `001`.
- Do not go greyscale with a single colour spot; that reads as `069`.
- Do not fill the frame with saturated red; that reads as `008`.
- Do not add gradients or soft shadows.

## Nearest styles

- `069` Selective-colour ink noir: this style puts flat muted colour fills beside its black; `069` is only black and white with one small spot of colour.
- `008` Red-black pop-punk graphic cel: this style uses muted slate, olive and ochre with one small red accent in static compositions; `008` is brighter, flooded with pure red, tilted and jagged.
- `001` Ink-outline comic cel: this style has perfectly flat colour and solid black shadow shapes; `001` hatches its shadows, draws wear marks and shades in three tone steps.

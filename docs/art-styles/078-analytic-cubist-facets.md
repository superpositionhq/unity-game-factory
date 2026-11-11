# Analytic cubist facets

Reference works: Picasso; Braque.

## References

- *Les Demoiselles d'Avignon* (1907), Pablo Picasso, oil painting. https://en.wikipedia.org/wiki/Les_Demoiselles_d'Avignon
- *Violin and Candlestick* (1910), Georges Braque, oil painting. https://en.wikipedia.org/wiki/Georges_Braque
- *Portrait of Daniel-Henry Kahnweiler* (1910), Pablo Picasso, oil painting. https://en.wikipedia.org/wiki/Daniel-Henry_Kahnweiler_(Picasso)
- *Houses at l'Estaque* (1908), Georges Braque, oil painting. https://en.wikipedia.org/wiki/Houses_at_l'Estaque
- *Nude Descending a Staircase, No. 2* (1912), Marcel Duchamp, oil painting. https://en.wikipedia.org/wiki/Nude_Descending_a_Staircase,_No._2

## Visual definition

- **Shape language and proportions:** Objects (guitars, bottles, faces, houses) are broken into angular facets and shown from several viewpoints at once. Facets overlap, slide apart and interpenetrate; object and background merge.
- **Line and outline:** Dark straight or arc line segments along some facet edges, broken and discontinuous.
- **Shading model:** Each facet has its own gradient from light on one edge to dark on the opposite edge, inconsistent with any single light source.
- **Palette:** `#8a7a5c` `#5f5a50` `#c9b88f` `#3a3a36` `#a89a7a` `#6f7a7a` `#e3d9c0`. Near-monochrome ochre, grey, brown and dull green.
- **Lighting:** No single light; each facet is lit as if separately.
- **Texture and surface:** Short, parallel, dabbed brush strokes (hatched dabs) inside facets; occasional stencil letters or wood-grain patches.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Frontal, shallow space; the picture plane is flat and crowded.
- **UI and typography:** Panels are overlapping angular planes in ochre `#c9b88f` and grey `#5f5a50` with broken dark line segments along some edges, like collage pieces. Text and numbers are stencil capitals in dark grey-brown `#3a3a36`, in the manner of the stencilled letters in the paintings, and icons are objects reduced to a few shifted facets.
- **VFX and motion:** Hits shatter an object into flat angular shards that slide apart and overlap before they settle; dust and smoke are stacks of small ochre and grey facets. Movement can leave a short trail of overlapping repeated poses, as in Nude Descending a Staircase, and facets shift as the camera turns.

## Fits

- **Genres:** `puzzle`, `detective-mystery`, `exploration`, `stealth`, `strategy`
- **Moods:** cerebral, disorienting, sombre
- **Settings:** Paris studio, café table still life, hillside village, music hall

## Unity recipe

### Assets

Still-life and figure subjects: guitars, bottles, faces, houses, tables. Take ordinary models and fracture them: an editor step cuts each mesh into angular chunks with random planes, then slides, rotates and overlaps the chunks slightly, and duplicates some chunks at a second orientation to suggest another viewpoint. Background planes are fractured the same way so object and ground merge. Give each facet UVs with a consistent edge-to-edge direction. Generate a hatched-dab brush tile, stencil-letter decals and a wood-grain patch.

### Materials

Write `Style/CubistFacet`, unlit. `UniversalForward` ignores scene lights: each facet shades itself with a linear gradient along its own UV axis from light on one edge to dark on the opposite edge, with gradient direction and strength randomised per facet from vertex colour, so no single light is implied. Colour comes from the ochre-grey palette, chosen per facet; multiply in the dab tile. Dark line segments along some facet edges come from a UV-border mask enabled on a random subset of edges and broken by noise. Add `DepthOnly` and `DepthNormals`; no `ShadowCaster`. A slight view-dependent offset of the facets (vertex-stage shift by facet normal and view direction) makes planes slide as the camera turns.

### Lighting and atmosphere

No lights are used, shadows off, flat ambient. No fog, SSAO or probes. Background is a field of the same facets in `#8a7a5c` and `#5f5a50`.

### Post-processing

None of note. Tonemapping None, optional canvas-grain multiply at low strength. No Bloom, no outline pass: lines must stay broken and belong to facets. MSAA 4x.

### UI and effects

Panels are overlapping angular planes in `#c9b88f` and `#5f5a50` with broken dark segments on some edges, like collage pieces. Text and numbers in stencil capitals from a face such as Stardos Stencil or Allerta Stencil, in `#3a3a36`. Icons are objects reduced to a few shifted facets. Hits release an object's chunks, which slide apart and overlap before settling back with a tween. Dust and smoke are stacks of small facet quads. Fast movement leaves a short trail of repeated poses: spawn two or three fading copies of the mesh at previous positions.

## Do / Do not

Do:

- Fragment objects into shifted angular facets.
- Show several viewpoints of one object together.
- Give each facet its own light-to-dark gradient.
- Hold the palette to ochre, grey and brown.

Do not:

- Do not keep objects whole with clean low-poly facets under one light; that reads as `043` or `066`.
- Do not use primary colours with black bars on white; that reads as `079`.
- Do not use diagonal red-black poster geometry; that reads as `080`.
- Do not paint coherent leaning sets with hard shadows; that reads as `071`.

## Nearest styles

- `071` Expressionist painted set: this style breaks objects into overlapping ochre-grey facets seen from several viewpoints; `071` keeps its sets whole but skewed, in tinted black and white with painted shadow shapes.
- `066` Faceted low-poly gradient: this style is dull ochre and grey with broken dark lines on facet edges and objects that fall apart into shifted planes; `066` keeps objects whole, with clean triangles in bright coral, mint and sky blue and no lines.
- `079` Primary grid neoplasticism: this style has brushy, shaded facets at all angles in ochre and grey; `079` is perfectly flat white, red, blue and yellow rectangles between straight black bars.

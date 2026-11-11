# Watercolour wash minimal

Reference works: Gris.

## References

- *Gris* (2018), Nomada Studio, video game. https://en.wikipedia.org/wiki/Gris
- *Neva* (2024), Nomada Studio, video game. https://en.wikipedia.org/wiki/Neva_(video_game)
- *Child of Light* (2014), Ubisoft Montreal, video game. https://en.wikipedia.org/wiki/Child_of_Light
- *The Red Turtle* (2016), Michael Dudok de Wit (Studio Ghibli and Wild Bunch), animated film. https://en.wikipedia.org/wiki/The_Red_Turtle

## Visual definition

- **Shape language and proportions:** Elegant, geometric simplification: circles, thin columns, long triangles. Architecture is tall and delicate; figures are small with flowing cloth.
- **Line and outline:** Sparse, thin pencil-like line on some structures. Most shapes have no line.
- **Shading model:** None. Shapes are flat washes with internal watercolour variation.
- **Palette:** `#f4efe9` `#e4b7b2` `#8fb8c9` `#b7a3c9` `#5d6d7e` `#f2d6a2` `#2f3a45`. Mostly pale: off-white, blush, dusty blue, lilac, with a dark slate for the figure. Colour is introduced one hue at a time.
- **Lighting:** No directional light. Depth is shown by layers that get paler with distance.
- **Texture and surface:** Watercolour: granulation, soft blooms, darker pigment at shape edges, visible paper.
- **Atmosphere and post-processing:** Paper overlay and soft edge bleed.
- **Camera and framing:** Side view with strong parallax layers; very wide framing, subject small.
- **UI and typography:** Almost no UI: thin pencil-line icons and small circular markers, with no panels or frames. Text is a light, widely spaced thin geometric sans in dark slate `#2f3a45` or off-white `#f4efe9`; counters are rows of small shapes instead of numerals.
- **VFX and motion:** Soft watercolour blooms, drifting dust motes and pigment that spreads through the paper when a new hue arrives; no hard impact flashes. Animation is fluid and hand-drawn, with long flowing cloth and hair and slow eases.

## Fits

- **Genres:** `platformer`, `puzzle`, `exploration`, `action-adventure`
- **Moods:** melancholic, serene, hopeful
- **Settings:** ruined temples, pale deserts, underwater caverns, sky palaces

## Unity recipe

### Assets

Build almost everything from scratch: the forms are circles, thin columns and long triangles, which the Mesh API or ProBuilder's API produces cleanly. Architecture is tall and delicate; figures are small with long cloth strips (cloth or a chain of bones). Store packs rarely fit; if one is used, strip textures and simplify meshes to plain shapes. Generate by script a watercolour set: paper grain, a granulation noise, a soft bloom mask and an edge-darkening profile. Arrange scenes as side-view parallax layers.

### Materials

Write `Style/Watercolour`, an unlit shader. `UniversalForward` outputs a flat wash colour modulated by granulation noise in screen space, darkened toward the shape's edge (use a UV-based or vertex-colour edge distance stored at build time, since `NdotV` is unreliable on flat layers) to imitate pigment gathering at the border. Each layer has a `_Paleness` value that lerps it toward `#f4efe9` with distance. No lighting function, no shadow pass; add `DepthOnly`. Transparent layers use alpha blending with `ZWrite Off` and are sorted by layer order. A global `_HueReveal` position and radius lets one hue at a time spread through the world: outside the radius colour is replaced by grey-white.

### Lighting and atmosphere

No lights, no shadows, no fog component, no SSAO, no probes. Disable main light shadows in the URP asset. Depth is carried by paleness per layer. The camera background is the paper colour.

### Post-processing

Two fullscreen passes after the scene. First, an edge-bleed pass: blur the colour slightly and displace the lookup with a low-frequency noise so edges bleed softly. Second, multiply by the paper texture and add faint granulation. Tonemapping None, no Bloom, no vignette, no line pass. SMAA. Use a very wide frame with a small subject.

### UI and effects

Almost no UI: thin pencil-line icons and small circular markers, no panels. Font asset from a thin geometric sans such as Jost ExtraLight or Raleway Thin with wide spacing, in `#2f3a45` or `#f4efe9`. Counters are rows of small shapes, not numerals. Effects are soft alpha-blended blooms that grow and fade over one to two seconds, drifting dust motes, and the pigment spread when a new hue arrives, animated by growing `_HueReveal` with a noisy front. No impact flashes. Use slow eases on every move.

## Do / Do not

Do:

- Use pale washes with darker pigment edges.
- Stack depth layers that fade to paper.
- Keep the figure small and dark against pale shapes.
- Limit each scene to one to three hues.

Do not:

- Do not add brush outlines on every contour; that reads as `022`.
- Do not use clean flat vector fills with strong saturation; that reads as `060`.
- Do not use thin lines on perfectly flat pastel colour; that reads as `012`.
- Do not add directional light and shadows.

## Nearest styles

- `022` Sumi-e ink wash: this style is mostly lineless, built from pale wash shapes; `022` draws almost every form with a heavy black brush line.
- `012` Thin-line pastel desert: washes here show granulation, blooms and paper grain, with few lines; `012` puts a fine dark line on perfectly flat, untextured colour.
- `060` Layered flat-colour wilderness: this style is pale and washed out, with soft bleeding edges; `060` uses vivid, deep sunset colours in crisp-edged flat layers.

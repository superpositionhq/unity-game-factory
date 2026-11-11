# Faceted low-poly gradient

Reference works: Astroneer; Islanders.

## References

- *Astroneer* (2019), System Era Softworks, video game. https://en.wikipedia.org/wiki/Astroneer
- *Islanders* (2019), Grizzly Games, video game. https://en.wikipedia.org/wiki/Islanders_(video_game)
- *Lara Croft Go* (2015), Square Enix Montreal, video game. https://en.wikipedia.org/wiki/Lara_Croft_Go

## Visual definition

- **Shape language and proportions:** Landscapes and objects made of visible triangles: irregular faceted terrain, crystal rocks, trees as a few stacked low-poly cones or blobs. Medium-low polygon counts, deliberately uneven triangulation.
- **Line and outline:** No outline.
- **Shading model:** Flat shading: one tone per triangle, so curved forms show many small flat steps. Soft overall light.
- **Palette:** `#f2a65a` `#ef6f6c` `#7fd1b9` `#4a7fb5` `#f7e3af` `#8e6bbf` `#2f4858`. Bright, soft gradient schemes: coral, sand, mint, sky blue and violet. Colour varies smoothly across the terrain by height.
- **Lighting:** Soft sun with coloured sky fill; gentle shadows.
- **Texture and surface:** None. Colour comes from vertex colours and facets.
- **Atmosphere and post-processing:** Soft gradient sky, light distance fog, mild bloom; clean anti-aliased edges.
- **Camera and framing:** Elevated three-quarter view or third-person; 35 to 50 mm equivalent.
- **UI and typography:** Rounded flat panels in soft pastel fills with no borders, and chunky simple icons, some built from a few facets. Text is a friendly rounded geometric sans in cream `#f7e3af` or dark slate `#2f4858`; counters are large clean numerals, with coral `#ef6f6c` and mint `#7fd1b9` as resource colours.
- **VFX and motion:** Particles are small flat-shaded triangles, cubes and low-poly puffs, not soft sprites; impacts throw a short burst of shards and a small pop of scale. Motion is smooth and bouncy with light squash and stretch, and placed objects settle with a small overshoot.

## Fits

- **Genres:** `survival-craft`, `strategy`, `simulation`, `exploration`, `tower-defense`, `puzzle`
- **Moods:** calm, cheerful, curious
- **Settings:** alien planet, tropical islands, floating islands, crystal canyon

## Unity recipe

### Assets

Visible triangles everywhere: irregular faceted terrain, crystal rocks, trees as stacked low-poly cones or blobs. Low-poly nature packs fit well. Generate terrain by script from a jittered point grid with uneven triangulation; avoid regular quads. Remove all textures and store colour in vertex colours: a height-based gradient across the terrain (sand to coral to mint to sky blue to violet) assigned per triangle, so each face has one colour. Split vertices per triangle.

### Materials

Write `Style/FacetGradient`. `UniversalForward` reads vertex colour, computes one flat normal per triangle (split vertices, or `normalize(cross(ddy(positionWS), ddx(positionWS)))` in the fragment stage, which also handles deforming meshes), and applies soft Lambert from `GetMainLight(shadowCoord)` plus `SampleSH` sky fill, with the shadow term softened so shadows stay gentle. A small per-triangle brightness variation from a hash of the face position keeps neighbouring facets distinct. Call `MixFog`. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`. Simple Lit with vertex colour is not enough because it has no vertex-colour input by default. Water is the same shader with animated vertex heights.

### Lighting and atmosphere

A soft sun with soft shadows at reduced strength (about 0.5), four cascades, 120 m, and a coloured gradient ambient (`AmbientMode.Trilight`) with a blue or violet sky term. Light linear fog toward the horizon colour. A soft gradient skybox. SSAO off or very low; facets already describe form.

### Post-processing

Full resolution with clean anti-aliasing (MSAA 4x or SMAA): crisp edges separate this from a retro polygon look. Mild Bloom, Neutral tonemapping, saturation +5. No grain, pixelation or outline.

### UI and effects

Rounded flat panels in soft pastel fills with no borders; chunky simple icons, some built from a few facets and rendered to sprites. Font asset from a friendly rounded geometric sans such as Quicksand Bold or Nunito, in `#f7e3af` or `#2f4858`; large clean numerals, `#ef6f6c` and `#7fd1b9` as resource colours. Particles are mesh particles with the facet shader: small triangles, cubes and low-poly puffs, never soft sprites. Impacts throw a short burst of shards and a small scale pop; placed objects settle with an overshoot tween.

## Do / Do not

Do:

- Make triangles irregular and visibly faceted.
- Colour by vertex colours with a height gradient.
- Use flat shading at full resolution with anti-aliasing.
- Keep lighting soft and bright.

Do not:

- Do not use a strict cube grid with the same top, left and right face tones on every block; that reads as `059`.
- Do not render at low resolution with very few polygons; that reads as `043`.
- Do not flatten layers into single fog colours; that reads as `060`.
- Do not add textures.

## Nearest styles

- `059` Isometric pastel impossible architecture: `059` builds on a strict block grid in isometric view, with the same tones on every top, left and right face; this style has irregular triangles that each catch a different tone, and colour that shifts with height.
- `043` Flat-shaded early polygon: `043` looks like an early 3D game, with low resolution, jagged pixel edges and very coarse models; this style is crisp, anti-aliased and bright, with enough triangles to shape hills and rocks.
- `067` Boxy toybox low-poly: `067` builds objects from boxes and cylinders with stripe, dot and face decals; this style has triangulated organic forms and no decals.

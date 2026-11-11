# Claymation

Reference works: Wallace & Gromit.

## References

- *Wallace & Gromit: The Wrong Trousers* (1993), Aardman Animations (Nick Park), stop-motion film. https://en.wikipedia.org/wiki/The_Wrong_Trousers
- *Chicken Run* (2000), Aardman Animations, stop-motion film. https://en.wikipedia.org/wiki/Chicken_Run
- *Shaun the Sheep Movie* (2015), Aardman Animations, stop-motion film. https://en.wikipedia.org/wiki/Shaun_the_Sheep_Movie
- *The Neverhood* (1996), The Neverhood, Inc., video game. https://en.wikipedia.org/wiki/The_Neverhood
- *Pingu* (1990), Otmar Gutmann, stop-motion TV series. https://en.wikipedia.org/wiki/Pingu

## Visual definition

- **Shape language and proportions:** Rounded, hand-formed blobs: thick limbs, wide mouths, bulging eyes set close together, sausage fingers. No sharp edges; every corner is pressed round.
- **Line and outline:** No outline.
- **Shading model:** Smooth and soft, with a waxy sheen and slight subsurface softness.
- **Palette:** `#e9d2a6` `#c9793a` `#6e9b5b` `#4a78b0` `#b5483a` `#f3efe4` `#5b4636`. Warm, slightly muted plasticine colours: tan, orange-brown, green, blue, brick red, cream.
- **Lighting:** Small-studio lighting: one soft key, fill and a rim, with soft contact shadows on a miniature set.
- **Texture and surface:** Fingerprints, thumb dents, tool marks and tiny lumps on every clay surface. Sets mix in real miniature materials (wood, fabric, wallpaper).
- **Atmosphere and post-processing:** Shallow depth of field as in macro photography; animation stepped at 12 frames per second.
- **Camera and framing:** Close, macro-like, 50 to 85 mm equivalent, eye level with the puppets.
- **UI and typography:** Panels and buttons look pressed from clay slabs or cut from cardboard, with rounded edges and thumb dents; icons are small clay models of the objects. Lettering is a soft, chunky rounded sans that looks rolled from clay ropes, and counters are fat rounded digits in cream `#f3efe4`, brick red `#b5483a` and blue `#4a78b0`.
- **VFX and motion:** Effects are made from physical materials: cotton-wool smoke, clay pellets and blobs for splashes, clear gel for water, cut-card stars on impact. Animation runs on twos with strong squash and stretch, mouth shapes that pop from one pose to the next, and a slight shimmer on clay surfaces between frames.

## Fits

- **Genres:** `puzzle`, `platformer`, `action-adventure`, `detective-mystery`, `stealth`
- **Moods:** cosy, comic, warm
- **Settings:** English village, farmyard, inventor's workshop, wallpapered living room

## Unity recipe

### Assets

Rounded, hand-formed shapes with no sharp edges: build characters and props in Blender background mode from metaballs or subdivided primitives with heavy bevels, thick limbs and bulging eyes. To restyle a cartoon pack, apply a smoothing pass and inflate thin parts. Generate clay surface maps by script: a fingerprint and thumb-dent normal map, a lumpy low-frequency height map and a subtle albedo mottling. Sets mix in miniature materials (wood, fabric, wallpaper) from ordinary PBR textures at exaggerated texel scale.

### Materials

Clay uses `Universal Render Pipeline/Lit`: base colours from the plasticine palette, smoothness 0.35 to 0.45 for a waxy sheen, no metallic, the fingerprint normal map through `_BumpMap` and a detail normal for small lumps. For subsurface softness write a small variant, `Style/Clay`, that fills `SurfaceData`, calls `UniversalFragmentPBR` and adds wrapped diffuse plus a faint warm transmission term on thin parts; it must include the full Lit pass set. To get the shimmer between frames, offset the normal-map UVs by a random amount on each animation step using a `MaterialPropertyBlock`.

### Lighting and atmosphere

Small-studio lighting sized to a tabletop: one soft key (a spot or area-like light at close range with soft shadows, high quality), a weak fill and a rim light. Shadow distance short (10 to 15 m at miniature scale) so the shadow map is dense and contact shadows are soft and precise. SSAO on with a small radius. A baked reflection probe of a studio environment. No fog. Backdrop is a painted card.

### Post-processing

Depth Of Field in Bokeh mode with a wide aperture and focus on the hero gives the macro look across the whole depth range, not just the top and bottom of the frame. Neutral tonemapping, slight warmth, mild Vignette. No Bloom, no Motion Blur: stepped animation must stay crisp. SMAA.

### UI and effects

Panels and buttons look pressed from clay slabs or cut from cardboard: render them from 3D models to sprites with an editor step. Font asset from a soft chunky rounded face such as Chewy or Baloo 2 ExtraBold; fat digits in `#f3efe4`, `#b5483a` and `#4a78b0`. Effects use mesh particles with the clay material: pellets and blobs for splashes, cotton-wool smoke meshes, clear gel for water (transparent Lit), cut-card stars on impact. Step all animation to 12 poses per second by ticking `Animator.Update` manually, and swap mouth shapes with no blending.

## Do / Do not

Do:

- Round every edge and break symmetry.
- Add fingerprints and thumb dents.
- Use macro depth of field.
- Step animation at 12 poses per second.

Do not:

- Do not make surfaces perfectly smooth and glossy; that reads as `057` or `052`.
- Do not use thin spindly forms in dark desaturated sets; that reads as `049`.
- Do not use fabric fuzz and stitches; that reads as `051`.
- Do not use hard-edged geometry.

## Nearest styles

- `049` Gothic stop-motion puppet: `049` is dark and muted, with thin spindly puppets on crooked sets; this style is bright and warm, with chunky rounded figures.
- `057` Toy-diorama tilt-shift: `057` is clean, glossy plastic with no marks; this style shows fingerprints and thumb dents on waxy clay.
- `051` Felt and yarn: `051` has fibre fuzz and visible stitches on every surface; this style is smooth clay with fingerprints and no stitch lines.

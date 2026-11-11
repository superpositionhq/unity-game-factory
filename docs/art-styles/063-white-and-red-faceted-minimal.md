# White-and-red faceted minimal

Reference works: Superhot.

## References

- *Superhot* (2016), Superhot Team, video game. https://en.wikipedia.org/wiki/Superhot
- *Superhot: Mind Control Delete* (2020), Superhot Team, video game. https://en.wikipedia.org/wiki/Superhot:_Mind_Control_Delete
- *THX 1138* (1971), George Lucas, live-action film. https://en.wikipedia.org/wiki/THX_1138
- *Antichamber* (2013), Alexander Bruce, video game. https://en.wikipedia.org/wiki/Antichamber

## Visual definition

- **Shape language and proportions:** Environments are clean white architectural models with simple blocky furniture. Enemies are faceted, crystalline human figures that shatter into shards. Weapons and interactive objects are simple solid shapes.
- **Line and outline:** No outline.
- **Shading model:** Flat-shaded facets on figures; environments have soft ambient occlusion on white. No textures.
- **Palette:** `#f4f4f4` `#dcdcdc` `#ff2a1a` `#141414` `#b8b8b8`. White and pale grey environment, glossy red enemies, solid black interactive objects. Nothing else.
- **Lighting:** Bright, diffuse, shadowless-looking light; faint ambient occlusion defines corners.
- **Texture and surface:** None.
- **Atmosphere and post-processing:** High exposure; red motion trails on bullets; slight bloom.
- **Camera and framing:** First-person, 80 to 90 degree field of view.
- **UI and typography:** No frames or panels. Messages are huge all-caps words in a heavy condensed sans that fill the screen one word at a time, in black `#141414` or red `#ff2a1a` on white. Icons are solid black flat shapes, and counters are plain bold numerals.
- **VFX and motion:** Enemies break into hard red glass shards with no blood or smoke; bullets leave straight red trails and muzzle flashes are simple faceted bursts. Motion is abrupt and linear and stays readable in slow motion, with shards that hang and drift in the air.

## Fits

- **Genres:** `fps`, `puzzle`, `top-down-shooter`, `roguelike`, `stealth`
- **Moods:** tense, clinical, stark
- **Settings:** office block, laboratory, virtual simulation, parking garage

## Unity recipe

### Assets

Environments are clean white architectural models: plain rooms, stairs, blocky furniture, built with ProBuilder's API or from stripped interior packs with every texture and small fitting removed. Enemies are faceted crystalline humanoids: decimate a rigged character to a few hundred triangles with split normals, and pre-fracture it into shards (Voronoi cut in Blender background mode) that replace the mesh on death. Weapons and interactive objects are simple solid shapes.

### Materials

Environment: `Universal Render Pipeline/Lit` or Simple Lit, `_BaseColor` `#f4f4f4`, smoothness near 0, no maps. Enemies: a faceted glossy red. Lit with `#ff2a1a`, smoothness 0.8 and split normals works; for stricter flat shading write `Style/FacetRed`, which derives the face normal in the fragment stage from screen-space derivatives of world position (`cross(ddy(p), ddx(p))`) so even skinned meshes stay faceted, then calls a simple Blinn-Phong with `GetMainLight()`. Interactive objects use `Universal Render Pipeline/Unlit` in `#141414`. Only these three material families exist.

### Lighting and atmosphere

Bright diffuse light that looks shadowless: strong flat white ambient and a weak directional light with shadows off or very faint. Form in the white rooms comes from ambient occlusion only: enable the SSAO renderer feature with moderate intensity and a medium radius, or bake occlusion into lightmaps. No fog; white sky. Reflection probe plain white so red highlights stay clean.

### Post-processing

High exposure: post exposure +0.5 with Neutral tonemapping so white is truly white. Slight Bloom. No grain, vignette or colour grade. MSAA 4x. Slow motion is a `Time.timeScale` change tied to player movement.

### UI and effects

No frames or panels. Messages are huge all-caps words that fill the screen one at a time: font asset from a heavy condensed sans such as Anton or Bebas Neue, black or `#ff2a1a` on white, shown for a few frames each. Icons are solid black shapes; counters are plain bold numerals. Enemies swap to their shard set on death, shards driven as rigidbodies with the red material; no blood or smoke. Bullets leave straight red `TrailRenderer` lines. Muzzle flashes are small faceted mesh bursts.

## Do / Do not

Do:

- Use only white, red and black.
- Facet the figures like crystal.
- Leave the environment untextured white.
- Shatter figures into shards.

Do not:

- Do not add more accent hues and smooth city architecture; that reads as `035`.
- Do not add moulded panels and equipment detail; that reads as `091`.
- Do not scatter black ink splats on white; that reads as `074`.
- Do not colour the environment.

## Nearest styles

- `035` White city with primary accents: `035` has smooth-shaded white city buildings with several bright accent colours; this style allows only red and black against white and facets its figures like crystal.
- `074` White void ink-splat: `074` is an unlit blank white void where the world shows only where black ink splats land; this style shows all of its white rooms, with soft corner shadows and faceted red figures.
- `091` Clinical white space-age: `091` has moulded panels, seams and equipment on smooth glossy white surfaces; this style has bare untextured white blocks with no fittings.

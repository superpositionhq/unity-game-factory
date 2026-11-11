# Voxel block world

Reference works: Minecraft.

## References

- *Minecraft* (2011), Mojang Studios, video game. https://en.wikipedia.org/wiki/Minecraft
- *Dragon Quest Builders* (2016), Square Enix, video game. https://en.wikipedia.org/wiki/Dragon_Quest_Builders
- *Terraria* (2011), Re-Logic, video game. https://en.wikipedia.org/wiki/Terraria
- *Minecraft Dungeons* (2020), Mojang Studios and Double Eleven, video game. https://en.wikipedia.org/wiki/Minecraft_Dungeons

## Visual definition

- **Shape language and proportions:** Everything is made of 1 m cubes on a grid. Characters are a few rectangular boxes. No curves anywhere; circles are stepped.
- **Line and outline:** No outline.
- **Shading model:** Each cube face gets a fixed brightness by direction (top brightest, two side levels, bottom darkest) plus simple corner ambient occlusion.
- **Palette:** `#7cb342` `#8d6e4a` `#7f7f7f` `#4fa3e0` `#c2b280` `#3b6e2a` `#d9d9d9` `#5a3d28`. Natural block colours: grass green, dirt brown, stone grey, sand, water blue.
- **Lighting:** Uniform sky light; block light levels fall off in steps.
- **Texture and surface:** 16x16 px textures per block face, unfiltered, with noisy pixel variation.
- **Atmosphere and post-processing:** None. Distance fog to sky colour.
- **Camera and framing:** First-person, 70 degree field of view.
- **UI and typography:** Square pixel-art panels in stone grey `#7f7f7f` with a one-pixel light edge and a one-pixel dark edge; a hotbar of square slots holds 16x16 px item icons, above rows of pixel hearts and food icons. Text is a blocky pixel sans in white with a dark drop shadow, and item counts are small digits in the slot corners.
- **VFX and motion:** Particles are tiny flat squares cut from the block textures: break fragments, smoke puffs, hit stars. A struck creature flashes red and is knocked back. Animation is stiff, with box limbs that swing on simple pivots and never bend or squash.

## Fits

- **Genres:** `survival-craft`, `exploration`, `simulation`, `action-adventure`, `rpg`, `tower-defense`
- **Moods:** calm, playful, adventurous
- **Settings:** blocky wilderness, underground mines, village and farmland, cube-built castle

## Unity recipe

### Assets

Build the world from scratch: a chunked voxel mesher written with the Mesh API that emits only visible faces of 1 m cubes and writes UVs into a block atlas. Paint the atlas by script: 16x16 px per face with noisy per-pixel variation in grass, dirt, stone, sand and water colours; point filtering, no mipmaps beyond what stays crisp, no compression. Characters and creatures are a few rectangular boxes with their own 16 px-per-face skins. Store packs do not fit unless voxelised.

### Materials

Write `Style/VoxelBlock`. Lighting is not computed from a light: `UniversalForward` picks a fixed brightness from the face normal (top 1.0, north-south 0.8, east-west 0.6, bottom 0.5), multiplies by a per-vertex ambient-occlusion value baked by the mesher (0 to 3 neighbours at each corner) and by a per-vertex block-light and sky-light level in steps of 1/15. Call `MixFog`. Use alpha clip for leaves and a second transparent material for water. Add `DepthOnly` and `ShadowCaster` only if sun shadows are wanted; the classic look needs neither. One opaque material covers all terrain.

### Lighting and atmosphere

Uniform sky light: a directional light may exist for particles but terrain ignores it. Shadows off or one cascade at short range. Linear fog to the sky colour starting at about 70 percent of the view distance. Flat blue sky or simple gradient. No SSAO renderer feature (corner occlusion is baked), no GI, no reflection probes.

### Post-processing

None beyond Tonemapping None or Neutral. No Bloom, no Depth Of Field, no grain. Render scale 1, MSAA off or 2x; texels stay sharp because of point filtering.

### UI and effects

Square pixel-art panels in `#7f7f7f` with a one-pixel light edge and a one-pixel dark edge, a hotbar of square slots with 16x16 item icons, rows of pixel hearts and food icons. Font asset from a blocky pixel sans such as Pixelify Sans or Silkscreen in raster mode, white with a dark one-pixel underlay offset as drop shadow; item counts in slot corners. Particles are tiny flat squares whose UVs are random 4x4 px cuts from the block atlas: break fragments, smoke puffs, hit stars. Struck creatures tint red and are pushed back. Box limbs swing on pivots only.

## Do / Do not

Do:

- Build everything from unit cubes on a grid.
- Use 16x16 unfiltered textures.
- Shade faces by direction with fixed levels.
- Add per-vertex corner ambient occlusion.

Do not:

- Do not use smooth plastic bricks with studs; that reads as `052`.
- Do not use 2D sprite tiles with three colours each; that reads as `042`.
- Do not add vertex wobble and affine warping; that reads as `036`.
- Do not use rounded or bevelled geometry.

## Nearest styles

- `052` Brick toy: `052` is smooth, clean, glossy plastic with studs; this style has noisy pixel textures on every cube face and no studs or gloss.
- `042` NES 8-bit tile: `042` is flat, unlit 2D tiles and sprites in a few saturated colours; this style is a 3D perspective world with three face shades and many natural colours.
- `036` PS1 low-poly wobble: `036` is dark, with wobbling low-poly models, warped textures and soft light blended across each polygon; this style is in bright daylight, with steady cubes and one fixed shade per face direction.

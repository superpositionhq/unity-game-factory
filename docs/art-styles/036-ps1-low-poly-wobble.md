# PS1 low-poly wobble

Reference works: Silent Hill; Final Fantasy VII.

## References

- *Silent Hill* (1999), Konami (Team Silent), video game. https://en.wikipedia.org/wiki/Silent_Hill_(video_game)
- *Final Fantasy VII* (1997), Square, video game. https://en.wikipedia.org/wiki/Final_Fantasy_VII
- *Metal Gear Solid* (1998), Konami, video game. https://en.wikipedia.org/wiki/Metal_Gear_Solid_(video_game)
- *Tomb Raider* (1996), Core Design, video game. https://en.wikipedia.org/wiki/Tomb_Raider_(1996_video_game)
- *Crash Bandicoot* (1996), Naughty Dog, video game. https://en.wikipedia.org/wiki/Crash_Bandicoot_(video_game)

## Visual definition

- **Shape language and proportions:** Very low polygon counts: characters of 300 to 800 triangles with blocky hands and pointed joints; environments made of large flat quads.
- **Line and outline:** No outline.
- **Shading model:** Per-vertex lighting (Gouraud) at low colour depth, so gradients show stepped bands and dither.
- **Palette:** `#1a1a22` `#4a4438` `#7a6a55` `#5a6a7a` `#8a3a2a` `#b8a888` `#2e3a2e`. Muddy, dark and low-contrast; 15-bit colour with visible ordered dither.
- **Lighting:** Vertex lighting from one or two sources, short draw distance closed off by fog or darkness.
- **Texture and surface:** Tiny textures (32 to 128 px) with no filtering: large square texels, warped by affine mapping; polygons jitter because vertices snap to the pixel grid.
- **Atmosphere and post-processing:** 320x240 output upscaled with nearest-neighbour sampling, 4x4 ordered dither, no anti-aliasing.
- **Camera and framing:** Fixed or tank-control cameras; wide field of view (60 to 75 degrees).
- **UI and typography:** Plain rectangular windows in a dark flat or gradient fill with a thin pale border, and low-resolution pixel icons. Type is a chunky low-resolution bitmap face with fixed-width pixel numerals. Text is pale tan `#b8a888` on near-black `#1a1a22`, and damage numbers are small pale pixel digits that pop up over the target.
- **VFX and motion:** Effects are a few flat textured quads with large pixels: a flash sprite, a puff of smoke, blood as a few dull red squares; no soft particles. Animation is stiff and keyframed with few in-betweens: limbs move as rigid segments and the mesh jitters as it moves.

## Fits

- **Genres:** `survival-horror`, `rpg`, `action-adventure`, `stealth`, `platformer`, `exploration`
- **Moods:** eerie, uneasy, nostalgic
- **Settings:** foggy abandoned town, industrial megacity slums, military base, ancient tomb

## Unity recipe

### Assets

Build or reduce models to very low counts: characters of 300 to 800 triangles with blocky hands, environments from large flat quads. Decimate store models in Blender background mode and rebake their textures to 32 to 128 px. Texture import settings in the editor step: `FilterMode.Point`, no mipmaps, no compression, max size 128. Remove normal, metallic and occlusion maps. Darken and mute albedos toward the palette, and quantise them to 5 bits per channel.

### Materials

Write `Style/RetroVertexLit`. In the vertex stage of `UniversalForward`: compute lighting per vertex from `GetMainLight()` and the additional-light loop (Gouraud), then snap the clip-space position to a virtual 320x240 grid (`pos.xy = floor(pos.xy / pos.w * grid) / grid * pos.w`) so polygons jitter. Pass the UV with the `noperspective` interpolation modifier for affine texture warping. The fragment stage multiplies texture by the interpolated light and applies fog per vertex. No per-pixel lighting, no specular, no shadow receiving. Add `DepthOnly` and, only if blob shadows are not used, `ShadowCaster`. Subdivide large floor quads slightly so affine warping stays tolerable near the camera.

### Lighting and atmosphere

One or two realtime lights, shadows off in the URP asset. Dark flat ambient. Linear fog with a short end distance (20 to 40 m) in near-black or dark grey, and set the camera far clip just beyond it. No SSAO, GI or reflection probes.

### Post-processing

Render the camera to a 320x240 `RenderTexture` with point filtering and blit it to the screen, or set render scale low with the upscaling filter on Point. A fullscreen pass on the low-resolution image applies a 4x4 Bayer ordered dither and reduces colour to 15 bits (5 per channel). No anti-aliasing, no Bloom, Tonemapping None, HDR off. Run the dither before the upscale so dither cells are one low-resolution pixel.

### UI and effects

Plain rectangular windows with a dark flat or gradient fill and a thin pale border, drawn on the same low-resolution target. Bitmap font: create the TextMeshPro asset from a pixel face such as Press Start 2P or Pixelify Sans with a raster render mode and point filtering. `#b8a888` on `#1a1a22`. Effects are a few flat unfiltered quads: a flash sprite, a smoke puff, dull red squares for blood; no soft particles. Animate with stepped keys and no blending between clips.

## Do / Do not

Do:

- Snap vertices to a 320x240 grid.
- Use affine texture mapping and nearest filtering.
- Render at 320x240 and upscale with nearest sampling.
- Add ordered dither at 5 bits per channel.

Do not:

- Do not filter textures or anti-alias edges; a blurred look reads as `037`.
- Do not remove textures and use flat colour polygons; that reads as `043`.
- Do not use billboard sprites in a ray-cast-style maze; that reads as `046`.
- Do not use perspective-correct mapping with stable vertices.

## Nearest styles

- `037` N64 filtered fog: textures here show hard square texels, polygons jitter, and the image is dark and dithered; `037` has smeared soft textures, steady geometry and bright primary colours.
- `046` Low-res sprite 2.5D shooter: characters and scenery here are textured polygon models; `046` uses flat sprites that always face the camera, in levels made of vertical walls and flat floors.
- `043` Flat-shaded early polygon: every polygon here carries a small pixelated texture; `043` has plain single-colour facets with no textures.

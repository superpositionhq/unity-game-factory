# Game Boy four-shade green

Reference works: Link's Awakening (1993); Tetris.

## References

- *The Legend of Zelda: Link's Awakening* (1993), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Link's_Awakening
- *Tetris (Game Boy)* (1989), Nintendo, video game. https://en.wikipedia.org/wiki/Tetris_(Game_Boy_video_game)
- *Pokemon Red and Blue* (1996), Game Freak, video game. https://en.wikipedia.org/wiki/Pokémon_Red,_Blue,_and_Yellow
- *Super Mario Land* (1989), Nintendo R&D1, video game. https://en.wikipedia.org/wiki/Super_Mario_Land

## Visual definition

- **Shape language and proportions:** Tile-based: everything fits an 8 px or 16 px grid. Characters are 16x16 px with large heads. Shapes are built from single pixels.
- **Line and outline:** One-pixel outlines in the darkest shade around sprites and important tiles.
- **Shading model:** None beyond pixel clusters of the two middle shades; at most one light and one dark shade per object.
- **Palette:** `#0f380f` `#306230` `#8bac0f` `#9bbc0f` `#cadc9f`. Exactly four olive-green shades from near-black green to pale yellow-green.
- **Lighting:** None.
- **Texture and surface:** Pixel patterns: checker dither, brick and grass tiles, 2x2 dot clusters.
- **Atmosphere and post-processing:** 160x144 output scaled by an integer factor; optional LCD pixel grid with thin gaps and slight ghosting.
- **Camera and framing:** Orthographic top-down or side view; when used in 3D, a fixed three-quarter view.
- **UI and typography:** Text boxes in the lightest shade `#cadc9f` with a one-pixel border in the darkest shade `#0f380f`, and 8x8 px tile icons such as hearts and coins. Type is an 8x8 px bitmap face in capitals. Counters use the same pixel digits in a fixed status bar at the screen edge, and a selected item is shown with its shades inverted.
- **VFX and motion:** Effects are tiny sprites of two or three frames: a star burst, a dust puff, a sword arc. A hit makes the sprite blink or invert its shades, and big events flash the whole screen by shifting all four shades. Animation uses two to four frames per cycle and moves in whole-pixel steps, so it reads as snappy.

## Fits

- **Genres:** `rpg`, `puzzle`, `action-adventure`, `platformer`, `roguelike`, `exploration`
- **Moods:** cosy, nostalgic, simple
- **Settings:** island village, monster-filled routes and towns, tile dungeon, falling-block well

## Unity recipe

### Assets

Everything is authored on an 8 or 16 px grid. The simplest route is 2D: tiles and 16x16 sprites painted by script or taken from a CC0 pixel pack and remapped to four shades. For a 3D game, use simple models and let the post pass reduce them, but design shapes to read at 160x144: large heads, thick features. All textures use point filtering, no mipmaps and no compression. Generate checker-dither, brick and grass tile patterns by script.

### Materials

Sprites and tiles use `Universal Render Pipeline/Unlit` with textures already limited to four grey levels. For 3D models write `Style/FourShade`: `UniversalForward` computes one flat lit or unlit value per object region from `_BaseColor` and a single `step` on NdotL (at most one light and one dark shade per object), outputs greyscale; `DepthOnly` and `DepthNormals` passes support the one-pixel outline. No shadows, no specular.

### Lighting and atmosphere

None. One directional light only as a direction for the step. Shadows off, flat ambient, no fog, no probes, no SSAO. The background is the lightest shade.

### Post-processing

Render to a 160x144 `RenderTexture` with point filtering. A fullscreen pass on that target: draw a one-pixel outline in the darkest shade from depth edges, quantise luminance to four levels (a 2x2 ordered dither may be used between the two middle shades), then map the four levels to the palette greens, from `#0f380f` (darkest) through `#306230` and `#8bac0f` to `#cadc9f` (lightest). Upscale by the largest integer factor that fits and centre it, with bars in the darkest shade. An optional final pass draws thin LCD gaps between pixels and blends 20 to 30 percent of the previous frame for ghosting. Tonemapping None, HDR off, no anti-aliasing.

### UI and effects

Draw UI into the same low-resolution target so it shares the pixel grid. Text boxes in `#cadc9f` with a one-pixel `#0f380f` border; 8x8 tile icons. Font asset from an 8x8 pixel face such as Press Start 2P, raster mode, capitals. A fixed status bar holds counters; selection inverts the shades. Effects are two- or three-frame sprites; hits blink or invert the sprite, and big events shift the whole four-shade mapping for a few frames. Move objects in whole low-resolution pixels.

## Do / Do not

Do:

- Output exactly four green shades.
- Render at 160x144 with integer scaling.
- Align everything to an 8 px grid.
- Outline sprites in the darkest shade.

Do not:

- Do not use cyan, magenta and white; that reads as `039`.
- Do not use only two values with dense dither; that reads as `041`.
- Do not use more colours per tile; that reads as `042`.
- Do not smooth or filter the upscale.

## Nearest styles

- `039` CGA four-colour: this style is one soft olive-green hue from dark to pale; `039` is harsh bright cyan, magenta and white on black.
- `041` One-bit dither: this style has four shades and uses the two middle ones as flat fills; `041` has only a dark and a light value, so every midtone is a dense dither pattern.
- `042` NES 8-bit tile: every tile and sprite here shares the same four greens; `042` mixes many vivid colours on one screen, such as red, blue, green and orange on a sky-blue or black background.

# Low-res sprite 2.5D shooter

Reference works: Doom (1993).

## References

- *Doom* (1993), id Software, video game. https://en.wikipedia.org/wiki/Doom_(1993_video_game)
- *Wolfenstein 3D* (1992), id Software, video game. https://en.wikipedia.org/wiki/Wolfenstein_3D
- *Duke Nukem 3D* (1996), 3D Realms, video game. https://en.wikipedia.org/wiki/Duke_Nukem_3D
- *Heretic* (1994), Raven Software, video game. https://en.wikipedia.org/wiki/Heretic_(video_game)

## Visual definition

- **Shape language and proportions:** Levels are extruded 2D floor plans: vertical walls, flat floors and ceilings at different heights, no sloped surfaces. Enemies, items and decorations are flat sprites that always face the camera.
- **Line and outline:** No outline.
- **Shading model:** Sector-based light levels plus distance darkening in discrete steps through a colour map. No dynamic shading on surfaces.
- **Palette:** `#1b1b1b` `#6b4f2f` `#8f8f8f` `#a32020` `#3f5f2f` `#c8a060` `#2f3f6f` `#ff7b00`. A fixed 256-colour palette heavy in browns, greys, reds and greens.
- **Lighting:** Each room has one light level; some sectors flicker or pulse. Darkness increases with distance in visible bands.
- **Texture and surface:** 64x64 px wall and floor textures, unfiltered: tech panels, brick, metal, slime. Sprites are pixel art with 8 view angles.
- **Atmosphere and post-processing:** 320x200 output stretched to 4:3, nearest upscale, colours snapped to the palette.
- **Camera and framing:** First-person at fixed eye height, 90 degree horizontal field of view, no pitch.
- **UI and typography:** A wide status bar across the bottom built from bevelled grey-metal pixel panels, with a face portrait in the centre that reacts to damage, key-card icons, and the weapon sprite held at bottom centre. Health, armour and ammo are chunky pixel digits in red `#a32020` with a dark drop shadow; messages are small red pixel capitals.
- **VFX and motion:** Muzzle flashes are two-frame sprite overlays that brighten the room for an instant; projectiles are glowing sprite fireballs, and blood and bullet puffs are sprites of three or four frames. Damage tints the screen red and a pick-up tints it yellow. Enemies move in few-frame sprite cycles, and the player glides fast with a bobbing weapon.

## Fits

- **Genres:** `fps`, `survival-horror`, `roguelike`, `exploration`
- **Moods:** aggressive, grim, tense
- **Settings:** Mars research base, hell dimension, medieval crypt, seedy city streets

## Unity recipe

### Assets

Levels are extruded floor plans: vertical walls, flat floors and ceilings at different heights, no slopes. Build them from a 2D sector map with the Mesh API. Textures are 64x64 px, point filtered, uncompressed, no mipmaps: tech panels, brick, metal, slime, painted by script or reduced from CC0 sources and snapped to a fixed 256-colour palette. Enemies, items and decorations are billboard sprites with eight view angles: render them from 3D models with an editor step camera at low resolution, or draw them.

### Materials

Write `Style/SectorLit`. It ignores Unity lights: `UniversalForward` reads a per-sector light level from vertex colour (or a property block), subtracts a distance term quantised in steps (`floor(viewDepth / bandSize)`), and uses the result as the row of a colour-map texture (palette index along U, 32 light levels along V), so darkening happens in visible bands and stays inside the palette. Sprites use the same shader on a quad that rotates around the Y axis to face the camera, with alpha clip and a script that picks the frame for the view angle. Add `DepthOnly`. No shadows, no specular.

### Lighting and atmosphere

No lights. A script animates sector light levels for flicker and pulse. Shadows off, no fog component (the colour map handles distance), no SSAO, no probes. Sky is a flat panoramic texture that scrolls with yaw.

### Post-processing

Render to 320x200 with point filtering and stretch to 4:3. A fullscreen pass on the low-resolution target snaps every pixel to the nearest palette entry through a 3D lookup texture built by script. Damage and pick-up tints are palette blends toward red or yellow applied in the same pass. Tonemapping None, HDR off, no anti-aliasing or Bloom.

### UI and effects

A wide status bar across the bottom built from bevelled grey-metal pixel panels, with a face portrait that changes with health, key-card icons and the weapon sprite at bottom centre, bobbing with movement. Digits are chunky pixel numerals in `#a32020` with a dark drop shadow; make a TextMeshPro sprite asset from drawn digits, and use a small pixel face such as Silkscreen for messages. Muzzle flashes are two-frame overlays that raise the current sector light level for an instant; fireballs, blood and bullet puffs are three- or four-frame sprites.

## Do / Do not

Do:

- Keep walls vertical and floors flat.
- Use camera-facing sprites for all characters and items.
- Darken with distance in discrete steps.
- Snap output to a fixed 256-colour palette.

Do not:

- Do not use polygonal characters and vertex wobble; that reads as `036`.
- Do not use sprites in a tilt-shift diorama with bloom; that reads as `047`.
- Do not use cube voxels; that reads as `044`.
- Do not allow camera pitch or sloped floors.

## Nearest styles

- `036` PS1 low-poly wobble: `036` has polygonal characters, wobbling vertices, fewer colours and soft light blended across each polygon; this style has flat camera-facing sprites, steady walls and light that drops in visible steps.
- `047` HD-2D pixel diorama: `047` is brighter, with dark-outlined sprites, smooth lighting, bloom and depth blur; this style is dark, with sprites that have no outline, stepped light and no glow.
- `044` Voxel block world: `044` is an open world of cubes in bright daylight; this style is dark interiors made of vertical walls and flat floors.

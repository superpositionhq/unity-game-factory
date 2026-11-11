# ASCII terminal glyph

Reference works: Rogue; Dwarf Fortress.

## References

- *Rogue* (1980), Michael Toy and Glenn Wichman, video game. https://en.wikipedia.org/wiki/Rogue_(video_game)
- *NetHack* (1987), The NetHack DevTeam, video game. https://en.wikipedia.org/wiki/NetHack
- *Dwarf Fortress* (2006), Bay 12 Games, video game. https://en.wikipedia.org/wiki/Dwarf_Fortress
- *Stone Story RPG* (2019), Martian Rex, video game. https://en.wikipedia.org/wiki/Stone_Story_RPG

## Visual definition

- **Shape language and proportions:** The image is a grid of text characters. Forms appear only through which glyph occupies each cell; resolution is about 80 to 160 columns.
- **Line and outline:** No outline as such. Edges can be suggested with directional glyphs: slash, backslash, bar, underscore.
- **Shading model:** Brightness maps to glyph density through a fixed ramp (space, dot, colon, dash, equals, plus, star, hash, percent, at-sign).
- **Palette:** `#000000` `#33ff33` `#00aa00` `#ffb000` `#c0c0c0` `#ffffff`. One phosphor colour (green or amber) on black, or the 16-colour terminal set used sparingly.
- **Lighting:** A simple strong light so the ramp has range.
- **Texture and surface:** The glyph grid itself. Every cell is high-frequency.
- **Atmosphere and post-processing:** Fixed monospace cell grid, optional CRT glow and scanlines.
- **Camera and framing:** Any; static or slow, since cells flicker when the image changes.
- **UI and typography:** Frames are built from box-drawing characters, menus are text lists with the selected row shown in inverted cells, and icons are single glyphs: an at-sign for the player, letters for monsters, punctuation for items. All text uses the same monospace terminal face as the scene, with stats on a status line as plain digits. The UI stays in the phosphor colour, with amber `#ffb000` or white for alerts.
- **VFX and motion:** Effects are glyph swaps: asterisks for an explosion, a run of dashes or slashes for a projectile, a cell that flashes inverted when hit. Movement goes cell by cell in discrete steps with no in-between frames.

## Fits

- **Genres:** `roguelike`, `rpg`, `simulation`, `strategy`, `puzzle`, `survival-craft`
- **Moods:** austere, cryptic, nostalgic
- **Settings:** dungeon depths, underground fortress, mainframe terminal

## Unity recipe

### Assets

Any simple, clearly lit 3D scene can feed this style, because the final image is a glyph grid; use bold shapes with strong value contrast and avoid fine detail, which turns to noise at 80 to 160 columns. Alternatively run the game as a pure cell grid with no 3D scene. Build by script a glyph atlas texture: the ramp characters (space, dot, colon, dash, equals, plus, star, hash, percent, at-sign) plus slash, backslash, bar and underscore, rendered from a monospace font into equal cells, point filtered.

### Materials

Scene objects use `Universal Render Pipeline/Simple Lit` or Lit with plain grey or simply coloured albedo; they exist only to produce brightness. Objects must write to the normals texture if edge glyphs are used, which the built-in shaders already do through `DepthNormals`. The important shader is the fullscreen one.

### Lighting and atmosphere

One strong directional light with shadows so the brightness ramp has range, plus low ambient. No fog, or black fog to fade distance into empty cells. No SSAO.

### Post-processing

A Full Screen Pass Renderer Feature after post-processing, requiring colour, depth and normals. Per screen pixel: find its cell (cell size chosen so the screen holds 80 to 160 columns of a fixed-aspect monospace cell), sample scene luminance at the cell centre, pick a glyph index from the ten-step ramp, and sample the glyph atlas at the pixel's position inside the cell. Where a depth or normal edge crosses the cell, replace the ramp glyph with a directional one chosen from the edge angle. Output the glyph in the phosphor colour (`#33ff33` or `#ffb000`) on black; an optional mode quantises scene hue to the 16-colour terminal set. Follow with Bloom at low threshold for CRT glow and an optional scanline pass. Disable anti-aliasing; render scale 1.

### UI and effects

Build UI on the same cell grid: frames from box-drawing characters, menus as text lists with the selected row inverted, single-glyph icons. Use one monospace terminal face for everything, for example VT323 or IBM Plex Mono, as a TextMeshPro asset with the font size locked to the cell height. Stats sit on a status line; alerts in amber or white. Effects are glyph swaps written into an overlay cell buffer: asterisks for explosions, dashes or slashes for projectiles, an inverted cell on hit. Move entities one cell per step.

## Do / Do not

Do:

- Map brightness to a density-sorted glyph ramp.
- Keep a fixed monospace cell grid.
- Use one phosphor colour on black.
- Use directional glyphs on strong edges.

Do not:

- Do not use dots or pixels in place of glyphs; that reads as `041`.
- Do not draw continuous vector lines; that reads as `040`.
- Do not use cells so small that glyphs cannot be read.
- Do not anti-alias the scene across cell borders.

## Nearest styles

- `040` Vector display glow: `040` draws clean continuous glowing lines on empty black; this style fills the screen with a busy grid of text characters.
- `041` One-bit dither: `041` is a neutral two-value pixel dither; this style builds tone from readable characters in phosphor green or amber, with several density steps.
- `088` Neon grid cyberspace: `088` has smooth dark surfaces crossed by neon grid lines; this style has no smooth surfaces, because every cell holds a glyph.

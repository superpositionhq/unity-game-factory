# Flat-shape ocean toon

Reference works: The Legend of Zelda: The Wind Waker.

## References

- *The Legend of Zelda: The Wind Waker* (2002), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_The_Wind_Waker
- *The Legend of Zelda: Phantom Hourglass* (2007), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Phantom_Hourglass
- *The Legend of Zelda: Spirit Tracks* (2009), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Spirit_Tracks
- *Oceanhorn: Monster of Uncharted Seas* (2013), Cornfox & Bros., video game. https://en.wikipedia.org/wiki/Oceanhorn:_Monster_of_Uncharted_Seas

## Visual definition

- **Shape language and proportions:** Strong caricature: large heads, large eyes, short limbs. Objects are reduced to a few bold shapes with sharp tapered points (wave crests, flames, smoke curls).
- **Line and outline:** No outlines. Shapes separate by colour contrast alone.
- **Shading model:** Two bands with a razor-sharp boundary. No specular, no gradient inside a band.
- **Palette:** `#1f8fd6` `#6fd0f0` `#ffffff` `#5cc04a` `#f2d15c` `#e8553d` `#2a5e2e`. Saturated sea blue, white, grass green and a few warm accents. Shadows are a darker, more saturated version of the base colour.
- **Lighting:** One sun; the terminator is the only shading feature. Cast shadows are simple dark blobs.
- **Texture and surface:** Almost none. Surfaces are flat colour, with at most a few large painted shapes (a stripe, a swirl).
- **Atmosphere and post-processing:** None apart from clear sky gradient. Effects (smoke, explosions, water foam) are solid white or coloured stylised shapes.
- **Camera and framing:** Medium-wide, slightly above the character, bright horizon line visible.
- **UI and typography:** Chunky rounded panels and buttons in flat sea blue and white, with no border line or bevel. Icons are bold two-colour shapes and text is a friendly rounded bold sans. Counters are large white numerals on a flat dark-blue backing shape.
- **VFX and motion:** Smoke is solid curling swirls, explosions are flat star and ring shapes in white, yellow and red, and defeated enemies burst into a puff of coloured cloud. Animation is bouncy, with strong squash and stretch and big readable expressions.

## Fits

- **Genres:** `action-adventure`, `exploration`, `platformer`, `puzzle`, `tower-defense`
- **Moods:** cheerful, breezy, playful
- **Settings:** island archipelago, open sea, seaside village

## Unity recipe

### Assets

Use cartoon packs with big heads and short limbs, or build props from scratch: this style needs few polygons but deliberate shapes. Model wave crests, flames and smoke curls as solid meshes with tapered points in Blender background mode. On store assets, delete every texture except at most one mask; assign one palette colour per material slot, or bake colours to vertex colour in an editor step. Recalculate normals with a high smoothing angle so the shadow edge runs as one clean curve.

### Materials

Write `Style/FlatToon`, an unlit-style shader with one light term. `UniversalForward` calls `GetMainLight(shadowCoord)` and uses `step(0, NdotL) * step(0.5, shadowAttenuation)`: a razor-sharp two-band split with no gradient inside a band. Each material exposes `_BaseColor` and `_ShadeColor`; the editor step derives the shade colour by lowering value and raising saturation, never by adding black. No specular, no rim, no ambient probe term, no outline pass. Add `ShadowCaster` and `DepthOnly`; `DepthNormals` is not needed because no effect reads normals. Water is the same shader with a scrolling mask that prints white foam shapes with a hard `step`.

### Lighting and atmosphere

One realtime directional light with hard shadows; turn soft shadows off and raise the main light shadow resolution to 4096 so the edge stays crisp, two cascades. Fog off: the air is clear. The sky is a two-colour vertical gradient from a small unlit skybox shader or a gradient dome mesh. No SSAO, no reflection probes, no baked lighting.

### Post-processing

Almost none. Tonemapping set to None so palette colours reach the screen unchanged; no Bloom, grain or vignette. Use MSAA 4x or 8x for clean shape edges, render scale 1; HDR can be off.

### UI and effects

Create the TextMeshPro font asset from a rounded bold sans such as Fredoka Bold. Panels and buttons are flat rounded sprites in `#1f8fd6` and white with no border and no bevel; counters are large white numerals on a dark-blue backing shape. Effects are meshes or hard alpha-clipped sprites, never soft particles: smoke as solid swirls that scale up and shrink out, explosions as flat star and ring shapes in white, `#f2d15c` and `#e8553d`, defeated enemies as a puff of coloured cloud. Drive squash and stretch with scale curves.

## Do / Do not

Do:

- Keep the band boundary one pixel sharp.
- Use colour contrast to separate shapes.
- Make effects from solid stylised shapes.
- Keep shadows saturated, not grey.

Do not:

- Do not add outlines; that reads as `015` or `004`.
- Do not add painted gradients or haze; that reads as `002`.
- Do not use smooth Lambert shading; that reads as `037`.
- Do not add blocky patterned stickers on boxy shapes; that reads as `067`.

## Nearest styles

- `002` Painterly open-air cel: this style keeps each surface one flat vivid colour under clear air; `002` paints soft gradients and brush patches and fades distance into pale blue haze.
- `067` Boxy toybox low-poly: this style has smooth rounded caricature forms with two sharp tone steps and almost no surface pattern; `067` builds everything from boxes and covers them with stripes, dots and labels in many more colours.
- `015` Two-tone fighting-anime cel: this style has no line at all and separates shapes by colour; `015` inks every silhouette in black and adds hard highlight shapes on hair and metal.

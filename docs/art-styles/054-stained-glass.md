# Stained glass

Reference works: Chartres Cathedral; Sainte-Chapelle.

## References

- *Stained glass windows of Chartres Cathedral* (c. 1205-1240), Chartres workshops, stained glass. https://en.wikipedia.org/wiki/Chartres_Cathedral
- *Sainte-Chapelle windows* (1248), Parisian workshops, stained glass. https://en.wikipedia.org/wiki/Sainte-Chapelle
- *Tiffany lamp* (1895), Tiffany Studios (Louis Comfort Tiffany and Clara Driscoll), leaded glass lamps. https://en.wikipedia.org/wiki/Tiffany_lamp
- *Beauty and the Beast (prologue windows)* (1991), Walt Disney Feature Animation, animated film. https://en.wikipedia.org/wiki/Beauty_and_the_Beast_(1991_film)

## Visual definition

- **Shape language and proportions:** Images are divided into cells of coloured glass, each a simple convex or gently curved piece. Figures are stiff and frontal, with forms simplified to fit the cell layout. In 3D, objects are faceted shells of glass panes.
- **Line and outline:** Thick black lead lines (came) between all pieces, of even width, plus thicker iron bars across large windows.
- **Shading model:** None from scene lighting. Each pane is a single glowing colour with internal variation; fine detail is painted in dark enamel.
- **Palette:** `#0d0d10` `#1e3fae` `#c21f2b` `#e8b21a` `#1f8a4c` `#7a2fa0` `#f2e6c2`. Deep ruby red and cobalt blue dominate, with gold, green and violet; all seen against black.
- **Lighting:** Back-lit: the glass is the light source. The surroundings are dark, with coloured light patches cast on nearby surfaces.
- **Texture and surface:** Glass streaks, bubbles and ripples inside each pane; dark painted trace lines for faces and folds.
- **Atmosphere and post-processing:** Glow around bright panes; dark vignette.
- **Camera and framing:** Frontal for windows; for 3D objects, any angle with a dark background.
- **UI and typography:** Panels are leaded window frames: black lead borders around panes of ruby, cobalt and gold glass, with icons set in small roundels. Type is a heavy gothic blackletter or uncial capital, painted in dark enamel on a pale pane or cut as glowing gold glass. Numbers glow gold against black.
- **VFX and motion:** Hits shatter panes into coloured shards with a flash of white light. Effects are shafts of coloured light, glowing dust motes and light patches that sweep across dark floors. Figures move stiffly from pose to pose, like panes sliding inside their lead lines, and the glow pulses slowly.

## Fits

- **Genres:** `puzzle`, `action-adventure`, `platformer`, `rpg`, `exploration`, `soulslike`
- **Moods:** solemn, mystical, radiant
- **Settings:** gothic cathedral, medieval kingdom, enchanted castle

## Unity recipe

### Assets

Build windows and objects from scratch: an editor step divides an image or a surface into convex cells (Voronoi relaxed toward the drawing's contours), extrudes thick black lead strips between them and thicker iron bars across large windows. In 3D, objects are faceted shells: decimate a model to large facets, turn each facet into a pane and each edge into a lead strip. Generate a glass texture by script with streaks, bubbles and ripples, and dark enamel trace lines for faces and folds. One colour per pane.

### Materials

Panes use an unlit emissive shader, `Style/GlassPane`: `UniversalForward` outputs `_BaseColor` times the streak texture as HDR emission (intensity 1.5 to 3), darkened by the enamel line texture, with a slight view-dependent brightness shift so panes shimmer as the camera moves. It does not read scene lights. Lead and iron use `Universal Render Pipeline/Unlit` in `#0d0d10`, or Lit with low smoothness if a faint edge highlight is wanted. Add `DepthOnly` passes; panes cast no shadows. Surrounding stone uses dark Lit materials.

### Lighting and atmosphere

The glass is the light. The surroundings are dark with near-black ambient. Coloured light patches on floors come from spot lights placed behind windows, each with a light cookie rendered from that window's pane layout (URP supports coloured cookies on spot lights), or from projected decals. Shafts of coloured light are additive cone or slab meshes tinted per pane group. No directional light indoors. Faint dark fog. No SSAO.

### Post-processing

Bloom with threshold 1, moderate intensity and medium scatter gives the glow around bright panes without washing out the lead lines. Vignette 0.45 in black. Neutral tonemapping to keep ruby and cobalt saturated. HDR on, MSAA 4x so lead lines stay even.

### UI and effects

Panels are leaded frames: black borders around ruby, cobalt and gold panes, icons in small roundels. Font asset from a heavy blackletter such as UnifrakturCook or an uncial such as Uncial Antiqua, either dark on a pale pane or gold with the TextMeshPro glow option. Numbers glow gold on black. Hits shatter panes into pre-cut coloured shards with a white flash. Add glowing dust motes inside light shafts and a slow sinusoidal pulse on pane emission. Figures move pose to pose with stepped interpolation.

## Do / Do not

Do:

- Separate every colour area with a black lead line.
- Make panes self-lit against a dark surround.
- Use deep red and blue as the main colours.
- Add streak and bubble variation inside panes.

Do not:

- Do not use small square pieces with light grout and surface shading; that reads as `055`.
- Do not use opaque flat fills with black bars on white; that reads as `079`.
- Do not use thin curving outlines with pastel fills; that reads as `083`.
- Do not light the glass from the front.

## Nearest styles

- `079` Primary grid neoplasticism: this style glows in deep ruby and cobalt against a black surround; `079` is mostly white, with a few flat opaque blocks of red, blue and yellow between straight black bars.
- `055` Mosaic tessera: here large panes of one glowing colour are each fully enclosed by thick black lead and lit from behind; `055` is thousands of tiny tiles with thin grout, lit from the front, with tones stepped across each form.
- `086` Insular illuminated manuscript: this style uses large plain panes of glowing colour; `086` packs a painted vellum page with fine knotwork and interlace, with no backlight.

# Flat-shaded early polygon

Reference works: Star Fox; Virtua Fighter.

## References

- *Star Fox* (1993), Nintendo EAD and Argonaut Software, video game. https://en.wikipedia.org/wiki/Star_Fox_(1993_video_game)
- *Virtua Fighter* (1993), Sega AM2, arcade video game. https://en.wikipedia.org/wiki/Virtua_Fighter_(video_game)
- *Another World* (1991), Eric Chahi (Delphine Software), video game. https://en.wikipedia.org/wiki/Another_World_(video_game)
- *Virtua Racing* (1992), Sega AM2, arcade video game. https://en.wikipedia.org/wiki/Virtua_Racing
- *Alone in the Dark* (1992), Infogrames, video game. https://en.wikipedia.org/wiki/Alone_in_the_Dark_(1992_video_game)

## Visual definition

- **Shape language and proportions:** Very low polygon counts (20 to 300 polygons per object) with large flat facets. Shapes are angular abstractions: wedge ships, box buildings, prism figures.
- **Line and outline:** No outline. Facet edges are visible only as colour changes.
- **Shading model:** Flat shading: one colour per polygon, brightness from the facet's angle to the light. No interpolation, no textures.
- **Palette:** `#1c2a6b` `#3e6fd1` `#c8322b` `#e8b83a` `#8f9aa8` `#2e8b57` `#f0f0f0`. Solid saturated colours per object part (blue, red, yellow, grey) on a simple two-colour sky and ground.
- **Lighting:** One directional light; no shadows.
- **Texture and surface:** None.
- **Atmosphere and post-processing:** Low resolution (about 256x224 or 320x200) with hard pixel edges; no filtering.
- **Camera and framing:** Behind-the-ship or side-on views with a 60 degree field of view.
- **UI and typography:** A sparse arcade overlay: thin single-colour bars for shield, boost and health, flat-polygon or wireframe icons, no panel textures. Text is blocky bitmap capitals or a slanted arcade sans, with large digits for lap time, speed and score in white, yellow `#e8b83a` and red `#c8322b`.
- **VFX and motion:** Explosions are bursts of flat-coloured triangles and spinning polygon shards; lasers are solid coloured bars, and a hit flashes the whole object white for a frame. Figures move stiffly on rigid limb segments at 15 to 20 frames per second, while the ground and scenery rush past the camera.

## Fits

- **Genres:** `vehicle-combat`, `racing`, `fighting`, `action-adventure`, `platformer`
- **Moods:** retro, brisk, abstract
- **Settings:** space battle corridor, race circuit, alien planet, fighting arena

## Unity recipe

### Assets

Very low polygon counts with large flat facets: 20 to 300 polygons per object. Build wedge ships, box buildings and prism figures from scratch with the Mesh API, or decimate store models hard. No textures at all. Split vertices so every polygon has its own normal (set the model importer's smoothing angle to 0, or duplicate vertices in the editor step). Colour is one solid saturated value per object part, stored in vertex colour or one material per colour.

### Materials

Write `Style/FlatFacet`. `UniversalForward` computes brightness once per face: with split vertices the vertex-stage Lambert term from `GetMainLight()` is already constant across the polygon; mark the interpolator `nointerpolation` to guarantee it. Output `baseColor * (ambient + NdotL * strength)` quantised to a small number of levels (8 to 16) to suggest limited colour depth. No textures, no specular, no shadow receiving. Add `DepthOnly`; no `ShadowCaster`.

### Lighting and atmosphere

One directional light, shadows disabled in the URP asset. Flat ambient. No fog or a hard near-black cut-off at the far clip plane. Sky and ground are two flat colours: a plain unlit skybox with a hard horizon, and a single flat ground plane. No SSAO, no probes.

### Post-processing

Render at about 320x200 or 256x224 with a low-resolution `RenderTexture` and point upscaling, so polygon edges are hard jagged steps. No anti-aliasing, no filtering, no Bloom, no dither pass. Tonemapping None, HDR off. Optionally cap the frame rate or step object animation at 15 to 20 updates per second while the camera and scenery move at full rate.

### UI and effects

A sparse arcade overlay: thin single-colour bars for shield, boost and health, flat-polygon or wireframe icons, no panel textures. Font asset from blocky bitmap capitals such as Silkscreen or a slanted arcade face such as Russo One set italic, with large digits for lap time, speed and score in white, `#e8b83a` and `#c8322b`. Explosions are mesh particles: flat-coloured triangles and spinning shards with the same facet shader. Lasers are solid coloured bars. A hit swaps the object's colour to white for one frame.

## Do / Do not

Do:

- Use one flat colour per polygon.
- Keep polygon counts very low.
- Render at low resolution without filtering.
- Use a simple two-colour sky and ground.

Do not:

- Do not add textures, even tiny ones; that reads as `036`.
- Do not raise polygon counts and use soft pastel gradients; that reads as `066`.
- Do not draw only edges; that reads as `040`.
- Do not smooth-shade.

## Nearest styles

- `066` Faceted low-poly gradient: `066` is bright and soft, with many small facets, pastel gradients and smooth edges; this style is darker, with a few large facets, solid colours and hard jagged pixels.
- `036` PS1 low-poly wobble: `036` covers its polygons with small pixelated textures that warp and wobble; this style has no textures, only one flat colour per polygon.
- `063` White-and-red faceted minimal: `063` is almost all white with a few red accents; this style puts strong blue, red and yellow on every object.

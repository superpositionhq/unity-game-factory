# White city with primary accents

Reference works: Mirror's Edge.

## References

- *Mirror's Edge* (2008), DICE, video game. https://en.wikipedia.org/wiki/Mirror's_Edge
- *Mirror's Edge Catalyst* (2016), DICE, video game. https://en.wikipedia.org/wiki/Mirror's_Edge_Catalyst
- *Portal* (2007), Valve, video game. https://en.wikipedia.org/wiki/Portal_(video_game)
- *Playtime* (1967), Jacques Tati, live-action film. https://en.wikipedia.org/wiki/Playtime

## Visual definition

- **Shape language and proportions:** Clean modern architecture: flat roofs, glass towers, ducts, railings, scaffolds and cranes. Simple orthogonal volumes with a few diagonal pipes.
- **Line and outline:** No outline.
- **Shading model:** Smooth, with soft global-illumination-like colour bleeding: coloured objects tint nearby white surfaces.
- **Palette:** `#ffffff` `#e9edf0` `#e2231a` `#f7a800` `#1f7ae0` `#2bb673` `#9aa4ad`. Overexposed white on almost every surface, with single-hue accents: one saturated red, orange, blue or green per area.
- **Lighting:** Very bright clear daylight, slightly overexposed; soft blue sky fill in shadows.
- **Texture and surface:** Nearly none. Clean painted concrete and metal with faint panel joints.
- **Atmosphere and post-processing:** High exposure, bloom on sky and white surfaces, light blue tint in shadows.
- **Camera and framing:** First-person, 90 degree field of view, rooftop vistas with deep perspective.
- **UI and typography:** Almost invisible: thin hairlines, wide white space and small flat pictograms like wayfinding signs. Type is a clean geometric sans in light weights, with large thin numerals for timers and speed. Text is cool grey `#9aa4ad` on white, and the key red `#e2231a` marks objectives and the route ahead.
- **VFX and motion:** Few particles: soft white bloom flashes, small dust puffs on landing and glass shards that catch the light, with no smoke or grime. Motion is fluid and driven by momentum, with realistic body weight, camera bob and roll on landings; objective objects pulse red.

## Fits

- **Genres:** `platformer`, `fps`, `action-adventure`, `puzzle`, `racing`, `exploration`
- **Moods:** clean, airy, kinetic
- **Settings:** rooftop cityscape, glass corporate towers, sterile test facility, modernist plaza

## Unity recipe

### Assets

Modern city and rooftop packs: flat roofs, glass towers, ducts, railings, scaffolds, cranes. Simple orthogonal volumes are also quick to build with ProBuilder's API. Remove all albedo textures and set surfaces to near-white; keep only a faint panel-joint normal map at low strength. In each area, choose one accent hue and paint it on a few whole objects (a pipe run, a door, a crane) as a pure saturated colour. Objective objects are always `#e2231a`.

### Materials

`Universal Render Pipeline/Lit` with `_BaseColor` white or `#e9edf0`, smoothness 0.2 to 0.4, no metallic, normal strength about 0.3. Accent materials are saturated Lit colours; they must be marked static and included in the bake, because their bounce light on white is the style. Glass uses transparent Lit with high smoothness and a pale blue tint. Use the `Meta` pass (already in Lit) and, if needed, raise the albedo boost in the lightmap parameters so accents bleed more. Pulsing objectives animate `_EmissionColor` in red.

### Lighting and atmosphere

Baked global illumination carries this style. One mixed directional sun at high intensity with soft shadows; bake lightmaps for static architecture and Adaptive Probe Volumes for dynamic objects, with several indirect bounces and indirect intensity above 1. Sky fill comes from a pale blue skybox so shadows turn blue. Four cascades, 150 m. SSAO on at low intensity. Baked reflection probes for glass. No fog, or a very faint white haze.

### Post-processing

Overexpose on purpose: Color Adjustments post exposure +0.7 to +1, Neutral tonemapping so whites clip softly. Bloom with threshold 1, moderate intensity and high scatter on sky and white walls. Shadows Midtones Highlights with a light blue tint in shadows. No grain, vignette or outline. TAA or MSAA 4x; HDR on.

### UI and effects

Nearly invisible UI: hairlines, wide empty space and small flat pictograms like wayfinding signs. Font asset from a light geometric sans such as Jost Light or Inter Thin, with large thin numerals for timers and speed, in `#9aa4ad` on white; the key red marks objectives and the route. Effects are few: soft white additive flashes, small dust puffs on landing, glass shards as mesh particles with high smoothness that catch the sun. No smoke or grime.

## Do / Do not

Do:

- Keep almost every surface white.
- Use one pure accent hue per area.
- Tint shadows pale blue and overexpose slightly.
- Let accent colours bleed onto nearby white.

Do not:

- Do not use faceted flat shading with only red; that reads as `063`.
- Do not move indoors with curved moulded panels and no accent colour; that reads as `091`.
- Do not add grime or weathering.
- Do not use raw grey concrete with heavy texture; that reads as `097`.

## Nearest styles

- `063` White-and-red faceted minimal: this style has smooth shaded surfaces with red, orange, blue and green accents that tint the white around them; `063` has faceted crystalline figures and uses only red and black against white.
- `091` Clinical white space-age: this style is outdoor rooftops blown out by daylight, with blue-tinted shadows and bold accent blocks; `091` is indoor curved, padded panels lit evenly by built-in strips, with visible seams and almost no colour.
- `097` Brutalist concrete: this style has clean white painted surfaces with almost no surface marks; `097` is mid-grey raw concrete with plank imprints and rain streaks.

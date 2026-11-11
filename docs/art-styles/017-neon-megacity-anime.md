# Neon megacity 1980s anime

Reference works: Akira.

## References

- *Akira* (1988), Tokyo Movie Shinsha (Katsuhiro Otomo), animated film. https://en.wikipedia.org/wiki/Akira_(1988_film)
- *Ghost in the Shell* (1995), Production I.G (Mamoru Oshii), animated film. https://en.wikipedia.org/wiki/Ghost_in_the_Shell_(1995_film)
- *Bubblegum Crisis* (1987), AIC and Artmic, original video animation. https://en.wikipedia.org/wiki/Bubblegum_Crisis
- *Cyberpunk: Edgerunners* (2022), Studio Trigger, animated TV series. https://en.wikipedia.org/wiki/Cyberpunk:_Edgerunners

## Visual definition

- **Shape language and proportions:** Dense megacity: stacked towers, highways, pipes and cables, drawn with accurate perspective and mechanical detail. Vehicles are low, wide and angular.
- **Line and outline:** Thin, precise black line on all foreground objects, with drawn panel and mechanical detail.
- **Shading model:** Two or three flat cel bands on foreground objects; backgrounds are painted night scenes with thousands of lit windows.
- **Palette:** `#0a0a14` `#d7263d` `#f46036` `#2e294e` `#1b998b` `#f5d547` `#3a86ff`. Near-black blue night with red, orange and teal light; one key red object.
- **Lighting:** Night. Light comes from signs, windows, headlights and street lamps; strong coloured rim light.
- **Texture and surface:** Painted background detail: window grids, stains, signage. Light trails from moving lamps.
- **Atmosphere and post-processing:** Glow around lights, light-trail streaks, mild film grain. No modern lens effects.
- **Camera and framing:** Deep one- and three-point perspective, low angles along streets, 28 mm equivalent.
- **UI and typography:** Thin-line rectangular frames on near-black with small technical callouts, like 1980s vehicle dashboards and video monitors. Text is a bold condensed sans in capitals, with blocky segmented digits for speed, time and ammunition counters. UI colours are red and orange on black with teal for secondary readouts; warnings blink in yellow.
- **VFX and motion:** Long red and white light trails behind lamps, hand-drawn explosions built from layered flat orange and yellow shapes, drawn smoke plumes, debris chunks and spark showers. Animation is detailed and weighty with fast cuts; vehicles lean and skid with drawn motion streaks.

## Fits

- **Genres:** `racing`, `vehicle-combat`, `third-person-shooter`, `action-adventure`, `detective-mystery`, `stealth`
- **Moods:** tense, rebellious, frenetic
- **Settings:** neon megacity at night, elevated highway, back-alley market, military research complex

## Unity recipe

### Assets

Dense sci-fi city packs: towers, highways, pipes, cables, low angular vehicles. Foreground objects lose their PBR maps and get flat colours plus drawn panel detail: generate thin black line textures from the pack's normal maps with an edge filter. Backgrounds are best built from scratch: tower blocks as simple boxes with a window-grid texture made by script, where a random subset of cells is lit in warm and teal tones through an emission map. One key object per scene is red (`#d7263d`).

### Materials

Foreground: `Style/NightCel`. `UniversalForward` loops additional lights (signs and lamps are the light) and quantises the summed diffuse into two or three flat steps per light colour; add a strong coloured rim from the brightest additional light. Use Forward+ so many lights are available, and compile the matching cluster keyword with `_ADDITIONAL_LIGHTS`. Multiply by the panel-line texture. The thin precise outline is an `SRPDefaultUnlit` hull pass at about 1.5 px. Passes: `ShadowCaster`, `DepthOnly`, `DepthNormals`. Background towers use `Universal Render Pipeline/Unlit` or Lit with the emissive window map; painted stains go into albedo.

### Lighting and atmosphere

No sun and no moon light. Many small point and spot lights at signs, windows, headlights and street lamps, with shadows on only the nearest few. Ambient near-black blue (`#0a0a14`). Fog exponential in dark blue to merge towers into the night. Bake nothing; no SSAO. Reflection probes are optional and low strength.

### Post-processing

Bloom with a threshold near 1 and moderate scatter gives the glow around lights; keep it soft and round. Film Grain at low intensity. Tonemapping Neutral, slight contrast lift. Do not add Chromatic Aberration, lens flares or Depth Of Field: no modern lens effects. Light trails are made in the scene, not in post. HDR on, SMAA.

### UI and effects

Thin-line rectangular frames on near-black with small technical callouts. Bold condensed capitals from Oswald or Barlow Condensed, and a segmented-digit face for speed, time and ammunition. Red and orange on black, teal for secondary readouts, yellow warnings that blink at 2 Hz. Effects: `TrailRenderer` ribbons in red and white behind every moving lamp with long lifetimes, explosions as layered flat orange and yellow flipbook shapes, drawn smoke plumes, mesh debris chunks and spark showers with stretched billboards.

## Do / Do not

Do:

- Fill the background with lit window grids.
- Light the scene from signs and lamps, not a sun.
- Keep line thin and mechanical.
- Include one strongly red hero object.

Do not:

- Do not use smooth PBR with wet reflections and volumetric haze; that reads as `089`.
- Do not reduce the scene to emissive lines on black; that reads as `088`.
- Do not use print dots and channel offsets; that reads as `009`.
- Do not light with a sunset sky; that reads as `016`.

## Nearest styles

- `089` Rain-soaked tech-noir: `089` has no drawn line and looks filmed, with smooth shading, wet reflections and thick haze; this style has black ink lines and flat cel tones on every foreground object.
- `009` Halftone print comic: `009` looks printed on paper, with visible dot screens and lighter page tones; this style is a dark night scene of clean flat cel colour and painted lit windows.
- `016` Luminous sky anime: `016` is filled by a bright sky at low sun or twilight; this style is a black night where all light comes from signs, windows and lamps.

# Luminous sky anime

Reference works: Your Name.

## References

- *Your Name* (2016), CoMix Wave Films (Makoto Shinkai), animated film. https://en.wikipedia.org/wiki/Your_Name
- *Weathering with You* (2019), CoMix Wave Films (Makoto Shinkai), animated film. https://en.wikipedia.org/wiki/Weathering_with_You
- *5 Centimeters per Second* (2007), CoMix Wave Inc. (Makoto Shinkai), animated film. https://en.wikipedia.org/wiki/5_Centimeters_per_Second
- *The Garden of Words* (2013), CoMix Wave Films (Makoto Shinkai), animated film. https://en.wikipedia.org/wiki/The_Garden_of_Words
- *Suzume* (2022), CoMix Wave Films (Makoto Shinkai), animated film. https://en.wikipedia.org/wiki/Suzume

## Visual definition

- **Shape language and proportions:** Realistic, precisely observed modern settings: power lines, railway crossings, rooftops, wet streets. Characters are simple anime figures, small in the frame.
- **Line and outline:** Thin dark line on characters only. Scenery edges are defined by light.
- **Shading model:** Characters: two bands with a coloured rim. Scenery: painted realism with strong light gradients and bounce colour.
- **Palette:** `#1e3a8a` `#60a5fa` `#fbcfe8` `#fde68a` `#f97316` `#0f172a` `#a7f3d0` `#ffffff`. Deep blue to pink and gold twilight skies, bright lens highlights, saturated reflected colour in shadows.
- **Lighting:** Low sun or twilight with long shadows, backlight, glowing cloud edges and visible light shafts.
- **Texture and surface:** High detail in sky and reflective surfaces: layered clouds, stars, wet ground reflections, glints on glass and metal.
- **Atmosphere and post-processing:** Bloom, lens flare streaks, light shafts, slight chromatic fringe, floating dust particles.
- **Camera and framing:** Low angles that give the sky 50 to 70% of the frame; wide lens.
- **UI and typography:** Very light UI: thin white lines and frosted translucent panels that let the sky show through, with small white outline icons. Text is a thin, clean modern sans in white, like film subtitles and phone-screen messages; counters are slim white numerals with a faint glow. Accents are twilight pink or gold.
- **VFX and motion:** Drifting dust motes, rain streaks, falling petals, lens flare streaks and slow meteor trails with glowing tails. Impacts are soft bursts of light and ripples on wet ground, not hard flashes. Characters animate on twos with restrained natural movement while clouds, light shafts and reflections move smoothly.

## Fits

- **Genres:** `exploration`, `detective-mystery`, `puzzle`, `simulation`, `racing`
- **Moods:** wistful, romantic, hopeful
- **Settings:** modern Tokyo rooftops, rural railway crossing, rain-soaked city park, lakeside mountain town

## Unity recipe

### Assets

Realistic modern-town packs: streets, railway crossings, power poles and cables, rooftops, signage. Keep their textures and normal maps; scenery here is observed realism. Raise wetness instead of stripping: add a puddle mask painted by script. Characters are simple anime models with flat colours. The sky is the main asset and should be built: several layered cloud planes or a high-resolution panoramic painted by script with layered cumulus, a low sun and stars.

### Materials

Scenery uses `Universal Render Pipeline/Lit`; in wet areas the editor step raises `_Smoothness` toward 0.9 and darkens albedo using the puddle mask. Characters use a small cel shader, `Style/TwilightCel`: two bands from `GetMainLight(shadowCoord)`, a strong coloured rim from `pow(1 - NdotV, 4)` tinted by the sky colour, and a thin dark hull line in an `SRPDefaultUnlit` pass; passes `ShadowCaster`, `DepthOnly`, `DepthNormals`. The sky uses `Skybox/Panoramic` or an unlit dome with HDR values so cloud edges exceed the bloom threshold.

### Lighting and atmosphere

A low directional sun (5 to 15 degrees) with long soft shadows, four cascades, 150 m. Skybox ambient so shadows pick up saturated blue and pink. Bake Adaptive Probe Volumes for bounce colour. Reflection probes are essential: place baked or realtime probes low over wet ground, box projected. Light shafts are additive quads or cone meshes aligned to the sun with a soft noise scroll. Fog in a twilight tint; SSAO on, low.

### Post-processing

Bloom with a low threshold (about 0.9), high scatter and a faint pink tint. Add the Screen Space Lens Flare override for streaks, and a Lens Flare (SRP) component on the sun. Slight Chromatic Aberration, ACES tonemapping, Split Toning with blue shadows and gold highlights. HDR on, SMAA or TAA. Frame low so the sky fills more than half the screen.

### UI and effects

Thin white lines and frosted translucent panels (sample a blurred copy of the camera colour, or use low-alpha white). Font asset from a thin modern sans such as Inter Light or Zen Kaku Gothic New Light, white with a faint glow through the TextMeshPro glow option. Accents in `#fbcfe8` or `#fde68a`. Particles: floating dust motes lit by the sun colour, stretched rain streaks, petals, slow meteor trails with a `TrailRenderer`, and ripple rings on wet ground instead of hard flashes.

## Do / Do not

Do:

- Give the sky at least half of the frame.
- Rim clouds and objects with sun-coloured light.
- Add reflections on wet or glossy ground.
- Use bloom and light shafts from the sun position.

Do not:

- Do not paint matte gouache backgrounds without glow; that reads as `014`.
- Do not flatten scenery into bands and gradients; that reads as `018`.
- Do not turn the scene into a black night filled with neon signs; that reads as `017`.
- Do not line the scenery.

## Nearest styles

- `014` Hand-painted pastoral anime: `014` has matte poster-colour scenery in plain daylight with no glow; this style has glowing skies, lens flares, light shafts and shining wet reflections.
- `017` Neon megacity 1980s anime: `017` is a near-black night city lit only by signs, windows and lamps; this style is lit by a bright open sky at low sun or twilight.
- `018` Soft open-world anime cel: `018` has clean, simplified scenery with smooth gradients and outlined props; this style has closely observed real places with detailed clouds, cables and reflections and no line on scenery.

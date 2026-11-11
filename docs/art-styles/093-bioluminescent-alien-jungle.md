# Bioluminescent alien jungle

Reference works: Avatar (2009).

## References

- *Avatar* (2009), James Cameron, live-action and computer-animated film. https://en.wikipedia.org/wiki/Avatar_(2009_film)
- *Avatar: The Way of Water* (2022), James Cameron, live-action and computer-animated film. https://en.wikipedia.org/wiki/Avatar:_The_Way_of_Water
- *Avatar: Frontiers of Pandora* (2023), Massive Entertainment, video game. https://en.wikipedia.org/wiki/Avatar:_Frontiers_of_Pandora
- *Subnautica* (2018), Unknown Worlds Entertainment, video game. https://en.wikipedia.org/wiki/Subnautica

## Visual definition

- **Shape language and proportions:** Dense alien jungle at night: giant trees with buttress roots, hanging vines, fan-shaped and spiral plants, mushroom caps, floating seeds like small jellyfish, moss carpets. Organic forms at many scales.
- **Line and outline:** No outline.
- **Shading model:** Realistic smooth shading in very low light, with self-illuminated patterns and soft subsurface glow in leaves.
- **Palette:** `#030812` `#0a2a3a` `#19e6c8` `#3a7bff` `#c44dff` `#7dff6a` `#ff6ad5`. Blue-black darkness with cyan, teal, violet, magenta and green bioluminescence.
- **Lighting:** No sun. Light comes from glowing dots, veins and fringes on plants and creatures; glow intensifies where things are touched. Faint blue moonlight from above.
- **Texture and surface:** Glowing vein networks and dot rows on leaves, speckled moss, wet bark; fine natural detail.
- **Atmosphere and post-processing:** Bloom, depth of field, drifting glowing particles, light mist.
- **Camera and framing:** Inside the forest at eye level looking through layered foliage; 35 mm equivalent, shallow focus.
- **UI and typography:** Thin glowing line frames and soft-edged translucent blue-black panels, with icons drawn as luminous organic glyphs (leaf, spiral, seed). Type is a light rounded sans with a faint glow. Counters are slim cyan `#19e6c8` numerals, with magenta `#ff6ad5` for damage and green `#7dff6a` for healing.
- **VFX and motion:** Drifting glowing spores, ripples of light that spread across plants where they are touched, and floating seeds that pulse; hits burst into luminous motes that fade slowly. Motion is fluid and organic: swaying fronds, gliding creatures, gentle ease in and out.

## Fits

- **Genres:** `exploration`, `survival-craft`, `action-adventure`, `stealth`, `rpg`
- **Moods:** wondrous, serene, mysterious
- **Settings:** alien jungle at night, glowing cave, deep ocean reef, forested alien moon

## Unity recipe

### Assets

Dense jungle packs with realistic detail: giant trees with buttress roots, hanging vines, fan and spiral plants, mushrooms, moss. Keep full PBR maps at high resolution; fine natural detail is part of the style. Add alien pieces from scratch: spiral plants, floating jellyfish-like seeds, large fan leaves. The key authored asset is the glow pattern: an editor step paints emission masks per plant with vein networks (branching lines along leaf UVs) and dot rows along edges, each plant family assigned one hue from cyan, teal, violet, magenta or green.

### Materials

Write `Style/BioLeaf`, built on `UniversalFragmentPBR`: normal PBR inputs with a dark albedo and wet smoothness on bark, plus emission equal to the mask times the family colour times an animated intensity. Intensity combines a slow pulse with a touch response: scripts write touch positions and times into global arrays (`Shader.SetGlobalVectorArray`), and the shader adds a ring of brightness expanding from each touch. Thin leaves add a subsurface glow: emission also leaks to the back face and is softened by a wide wrap term. Alpha-clipped, two-sided for foliage. Full Lit pass set. Floating seeds use an emissive transparent variant with Fresnel.

### Lighting and atmosphere

No sun. A faint blue directional moon light from above with soft shadows at low intensity. Most light is emissive; add small point lights at the brightest plants and creatures (Forward+), shadows off on most. Ambient blue-black `#030812`. Bake Adaptive Probe Volumes with emissive contribution for static plants. Light exponential fog in `#0a2a3a` and thin mist cards. SSAO on, medium; reflection probes at low intensity for wet bark.

### Post-processing

Bloom with threshold 1, moderate intensity and medium scatter: glow must stay tied to veins and dots, not flood the frame. Depth Of Field in Bokeh mode with moderate blur on far and very near foliage. ACES tonemapping with saturation +10 so glow hues stay vivid against true darkness. Slight Vignette. TAA, HDR on.

### UI and effects

Thin glowing line frames and soft-edged translucent blue-black panels; icons are luminous organic glyphs (leaf, spiral, seed). Font asset from a light rounded sans such as Quicksand Light or Comfortaa with the TextMeshPro glow option; slim cyan numerals, magenta `#ff6ad5` for damage, green `#7dff6a` for healing. Particles: slow drifting additive spores with noise motion and long lifetimes, pulsing floating seeds, and luminous motes on hits that fade over one to two seconds. Fronds sway in the vertex stage; creatures glide with gentle easing.

## Do / Do not

Do:

- Light the scene only from glowing plants and a faint moon.
- Put vein and dot patterns on leaves.
- Use several glow hues: cyan, violet, magenta, green.
- Add drifting glowing particles and bloom.

Do not:

- Do not simplify into soft painted shapes with a glowing hero; that reads as `027`.
- Do not use straight emissive circuit lines on geometric solids; that reads as `088`.
- Do not add urban neon signs and rain; that reads as `089`.
- Do not add daylight.

## Nearest styles

- `027` Glowing forest painterly: this style shows realistic, finely detailed plants in deep darkness with many vivid glow colours; `027` is lighter and softer, with simplified painted shapes and one glowing hero.
- `088` Neon grid cyberspace: glow here follows veins and dot rows on dense organic foliage in many hues; `088` is straight glowing lines on bare geometric solids in only a few colours.
- `089` Rain-soaked tech-noir: light here comes from plants and creatures in vivid cyan, violet and magenta; `089` is a city where neon signs reflect in wet streets, with duller colour between the lights.

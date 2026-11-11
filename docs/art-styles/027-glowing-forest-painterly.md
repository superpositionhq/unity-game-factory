# Glowing forest painterly

Reference works: Ori and the Blind Forest.

## References

- *Ori and the Blind Forest* (2015), Moon Studios, video game. https://en.wikipedia.org/wiki/Ori_and_the_Blind_Forest
- *Ori and the Will of the Wisps* (2020), Moon Studios, video game. https://en.wikipedia.org/wiki/Ori_and_the_Will_of_the_Wisps
- *Trine 2* (2011), Frozenbyte, video game. https://en.wikipedia.org/wiki/Trine_2
- *Rayman Legends* (2013), Ubisoft Montpellier, video game. https://en.wikipedia.org/wiki/Rayman_Legends

## Visual definition

- **Shape language and proportions:** Organic, twisting forest forms: gnarled roots, hanging vines, mushrooms, mossy rocks. The hero is a small, simple, glowing white figure.
- **Line and outline:** No outline. Foreground elements are dark silhouettes.
- **Shading model:** Soft painted gradients with strong glow light sources. Smooth.
- **Palette:** `#0d1b2a` `#1b4965` `#5fa8d3` `#bee9e8` `#ffd166` `#7b2cbf` `#2d6a4f` `#ffffff`. Deep blue and teal night forest with cyan, gold and violet light sources and a white-glowing hero.
- **Lighting:** Many small emissive sources (spirit lights, glowing plants) and shafts of light; strong backlight.
- **Texture and surface:** Painterly foliage and bark with soft detail; layered depth with blurred near and far planes.
- **Atmosphere and post-processing:** Heavy bloom, light shafts, floating particles, depth of field on foreground and background layers, vignette.
- **Camera and framing:** Side-on, layered parallax; medium-wide.
- **UI and typography:** Frameless UI: glowing icons and thin luminous lines laid directly over the scene, with round orbs for health and energy. Text is a light, elegant serif with a soft glow, and counters are small glowing numerals. UI colours are pale cyan `#bee9e8` and white `#ffffff`, with gold `#ffd166` for pickups.
- **VFX and motion:** Dense particles: glowing motes, drifting leaves, light trails behind the hero and soft sparkle bursts on hits. Animation is quick and fluid, with strong squash and stretch and bright arcs on jumps and dashes.

## Fits

- **Genres:** `platformer`, `exploration`, `action-adventure`, `puzzle`
- **Moods:** wondrous, bittersweet, magical
- **Settings:** enchanted night forest, glowing caverns, ancient spirit trees, misty swamps

## Unity recipe

### Assets

Organic forest packs: gnarled roots, vines, mushrooms, mossy rocks. Arrange them in side-on parallax layers. Soften textures by blurring albedo and lowering normal strength so detail is painterly. Foreground pieces become pure dark silhouettes (a black unlit material). Glowing plants get emission masks painted by script. The hero is a small simple white figure, easiest to build from scratch, with an emissive material.

### Materials

Midground scenery uses `Universal Render Pipeline/Lit` with low smoothness and emission enabled (`_EMISSION`, HDR `_EmissionColor` in cyan, gold or violet). Foreground silhouettes use `Universal Render Pipeline/Unlit` in `#0d1b2a`. The hero uses an unlit emissive shader with a Fresnel falloff so the glow is brighter at the rim. Foliage uses an alpha-clipped Lit variant with vertex sway. Light shafts are additive transparent quads with a scrolling noise mask and soft-particle depth fade (requires the depth texture in the URP asset).

### Lighting and atmosphere

Many small point lights at spirit lights and glowing plants: use Forward+ and keep shadows off on most. One dim blue directional backlight with soft shadows. Ambient deep blue. Exponential fog in `#1b4965` so far layers stay visible as blue shapes, which keeps the scene readable behind the black foreground. No baked lighting needed for a side-scroller; SSAO off.

### Post-processing

This style relies on the Volume profile. Bloom with low threshold (0.8), high intensity and high scatter. Depth Of Field in Bokeh mode focused on the gameplay plane, so near and far layers blur. Vignette at 0.35 to 0.45. Neutral or ACES tonemapping, slight saturation lift, Shadows Midtones Highlights pushing shadows toward blue. HDR on, TAA or SMAA.

### UI and effects

Frameless UI: glowing icons and thin luminous lines over the scene, round orbs for health and energy drawn with a radial-fill shader. Font asset from a light elegant serif such as Cormorant Garamond Light with the TextMeshPro glow option on, in `#bee9e8` and white; gold for pickups. Particles are dense: hundreds of additive glowing motes with noise motion, drifting leaves, a `TrailRenderer` light trail behind the hero and soft sparkle bursts on hits.

## Do / Do not

Do:

- Put a dark silhouette layer in front and blurred layers behind.
- Use many small glowing sources with strong bloom.
- Make the hero the brightest object.
- Add drifting particles and light shafts.

Do not:

- Do not use pure black silhouettes on grey fog without colour; that reads as `070`.
- Do not cover plants in neon patterns with photoreal detail; that reads as `093`.
- Do not light evenly with painted albedo detail; that reads as `023`.
- Do not add outlines.

## Nearest styles

- `093` Bioluminescent alien jungle: this style has soft painted forms, gentle glow and a visible deep-blue forest behind; `093` is almost black, with sharp realistic leaf detail and vivid neon patterns.
- `070` Silhouette fog monochrome: behind the dark foreground this style is full of colour, in deep blue, cyan, gold and violet; `070` uses only black and greys.
- `023` Chunky hand-painted fantasy: this style is dark, with glowing light sources and heavy bloom; `023` is bright and evenly lit, with detail painted onto the surfaces.

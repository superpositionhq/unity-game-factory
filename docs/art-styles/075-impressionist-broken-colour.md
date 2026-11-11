# Impressionist broken colour

Reference works: Monet.

## References

- *Impression, Sunrise* (1872), Monet, oil painting. https://en.wikipedia.org/wiki/Impression,_Sunrise
- *Water Lilies* (1896-1926), Monet, oil painting series. https://en.wikipedia.org/wiki/Water_Lilies_(Monet_series)
- *Bal du moulin de la Galette* (1876), Pierre-Auguste Renoir, oil painting. https://en.wikipedia.org/wiki/Bal_du_moulin_de_la_Galette
- *Haystacks* (1890-1891), Monet, oil painting series. https://en.wikipedia.org/wiki/Haystacks_(Monet_series)
- *Woman with a Parasol - Madame Monet and Her Son* (1875), Monet, oil painting. https://en.wikipedia.org/wiki/Woman_with_a_Parasol_–_Madame_Monet_and_Her_Son

## Visual definition

- **Shape language and proportions:** Everyday outdoor subjects: water, gardens, bridges, haystacks, figures with parasols. Forms have soft, dissolved edges; nothing is sharply bounded.
- **Line and outline:** None. Edges are transitions between dabs of colour.
- **Shading model:** Light is shown by colour temperature, not by dark shadow: sunlit areas in warm yellow-pink, shadows in blue-violet of similar brightness.
- **Palette:** `#a9c7e8` `#f4d9a0` `#e8a6b8` `#7fae7a` `#c9b6e4` `#f6f0dc` `#5f7fb5` `#e9905a`. High-key pastel colours: sky blue, lilac, pink, pale gold, fresh green. No black, no brown-black shadows.
- **Lighting:** Bright outdoor daylight, hazy sun, strong reflections on water.
- **Texture and surface:** The whole image is short, separate brush dabs (comma strokes), each a slightly different colour, with bare linen showing between. Water is horizontal dabs, foliage is multi-directional.
- **Atmosphere and post-processing:** A full-frame brush pass that rebuilds the image from dabs; slight linen weave.
- **Camera and framing:** Eye-level landscape views with a high or absent horizon; 35 to 50 mm equivalent.
- **UI and typography:** Panels are soft-edged patches of pale cream paint `#f6f0dc` with dabbed borders and no hard frames, and icons are loose brush sketches made of a few strokes. Text is a light, rounded brush-lettered hand in deep sky blue `#5f7fb5`, and numbers are painted in the same hand with warm orange `#e9905a` for highlights.
- **VFX and motion:** Particles are loose dabs of paint: petals, light sparkles on water, drifting pollen and mist. Impacts are soft bursts of pale dabs with no hard flash, and motion is gentle and flowing, with dabs that shimmer slightly as light moves over water and leaves.

## Fits

- **Genres:** `exploration`, `simulation`, `puzzle`, `sports`
- **Moods:** serene, sunny, nostalgic
- **Settings:** water garden, riverside village, summer meadow, seaside harbour at dawn

## Unity recipe

### Assets

Everyday outdoor subjects: water, gardens, bridges, haystacks, figures with parasols. Soft, simple models are enough because edges are dissolved in post; nature packs work with normal maps removed. Repaint albedos toward the high-key pastel palette and lift all dark values: no black or brown. Generate by script a set of comma-shaped dab stamps with soft ends and a linen-weave tile. Water is a plane with a gently animated surface.

### Materials

Write `Style/TemperatureLit`. `UniversalForward` uses `GetMainLight(shadowCoord)` but maps light to hue instead of value: lit areas lerp the albedo toward warm yellow-pink, shadowed areas toward blue-violet (`#c9b6e4`, `#5f7fb5`) at nearly the same brightness, so shadows are coloured, not dark. Add strong sky reflection on water through a reflection probe sample. No specular highlights elsewhere, no outline. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`. A per-pixel hue jitter of a few degrees from a noise texture gives the dab pass varied colours to pick up.

### Lighting and atmosphere

Bright hazy sun: a directional light with soft shadows at low strength, and a bright gradient ambient. Pale exponential fog in warm white-blue. A soft pastel sky. A reflection probe for water. No SSAO; it would add grey.

### Post-processing

A custom ScriptableRendererFeature rebuilds the frame from dabs with the RenderGraph API, before post-processing. Simplest robust method: a fullscreen pass that, per pixel, looks up a jittered grid of dab centres (two overlapping grids), samples scene colour at each centre, and draws an elongated soft dab oriented by a direction field: horizontal where the surface is water (flagged in a mask channel), multi-directional elsewhere from a noise field. Leave small gaps showing a linen colour, then multiply the linen weave. Dab positions shift slightly a few times per second for shimmer. Neutral tonemapping, saturation +5, no Bloom or sharp effects. Render scale 1.

### UI and effects

Panels are soft-edged patches of cream paint `#f6f0dc` with dabbed borders; icons are loose brush sketches. Font asset from a light rounded brush hand such as Kalam Light or Caveat Brush, in `#5f7fb5`, with `#e9905a` for highlights. Particles are single dab sprites: petals, sparkles on water, pollen, mist; impacts are soft bursts of pale dabs with no flash.

## Do / Do not

Do:

- Build the image from short separate dabs.
- Colour shadows blue-violet at near the same brightness as lights.
- Keep edges soft and dissolved.
- Avoid black entirely.

Do not:

- Do not use round uniform dots of pure pigment; that reads as `077`.
- Do not use long swirling strokes with dark contours; that reads as `076`.
- Do not use muted overcast colours with accent strokes; that reads as `028`.
- Do not keep photographic detail under the dabs; that reads as `032`.

## Nearest styles

- `077` Pointillist dot field: this style uses irregular, elongated dabs of many blended pastel colours with soft dissolved forms; `077` uses even round dots of a few pure pigments on smooth, stiff, clearly shaped forms.
- `076` Swirling impasto: this style has no contours and keeps soft pastel daylight colour in short dabs; `076` draws dark brushed contours and uses long swirling strokes of strong blue and yellow.
- `028` Expressionist oil isometric: this style is bright, sunlit and pastel; `028` is dim and overcast, in muted greens, greys and browns with thick dark paint.

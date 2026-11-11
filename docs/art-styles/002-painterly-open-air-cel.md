# Painterly open-air cel

Reference works: The Legend of Zelda: Breath of the Wild.

## References

- *The Legend of Zelda: Breath of the Wild* (2017), Nintendo EPD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Breath_of_the_Wild
- *The Legend of Zelda: Tears of the Kingdom* (2023), Nintendo EPD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Tears_of_the_Kingdom
- *The Legend of Zelda: Skyward Sword* (2011), Nintendo EAD, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Skyward_Sword
- *Immortals Fenyx Rising* (2020), Ubisoft Quebec, video game. https://en.wikipedia.org/wiki/Immortals_Fenyx_Rising

## Visual definition

- **Shape language and proportions:** Natural proportions, simplified. Rocks, trees and ruins are soft, rounded masses with few small details; silhouettes read clearly at long distance.
- **Line and outline:** No drawn outline on scenery. Characters and small props get a thin, soft dark rim (1 to 2 px) and a bright fresnel rim on the lit side.
- **Shading model:** Two bands (lit and shadow) with a narrow soft transition, plus an optional specular highlight band on metal and hair.
- **Palette:** `#8fc46a` `#4f8a5b` `#bfe3f2` `#f3e7b8` `#c98d5a` `#6f7fa8` `#e06a4a`. Fresh greens, sky blues and warm stone; shadows are blue-tinted, never grey or black.
- **Lighting:** Bright outdoor sun with strong sky fill. Shadows are soft-edged and light in value.
- **Texture and surface:** Low-frequency painted gradients and broad brush patches. Grass and foliage are flat colour cards with a vertical gradient.
- **Atmosphere and post-processing:** Strong aerial perspective that fades distance to pale blue, mild bloom on sky and highlights, light volumetric haze.
- **Camera and framing:** Wide 28 to 35 mm equivalent, third-person height, horizon in the upper third to show terrain depth.
- **UI and typography:** Thin, quiet UI: small white icons and translucent dark panels with a fine pale border and soft corner ornaments. Text is a light humanist sans in white or pale cream (`#f3e7b8`). Counters are small plain numerals, with red-orange (`#e06a4a`) only for hearts and danger.
- **VFX and motion:** Effects are soft-edged stylised shapes: curled smoke puffs, pale blue glows, drifting spores and grass that bends in the wind. Hits give a brief white starburst and a short hit-pause; animation is fluid and natural with light anticipation.

## Fits

- **Genres:** `exploration`, `action-adventure`, `survival-craft`, `rpg`, `puzzle`
- **Moods:** serene, adventurous, wistful
- **Settings:** grassy highlands, overgrown ruins, mountain wilderness, sky islands

## Unity recipe

### Assets

Choose nature and ruin packs with large rounded masses: boulders, broad-crowned trees, simple stone architecture. Restyle by removing normal maps and smoothness detail, then blur each albedo heavily in an editor step and remap it to the palette so only low-frequency painted patches remain; 512 to 1024 px, bilinear, with mipmaps. Replace grass and foliage with flat cards built by script that carry a vertical gradient in vertex colour. Rolling terrain is best generated as a mesh with soft slopes instead of using a detailed terrain pack.

### Materials

Author `Style/OpenAirCel`. In `UniversalForward`, read `GetMainLight(shadowCoord)` and shade with `smoothstep(0.45, 0.55, NdotL * shadowAttenuation)`: two bands with a narrow soft transition. The shadow band lerps toward blue (`#6f7fa8`) and never below mid value. Add a Fresnel rim on the lit side and, under a `_SPECULAR_BAND` keyword for metal and hair, one stepped Blinn-Phong highlight. Sample `SampleSH` for sky fill. Include `ShadowCaster`, `DepthOnly` and `DepthNormals`, and call `MixFog`. Characters and small props get a thin inverted-hull rim (pass tagged `SRPDefaultUnlit`, `Cull Front`) in a soft dark colour at 1 to 2 px; scenery materials leave it off. A foliage variant adds vertex wind and alpha clip.

### Lighting and atmosphere

One realtime sun with soft shadows (soft shadows on, four cascades, 150 m distance) and a strong gradient ambient (`AmbientMode.Trilight`) with a blue sky colour. Exponential-squared fog in pale blue (`#bfe3f2`) carries the aerial perspective; use `Skybox/Procedural` with low atmosphere thickness. Bake nothing; SSAO off, since it would grey the blue shadows.

### Post-processing

Volume profile: Neutral tonemapping, Bloom with a high threshold and low intensity so only sky and highlights glow, Color Adjustments with a small saturation lift. No outline pass, no grain. Fake haze shafts with a few large additive quads near the sun direction. Render scale 1, MSAA 4x, HDR on.

### UI and effects

Use a light humanist sans such as Nunito Sans Light for the TextMeshPro font asset, in white or `#f3e7b8`. Panels are translucent dark sprites with a one-pixel pale border and small corner ornaments; icons are small white glyphs. Keep `#e06a4a` for hearts and danger. Particles are soft-edged alpha sprites: curled smoke puffs, slow pale blue motes, a brief white starburst on hit. Bend grass around the player with a global position passed through `Shader.SetGlobalVector`.

## Do / Do not

Do:

- Tint shadows blue and keep them light.
- Fade distant terrain strongly toward sky colour.
- Use a bright fresnel rim on characters.
- Keep textures as large soft patches.

Do not:

- Do not add heavy black outlines or hatching; that reads as `001`.
- Do not remove all texture and gradient; flat fills read as `003`.
- Do not use full PBR roughness and metal response; that reads as `013`.
- Do not use dense painted backgrounds with brown line art; that reads as `014`.

## Nearest styles

- `003` Flat-shape ocean toon: this style has soft painted gradients, distance haze and natural proportions; `003` uses single flat colours with a knife-sharp shadow edge, clear air and strong caricature.
- `018` Soft open-world anime cel: this style draws no outline on scenery and only a faint rim on characters; `018` draws a thin coloured outline around every character and prop and adds fine ornamental trim on costumes.
- `014` Hand-painted pastoral anime: this style keeps scenery as broad soft colour patches; `014` has densely painted backgrounds with visible brush dabs and a brown line on characters.

# Frontier natural-light realism

Reference works: Red Dead Redemption 2.

## References

- *Red Dead Redemption 2* (2018), Rockstar Games, video game. https://en.wikipedia.org/wiki/Red_Dead_Redemption_2
- *The Last of Us Part II* (2020), Naughty Dog, video game. https://en.wikipedia.org/wiki/The_Last_of_Us_Part_II
- *The Revenant* (2015), Alejandro G. Inarritu, live-action film. https://en.wikipedia.org/wiki/The_Revenant_(2015_film)
- *Among the Sierra Nevada, California* (1868), Albert Bierstadt, oil painting. https://en.wikipedia.org/wiki/Among_the_Sierra_Nevada,_California
- *Kingdom Come: Deliverance* (2018), Warhorse Studios, video game. https://en.wikipedia.org/wiki/Kingdom_Come:_Deliverance

## Visual definition

- **Shape language and proportions:** Accurate real-world proportions. Open landscapes, timber buildings, wagons, fences; natural irregularity in every object.
- **Line and outline:** No outline.
- **Shading model:** Full physically based shading with natural soft-to-hard shadow falloff and realistic sky lighting.
- **Palette:** `#8a7a5c` `#c9b48a` `#5f6f4a` `#9db4c8` `#6b4a32` `#e8dcc0` `#3a3a30` `#d99a5a`. Natural earth, dry grass, sage green and weathered wood under a soft blue sky; warm golden-hour highlights.
- **Lighting:** Natural sun and sky at golden hour or under broken cloud; long shadows, visible atmospheric scattering.
- **Texture and surface:** Photographic detail at every scale: wood grain, mud, grass, stone, cloth weave.
- **Atmosphere and post-processing:** Aerial haze, mild bloom, light film grain, gentle depth of field at long range.
- **Camera and framing:** Wide landscape framing, 28 to 40 mm equivalent, horizon low or on a third.
- **UI and typography:** Minimal and mostly hidden: worn paper panels like a hand-drawn map or journal, thin inked rules, and icons drawn as catalogue engravings. Body text is an old-style serif, with wood-type slab capitals for titles as on frontier posters. Counters are small plain numerals in cream `#e8dcc0`, with dusty orange `#d99a5a` for alerts; no floating damage numbers.
- **VFX and motion:** Dust rises from hooves and wheels, gunsmoke hangs and drifts on the wind, breath shows as vapour in cold air and campfires throw slow embers. Motion is weighty and realistic, with full anticipation and follow-through and no snap.

## Fits

- **Genres:** `action-adventure`, `exploration`, `third-person-shooter`, `survival-craft`, `rpg`, `simulation`
- **Moods:** contemplative, rugged, melancholic
- **Settings:** American frontier, mountain wilderness, medieval countryside, overgrown abandoned town

## Unity recipe

### Assets

Photoreal nature and frontier packs: terrain, grass, rock, timber buildings, wagons, fences. Photogrammetry libraries (CC0 scans and PBR sets) suit this style well. Keep every map at full resolution with anisotropic filtering. Avoid perfect repetition: vary rotation, scale and tint per instance in the placement step, and sag fences and roof lines slightly. Use Unity Terrain with painted layers and detail grass.

### Materials

`Universal Render Pipeline/Lit` for objects and `Universal Render Pipeline/Terrain/Lit` for terrain layers with normal and mask maps. Foliage uses alpha-clipped Lit with two-sided rendering and wind in a small custom vertex variant if the pack lacks one. Water uses a transparent Lit-based shader with depth fade and probe reflections. Do not alter the PBR response; correctness of albedo brightness matters, so check that albedo values are not too dark or too saturated.

### Lighting and atmosphere

Natural sun and sky. A directional light at golden-hour angle (10 to 25 degrees) with colour temperature near 4500 K, soft shadows, four cascades, 200 m or more. `Skybox/Procedural` or an HDRI on `Skybox/Panoramic`, with ambient from the skybox. Bake Adaptive Probe Volumes with sky occlusion for correct sky lighting on a large terrain. Baked reflection probes. Exponential fog in a pale warm blue-grey for aerial haze. SSAO on, moderate.

### Post-processing

ACES tonemapping, mild Bloom, light Film Grain, Depth Of Field in Bokeh mode with a far focus so only long range softens. Keep colour natural: no strong grade, saturation near 0, slight warm White Balance. TAA, HDR on. Add the Lens Flare (SRP) component on the sun at low intensity.

### UI and effects

Mostly hidden UI: worn paper panels like a journal or hand-drawn map, thin inked rules, engraving-style icons. Body text from an old-style serif such as IM Fell English; titles in wood-type slab capitals such as Rye or Sancreek. Small plain numerals in `#e8dcc0`, `#d99a5a` for alerts, no floating damage numbers. Effects: lit dust from hooves and wheels, gunsmoke that hangs and drifts with a wind zone for five to eight seconds, breath vapour, slow campfire embers. Use `Universal Render Pipeline/Particles/Lit` so smoke takes the sun colour.

## Do / Do not

Do:

- Light with a physically based sky at low sun.
- Scatter dense instanced grass and rocks.
- Add irregularity and sag to built objects.
- Fade distance with aerial haze.

Do not:

- Do not push a two-hue colour grade; that reads as `033`.
- Do not desaturate and crush contrast; that reads as `030`.
- Do not simplify materials into clean stylised regions; that reads as `013`.
- Do not replace detail with visible dabs of paint; that reads as `075`.

## Nearest styles

- `033` Teal-orange desert blockbuster: this style keeps natural greens, soft haze and many quiet earth colours; `033` pushes the whole frame to vivid orange sand against teal sky and shadow.
- `030` Gritty desaturated war realism: this style has warm golden sun on an open landscape with clear natural colour; `030` is darker and almost colourless grey, with crushed shadows.
- `075` Impressionist broken colour: surfaces here show photographic detail with smooth tonal transitions; `075` builds the whole image from separate visible paint dabs in pale, bright pastels.

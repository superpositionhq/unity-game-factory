# Hand-painted pastoral anime

Reference works: Spirited Away; My Neighbor Totoro.

## References

- *My Neighbor Totoro* (1988), Studio Ghibli (Hayao Miyazaki), animated film. https://en.wikipedia.org/wiki/My_Neighbor_Totoro
- *Spirited Away* (2001), Studio Ghibli (Hayao Miyazaki), animated film. https://en.wikipedia.org/wiki/Spirited_Away
- *Kiki's Delivery Service* (1989), Studio Ghibli (Hayao Miyazaki), animated film. https://en.wikipedia.org/wiki/Kiki's_Delivery_Service
- *Ni no Kuni: Wrath of the White Witch* (2011), Level-5, video game. https://en.wikipedia.org/wiki/Ni_no_Kuni:_Wrath_of_the_White_Witch
- *Howl's Moving Castle* (2004), Studio Ghibli (Hayao Miyazaki), animated film. https://en.wikipedia.org/wiki/Howl's_Moving_Castle_(film)

## Visual definition

- **Shape language and proportions:** Gentle realism. Buildings are lived-in and slightly irregular; vegetation is lush and detailed. Characters have simple faces and soft rounded bodies.
- **Line and outline:** Thin dark-brown line on characters and moving props. Backgrounds have no line and are painted.
- **Shading model:** Characters: two flat bands. Backgrounds: fully painted light with soft gradients.
- **Palette:** `#6aa84f` `#2f6b3a` `#9fd3f0` `#fdfdf5` `#d9b382` `#b5533c` `#5a4636` `#f4d67a`. Rich greens, cumulus white, sky blue and warm wood and earth colours.
- **Lighting:** Summer daylight with tall white clouds, dappled leaf shadow, warm interiors.
- **Texture and surface:** Backgrounds look like poster-colour paintings: visible brush dabs in foliage, soft washed walls, crisp painted cloud edges.
- **Atmosphere and post-processing:** None beyond slight warmth. The split between flat characters and painted backgrounds is intended.
- **Camera and framing:** Calm, level, 35 to 50 mm equivalent; wide landscape views with large sky.
- **UI and typography:** Cream paper panels with a thin brown border, or small painted wooden signboards. Text is a soft rounded hand-lettered face in dark brown; icons are small poster-colour paintings with a brown line. Counters are plain rounded brown numerals with no glow; highlights use leaf green or warm yellow.
- **VFX and motion:** Effects are hand-drawn and flat: round dust puffs, soot specks, water drops with a single white highlight, leaves and petals on the wind. Character animation is on twos with gentle, weighty everyday movement; hair, grass and cloth sway slowly and clouds drift.

## Fits

- **Genres:** `exploration`, `simulation`, `action-adventure`, `rpg`, `puzzle`, `platformer`
- **Moods:** gentle, nostalgic, wondrous
- **Settings:** countryside village, forest shrine, seaside European town, spirit bathhouse

## Unity recipe

### Assets

Two asset classes with different treatment. Characters and moving props: simple rounded models with plain faces, all textures removed, flat colours. Scenery: lived-in village, farm and forest packs with irregular buildings and lush vegetation. Repaint scenery textures by script to look like poster colour: reduce to palette greens, wood and earth, then stamp many small opaque brush dabs along the texture's own colour boundaries; 2048 px, bilinear, no normal maps. Clouds are painted quads or dome textures with crisp edges, made by script.

### Materials

Characters use `Style/PastoralCel`: `UniversalForward` with `GetMainLight(shadowCoord)` and one `step` for two flat bands, shadow colour a warmer darker hue, plus an inverted-hull pass tagged `SRPDefaultUnlit` drawing a thin dark-brown line (`#5a4636`, about 1.5 px). Include `ShadowCaster`, `DepthOnly`, `DepthNormals`. Scenery uses a second shader, `Style/PaintedBackdrop`: albedo with light painted in, multiplied by baked lightmap and a soft realtime shadow term so characters still cast onto it; no specular, no line. The difference between the two shaders is intended; do not unify them.

### Lighting and atmosphere

A high summer directional light with soft shadows. Bake lightmaps for static scenery so painted buildings get soft gradients and bounce; use Adaptive Probe Volumes to light characters. Dappled leaf shadow comes from a light cookie on the sun (URP supports cookies on the main light) with a slow scroll. Warm point lights indoors. Fog off or very faint; a painted sky dome with tall cumulus. SSAO off.

### Post-processing

Keep it matte: Neutral tonemapping, White Balance slightly warm, nothing else. No Bloom, no glow, no lens effects, no grain. MSAA 4x, render scale 1.

### UI and effects

Cream paper panels with a thin brown border, or small painted wooden signboards as sprites. Font asset from a soft rounded hand-lettered face such as Klee One or Patrick Hand, dark brown. Counters are plain rounded numerals; highlights in `#6aa84f` or `#f4d67a`. Effects are flat hand-drawn flipbooks, alpha blended and unlit: round dust puffs, soot specks, water drops with one white highlight, leaves and petals drifting on a wind zone. Step character clips to twos; sway grass and cloth slowly in the vertex shader and drift the clouds.

## Do / Do not

Do:

- Keep characters flat and backgrounds painted.
- Use brown, not black, for line.
- Paint clouds with crisp lit edges and soft undersides.
- Layer foliage dabs dark to light.

Do not:

- Do not add lens flare, glow gradients and photo-level sky detail; that reads as `016`.
- Do not line and flat-shade the scenery too; that reads as `018`.
- Do not use chunky high-contrast painted textures with smooth shading on characters; that reads as `023`.
- Do not use black outlines.

## Nearest styles

- `016` Luminous sky anime: `016` fills the frame with glowing twilight skies, lens flares and wet reflections; this style has matte daylight paintings with no glow.
- `018` Soft open-world anime cel: `018` has clean, smooth scenery with simple gradients and outlined props; this style has scenery painted with visible brush dabs and no line.
- `002` Painterly open-air cel: `002` has almost no line and paints the world in broad soft patches of colour; this style draws a brown line around characters and paints dense detail into foliage and buildings.

# Chunky hand-painted fantasy

Reference works: World of Warcraft.

## References

- *World of Warcraft* (2004), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/World_of_Warcraft
- *Warcraft III: Reign of Chaos* (2002), Blizzard Entertainment, video game. https://en.wikipedia.org/wiki/Warcraft_III:_Reign_of_Chaos
- *League of Legends* (2009), Riot Games, video game. https://en.wikipedia.org/wiki/League_of_Legends
- *Torchlight II* (2012), Runic Games, video game. https://en.wikipedia.org/wiki/Torchlight_II
- *Dota 2* (2013), Valve, video game. https://en.wikipedia.org/wiki/Dota_2

## Visual definition

- **Shape language and proportions:** Chunky and exaggerated: oversized shoulders, hands, weapons and roof beams; thick edges; bent and tapered silhouettes. Low to mid polygon counts.
- **Line and outline:** No outline. Dark painted crevices act as line.
- **Shading model:** Light and shadow are mostly painted into the albedo; real-time lighting adds a soft smooth gradient on top.
- **Palette:** `#7a4b2a` `#c8a15a` `#4f7a3a` `#3b5fa8` `#8b2f8f` `#e8d8a8` `#2a2333`. Warm wood and gold against saturated blue, purple and green. Each zone has a strong colour identity.
- **Lighting:** Soft, even daylight or a coloured zone ambient; no hard contrast from real-time lights.
- **Texture and surface:** Hand-painted with visible brush strokes: bright chiselled edge highlights, dark seams, gradients from top to bottom, painted metal shine.
- **Atmosphere and post-processing:** Light bloom, zone-coloured distance fog.
- **Camera and framing:** Third-person from above shoulder height or a top-down 55 degree view.
- **UI and typography:** Heavy ornate frames of gold metal, carved stone and wood, with painted square ability icons in bevelled borders. Titles use a chunky fantasy serif and values a bold sans; damage numbers are large floating yellow and white digits with a dark outline. UI colours are gold `#c8a15a` and parchment `#e8d8a8` on dark purple-black `#2a2333`.
- **VFX and motion:** Bold, readable spell effects in saturated blue, purple and green: big soft glows, painted swirls and large spark shapes. Animation is exaggerated, with wide anticipation, big weapon arcs and slight squash and stretch.

## Fits

- **Genres:** `rpg`, `strategy`, `hack-and-slash`, `tower-defense`, `action-adventure`, `roguelike`
- **Moods:** heroic, adventurous, warm
- **Settings:** high-fantasy kingdoms, orc war camps, enchanted forests, dungeon ruins

## Unity recipe

### Assets

Chunky fantasy packs with oversized shoulders, weapons and roof beams and thick edges; low to mid polygon counts. Hand-painted packs fit as they are. To restyle a realistic pack, bake its lighting into albedo: in an editor step combine the albedo with its occlusion map as dark seams, add edge highlights from a curvature map derived from the normal map, apply a top-to-bottom gradient, then discard the normal, metallic and smoothness maps. 1024 px, bilinear. Exaggerate proportions by scaling bones or mesh parts.

### Materials

`Universal Render Pipeline/Simple Lit` with specular highlights off (`_SpecularHighlights` 0) is enough for most surfaces: light and shadow are already painted, and realtime light adds only a soft gradient. Where more control is wanted, write `Style/PaintedDiffuse`: half-Lambert from `GetMainLight(shadowCoord)` remapped to a narrow range (0.6 to 1.0) so realtime light never makes hard contrast, plus `SampleSH` ambient and `MixFog`, with `ShadowCaster`, `DepthOnly`, `DepthNormals` and `Meta` passes. Painted metal shine stays in the texture; do not use metallic values. No outline.

### Lighting and atmosphere

Soft even daylight: a directional light at moderate intensity with soft shadows at reduced strength (0.5 to 0.6), and a bright gradient ambient coloured per zone. Bake Adaptive Probe Volumes and lightmaps on static scenery. Each zone gets its own fog colour (linear fog, saturated blue, purple or green) switched by trigger volumes. SSAO off or minimal, since crevices are painted. Simple gradient or painted skybox.

### Post-processing

Light Bloom (threshold 1, low intensity), Neutral tonemapping, saturation +10. Per-zone local Volumes shift the colour filter. No grain, no outline. SMAA or MSAA 4x.

### UI and effects

Heavy ornate frames in gold metal, carved stone and wood as painted 9-sliced sprites, and square ability icons in bevelled borders. Titles from a chunky fantasy serif such as Almendra Bold or Cinzel Decorative; values from a bold sans. Floating damage digits are large, yellow and white with a dark outline. `#c8a15a` and `#e8d8a8` on `#2a2333`. Spell effects are big and readable: large soft additive glows, painted swirl flipbooks and large spark shapes in saturated blue, purple and green, with long 0.6 to 1 s lifetimes and wide weapon-arc trails.

## Do / Do not

Do:

- Paint light, shadow and edge highlights into the albedo.
- Exaggerate thickness and silhouette.
- Use diffuse-only materials.
- Give each zone a strong colour identity.

Do not:

- Do not rely on normal maps and PBR response; that reads as `013`.
- Do not mute and compress the palette with rim light; that reads as `005`.
- Do not use nearest-filtered low-resolution pixel textures; that reads as `036` or `044`.
- Do not add ink outlines.

## Nearest styles

- `013` Stylised hero PBR: surfaces here are matte and carry painted brush strokes, edge highlights and dark seams; `013` has clean smooth surfaces with realistic material shine and little painted detail.
- `005` Rim-lit illustrative caricature: colours here are strong and every zone is saturated, with busy painted texture; `005` is muted on neutral backgrounds, with low-contrast brush marks and a bright rim light on every form.
- `024` Brush-textured 3D drama: this style is bright and evenly lit with soft smooth light; `024` is dark and dramatic, with light broken into stepped painted planes.

# Soft open-world anime cel

Reference works: Genshin Impact.

## References

- *Genshin Impact* (2020), miHoYo, video game. https://en.wikipedia.org/wiki/Genshin_Impact
- *Honkai: Star Rail* (2023), miHoYo, video game. https://en.wikipedia.org/wiki/Honkai:_Star_Rail
- *Tales of Arise* (2021), Bandai Namco Studios, video game. https://en.wikipedia.org/wiki/Tales_of_Arise
- *Zenless Zone Zero* (2024), miHoYo, video game. https://en.wikipedia.org/wiki/Zenless_Zone_Zero

## Visual definition

- **Shape language and proportions:** Slim anime characters with detailed layered costumes and ornaments. Scenery is clean and idealised: rounded hills, tidy stone towns, stylised trees.
- **Line and outline:** Thin dark outline (1 to 2 px), coloured slightly toward the local hue, on characters and props; light or none on terrain.
- **Shading model:** Two bands with a soft-edged ramp, plus a stylised metal highlight and a face shadow that keeps a clean shape.
- **Palette:** `#a8d8ea` `#fcefc7` `#aa96da` `#fcbad3` `#7fcd91` `#4d5b8c` `#ffffff`. Light pastels: sky blue, cream, lavender, mint, with gold trim. Shadows are lavender-blue.
- **Lighting:** Clear daylight with strong ambient; rim light on characters.
- **Texture and surface:** Smooth gradients inside flat regions; fine ornamental trim lines on costumes; terrain has simple painted variation.
- **Atmosphere and post-processing:** Soft bloom, light haze, gentle colour grade toward pastel.
- **Camera and framing:** Third-person, 35 to 50 mm equivalent, character centred against open scenery.
- **UI and typography:** Cream and dark slate-blue panels with rounded corners, thin gold borders and small ornamental flourishes at the corners. Icons are flat white or gold glyphs inside circles and diamonds. Text is an elegant rounded serif for titles and a clean sans for body text; damage numbers are small bold numerals coloured by element (lavender, mint, sky blue, gold) that float up and fade.
- **VFX and motion:** Soft glowing particles, petals, sparkles and translucent ribbon trails in pastel element colours, with a ring of light and a short bloom flash on hit. Animation is fluid and graceful, with flowing hair and cloth, flourished attack poses and a light floaty landing.

## Fits

- **Genres:** `rpg`, `action-adventure`, `exploration`, `hack-and-slash`, `roguelike`, `puzzle`
- **Moods:** serene, adventurous, bright
- **Settings:** fantasy meadows and cliffs, harbour city, mountain temple, floating islands

## Unity recipe

### Assets

Slim anime characters with layered costumes and ornaments, and tidy idealised scenery: rounded hills, clean stone towns, stylised trees. Fantasy packs made for anime-style games fit directly. Soften realistic packs by removing normal maps, flattening albedo into smooth gradients and shifting it to pastel. Keep fine trim lines on costumes as texture detail at 2048 px. Faces need a painted shadow-threshold map (made in Blender or by script) so the face shadow keeps a clean shape as the light turns.

### Materials

Write `Style/SoftAnimeCel`. `UniversalForward` uses `GetMainLight(shadowCoord)` and looks NdotL up in a small ramp texture with a soft edge between two bands; shadow is lavender-blue (`#aa96da` mixed with the base). Face materials replace NdotL with a comparison between the light's angle around the head and the threshold map. Metal uses a view-space matcap-like highlight stripe. Add a rim from depth: compare scene depth at a small screen offset toward the light and brighten where it is farther. The outline is an `SRPDefaultUnlit` hull pass, 1 to 2 px, coloured as the base colour darkened and saturated, not black. Terrain materials disable the hull. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`.

### Lighting and atmosphere

Clear daylight directional light with soft shadows, four cascades, 200 m for open-world views. Strong ambient from a trilight gradient. Adaptive Probe Volumes baked for gentle bounce. Light linear fog in pale blue. SSAO on at very low intensity so contact stays soft. A procedural sky with painted cloud cards.

### Post-processing

Soft Bloom (threshold 0.9, low intensity, high scatter). Color Adjustments and Lift Gamma Gain lifting the blacks toward lavender for a pastel grade. Neutral tonemapping. TAA or SMAA. No grain, no heavy contrast.

### UI and effects

Cream and slate-blue (`#4d5b8c`) rounded panels with thin gold borders and small corner flourishes, as 9-sliced sprites. Titles from an elegant serif such as Cormorant Garamond SemiBold, body from a clean sans such as Nunito. Damage numbers are small bold numerals coloured by element that float up and fade. Effects: soft glowing particles, petals, sparkles and translucent ribbon trails in pastel element colours, with a ring of light and a short bloom flash on hit. Use cloth and hair physics for flowing motion.

## Do / Do not

Do:

- Use tinted, thin outlines.
- Keep shadows lavender and light.
- Add gold trim and a stylised metal highlight.
- Use soft-edged two-band ramps.

Do not:

- Do not use hard black lines and razor band edges with saturated shadows; that reads as `015`.
- Do not remove outlines and paint the terrain broadly; that reads as `002`.
- Do not add dense painted backgrounds; that reads as `014`.
- Do not use full PBR shading on characters; that reads as `013`.

## Nearest styles

- `002` Painterly open-air cel: `002` has almost no outline and paints its terrain in broad soft patches; this style outlines characters and props and keeps terrain clean and smooth.
- `015` Two-tone fighting-anime cel: `015` has black tapered outlines, razor-sharp shadow edges and strong, dark shadow colours; this style has thin tinted outlines, soft shadow edges and light lavender shadows.
- `014` Hand-painted pastoral anime: `014` paints its scenery with visible brush dabs and dense foliage detail; this style keeps scenery smooth, with simple gradients and tidy shapes.

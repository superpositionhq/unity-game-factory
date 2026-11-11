# Metaphysical long-shadow plaza

Reference works: Giorgio de Chirico; Ico.

## References

- *The Song of Love* (1914), Giorgio de Chirico, oil painting. https://en.wikipedia.org/wiki/The_Song_of_Love
- *Mystery and Melancholy of a Street* (1914), Giorgio de Chirico, oil painting. https://en.wikipedia.org/wiki/Mystery_and_Melancholy_of_a_Street
- *Ico* (2001), Team Ico (Fumito Ueda), video game. https://en.wikipedia.org/wiki/Ico
- *The Persistence of Memory* (1931), Salvador Dali, oil painting. https://en.wikipedia.org/wiki/The_Persistence_of_Memory
- *The Disquieting Muses* (1916-1918), Giorgio de Chirico, oil painting. https://en.wikipedia.org/wiki/The_Disquieting_Muses

## Visual definition

- **Shape language and proportions:** Empty town squares with long arcades of round arches, a tower or chimney, a statue or mannequin, a few isolated objects (a ball, a glove, a train on the horizon). Simple, smooth, solid volumes; steep, inconsistent perspective.
- **Line and outline:** No outline.
- **Shading model:** Simple firm modelling in three to five tone steps; cast shadows are large, flat, very dark shapes with hard edges.
- **Palette:** `#d9a441` `#c8553d` `#2f5d50` `#1f3a4d` `#e9d9a6` `#6b4a32` `#f2efe2`. Ochre and terracotta buildings, dark green-teal sky that lightens to yellow at the horizon, deep brown-black shadows.
- **Lighting:** Very low late-afternoon sun producing shadows two to five times longer than the objects; shadow directions need not agree.
- **Texture and surface:** Smooth, matte painted surfaces with slight dry-brush unevenness.
- **Atmosphere and post-processing:** None; clear air with no haze.
- **Camera and framing:** Wide angle from slightly above, with exaggerated converging lines; deep empty foreground.
- **UI and typography:** Panels are plain flat rectangles in ochre or pale cream with a hard dark drop shadow, offset like a cast shadow, and no ornament; icons are simple solid silhouettes (arch, tower, ball, clock). Text is a classical Roman serif in widely spaced capitals, in deep brown or cream. Counters use old-style serif numerals, with terracotta for warnings.
- **VFX and motion:** Particles are few: a train's smoke plume as a firm white shape, a flag that moves in a wind nothing else feels. A hit shows as a brief flat flash and a jump of the long shadow. Motion is slow and deliberate with long stillness, and moving objects are read by their sliding hard shadows.

## Fits

- **Genres:** `puzzle`, `exploration`, `action-adventure`, `detective-mystery`, `stealth`, `platformer`
- **Moods:** eerie, melancholic, lonely, dreamlike
- **Settings:** empty Italian piazza, deserted seaside town, ruined castle

## Unity recipe

### Assets

Empty town squares: long arcades of round arches, a tower or chimney, a statue or mannequin, a few isolated objects (a ball, a glove, a train on the horizon). Build architecture from scratch with ProBuilder's API as simple smooth solid volumes; classical-town packs work if stripped of ornament and texture. Exaggerate and vary perspective by tapering buildings and tilting ground planes slightly. Generate a subtle dry-brush variation texture. Keep the square mostly empty.

### Materials

Write `Style/PlazaTone`. `UniversalForward` takes `GetMainLight(shadowCoord)` and quantises NdotL into three to five firm tone steps of the matte base colour (ochre, terracotta, cream), multiplied by the dry-brush texture at low contrast. Cast shadow is not blended softly: where `shadowAttenuation` is below 0.5 output a flat, very dark brown-black (`#6b4a32` darkened) regardless of the surface colour, with a hard edge. No specular. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`. For shadow directions that disagree, selected objects use a fake shadow: a flattened dark copy of the mesh projected along its own chosen direction, drawn as an unlit decal mesh on the ground.

### Lighting and atmosphere

One directional sun at 10 to 20 degrees elevation so shadows are two to five times longer than the objects. Hard shadows: soft shadows off, shadow resolution 4096, distance tuned tightly to the plaza (60 to 80 m), two cascades. Flat ambient. No fog and no haze: the air is clear. The sky is an unlit gradient from dark green-teal `#1f3a4d` and `#2f5d50` overhead to yellow `#e9d9a6` at the horizon. No SSAO, no reflection probes.

### Post-processing

None of note. Tonemapping None or Neutral; no Bloom, grain or blur. Use a perspective camera with a moderately wide lens and steep converging lines. MSAA 4x so shadow and arch edges are clean.

### UI and effects

Panels are plain flat rectangles in ochre or pale cream with a hard dark drop shadow offset like a cast shadow (TextMeshPro underlay for text, a duplicate dark image for panels), no ornament. Font asset from a classical Roman serif in widely spaced capitals such as Cinzel or Marcellus, deep brown or cream; old-style numerals, terracotta for warnings. Icons are solid silhouettes: arch, tower, ball, clock. Effects are few: a train's smoke as a firm white mesh shape, a flag moving in an unfelt wind, a brief flat flash on hit with a small jump of the shadow.

## Do / Do not

Do:

- Cast very long, hard, dark shadows.
- Leave the plaza almost empty.
- Repeat round arches in long receding rows.
- Use a dark green sky that turns yellow at the horizon.

Do not:

- Do not use an isometric camera with pastel three-tone faces and no shadows; that reads as `059`.
- Do not use hazy single-hue sand and soft light; that reads as `061`.
- Do not go to deep black backgrounds with a spotlight on figures; that reads as `085`.
- Do not add weathering detail.

## Nearest styles

- `059` Isometric pastel impossible architecture: this style has a perspective camera with steep converging lines, earthy ochre and terracotta, and very long hard cast shadows; `059` has an isometric view, pastel faces in three flat tones and no cast shadows.
- `061` Soft-gradient minimal desert: this style has firm tone steps, hard dark shadows, clear air and ochre walls against a green sky; `061` has smooth gradients, haze, soft light and one hue family across the scene.
- `097` Brutalist concrete: this style has warm ochre and terracotta arcades under a green and yellow sky; `097` is raw grey concrete with almost no colour.

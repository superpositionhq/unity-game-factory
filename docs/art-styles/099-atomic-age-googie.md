# Atomic-age Googie

Reference works: Fallout; The Jetsons.

## References

- *Fallout 4* (2015), Bethesda Game Studios, video game. https://en.wikipedia.org/wiki/Fallout_4
- *The Jetsons* (1962), Hanna-Barbera Productions, animated TV series. https://en.wikipedia.org/wiki/The_Jetsons
- *The Incredibles* (2004), Pixar Animation Studios (Brad Bird), animated film. https://en.wikipedia.org/wiki/The_Incredibles
- *Theme Building, Los Angeles International Airport* (1961), Pereira and Luckman with Paul Williams and Welton Becket, architecture. https://en.wikipedia.org/wiki/Theme_Building
- *TWA Flight Center* (1962), Eero Saarinen, architecture. https://en.wikipedia.org/wiki/TWA_Flight_Center

## Visual definition

- **Shape language and proportions:** Optimistic space-age forms: upswept cantilevered roofs, parabolic arches, boomerangs, kidney shapes, starbursts, atoms with orbit rings, flying-saucer discs, tail fins, bubble domes, tapered legs, bullet-shaped robots and rockets.
- **Line and outline:** No outline.
- **Shading model:** Smooth and glossy: enamel paint, chrome trim and coloured plastics with clean highlights.
- **Palette:** `#4fc1c9` `#f26b4f` `#f6d55c` `#f4efe1` `#e8a0b4` `#3b3b3b` `#c9d1d3`. Turquoise, coral, mustard yellow, pink and cream with chrome and charcoal.
- **Lighting:** Bright sunny daylight or a cheerful showroom; neon sign glow at dusk.
- **Texture and surface:** Clean surfaces with printed mid-century patterns: boomerang laminate, starburst wallpaper, terrazzo speckle, wood veneer. Minimal wear.
- **Atmosphere and post-processing:** Slight warm grade and mild bloom on chrome and neon.
- **Camera and framing:** Low three-quarter views emphasising roof sweep; wide lens.
- **UI and typography:** Rounded kidney and boomerang panels with chrome trim and starburst accents; icons are cheerful flat pictograms like 1950s appliance badges. Type mixes a bouncy casual brush script for titles with a bold rounded sans for labels. Counters are chunky cream numerals on turquoise `#4fc1c9` or coral `#f26b4f`, or needle dials like a car dashboard.
- **VFX and motion:** Four-point star twinkles on chrome, atom orbit rings, puffy stylised smoke clouds and ray-gun rings; hits pop as starbursts in coral and mustard. Motion is bouncy and upbeat, with light squash and stretch, quick anticipation and smoothly hovering vehicles.

## Fits

- **Genres:** `action-adventure`, `racing`, `survival-craft`, `simulation`, `vehicle-combat`, `rpg`
- **Moods:** optimistic, playful, cheerful, retro
- **Settings:** 1950s space-age suburb, roadside diner, sky city, world's fair

## Unity recipe

### Assets

Space-age forms: upswept cantilevered roofs, parabolic arches, boomerangs, kidney shapes, starbursts, atoms with orbit rings, saucer discs, tail fins, bubble domes, tapered legs, bullet-shaped robots and rockets. Retro diner, motel and 1950s car packs fit; build signs, starbursts and boomerang canopies by script. Keep surfaces clean with minimal wear. Generate printed pattern textures by script: boomerang laminate, starburst wallpaper, terrazzo speckle, plus wood veneer from a CC0 source. Recolour to turquoise, coral, mustard, pink and cream.

### Materials

`Universal Render Pipeline/Lit`. Enamel paint: saturated palette albedo, metallic 0, smoothness 0.8, or `Universal Render Pipeline/Complex Lit` with clear coat for car bodies and appliances. Chrome trim: metallic 1, smoothness 0.95, albedo `#c9d1d3`. Coloured plastics: smoothness 0.6. Patterned laminate and wallpaper carry the printed textures at moderate smoothness. Bubble domes use transparent Lit. Neon signs use emissive Lit tubes (swept meshes) with HDR colour. No outline or toon shading.

### Lighting and atmosphere

Bright sunny daylight: a strong directional sun with soft shadows, four cascades, 150 m; a clear blue procedural sky and skybox ambient. Chrome needs reflections: baked reflection probes outdoors and box-projected ones in showrooms. Bake Adaptive Probe Volumes for bounce. At dusk, lower the sun, switch on neon emission and add coloured point lights at signs. No fog. SSAO on, low.

### Post-processing

Neutral tonemapping, slight warm White Balance, saturation +10. Mild Bloom on chrome glints and neon (threshold 1). No Depth Of Field: full-size buildings stay in sharp focus across the frame. No grain. TAA or MSAA 4x. Use low three-quarter camera angles to show the swept roofs.

### UI and effects

Rounded kidney and boomerang panels with chrome trim and starburst accents; icons are cheerful flat pictograms like appliance badges. Titles from a bouncy casual brush script such as Pacifico or Yellowtail; labels from a bold rounded sans such as Fredoka or Baloo 2; chunky cream numerals on turquoise or coral, or needle dials. Effects: four-point star twinkles on chrome (additive sprites that scale and rotate), atom orbit rings, puffy stylised smoke clouds as rounded meshes, ray-gun rings that expand along the shot path, starburst pops in coral and mustard. Vehicles hover smoothly; characters move with light squash and stretch.

## Do / Do not

Do:

- Use upswept roofs, boomerangs, starbursts and atom motifs.
- Combine turquoise, coral and mustard with chrome.
- Keep surfaces glossy and clean.
- Add tail fins and bubble domes to vehicles.

Do not:

- Do not use dark stepped symmetry with gold and black; that reads as `096`.
- Do not flatten the light and frame symmetrically in muted pastels; that reads as `034`.
- Do not round everything into tiny blurred toys; that reads as `057`.
- Do not add brass gears and rivets; that reads as `095`.

## Nearest styles

- `034` Symmetric pastel dollhouse film: this style has glossy curved forms in vivid turquoise and coral, seen from low three-quarter angles; `034` is flat-lit, muted pastel and strictly symmetric.
- `096` Art Deco streamline: this style is bright and sunny with playful swept curves; `096` is dark and formal, polished in black, gold and teal.
- `057` Toy-diorama tilt-shift: this style shows full-size buildings and vehicles in sharp focus with printed patterns on their surfaces; `057` is plain miniature toys with the top and bottom of the frame blurred.

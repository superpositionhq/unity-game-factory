# Toy-diorama tilt-shift

Reference works: Link's Awakening (2019).

## References

- *The Legend of Zelda: Link's Awakening* (2019), Grezzo, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Link's_Awakening_(2019_video_game)
- *Captain Toad: Treasure Tracker* (2014), Nintendo EAD Tokyo, video game. https://en.wikipedia.org/wiki/Captain_Toad:_Treasure_Tracker
- *Animal Crossing: New Horizons* (2020), Nintendo EPD, video game. https://en.wikipedia.org/wiki/Animal_Crossing:_New_Horizons
- *The Legend of Zelda: Echoes of Wisdom* (2024), Nintendo EPD and Grezzo, video game. https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Echoes_of_Wisdom

## Visual definition

- **Shape language and proportions:** Small, rounded, toy-like forms: stubby characters with bead eyes, trees as glossy lumps, houses like moulded play-set pieces. The world looks like a tabletop diorama.
- **Line and outline:** No outline.
- **Shading model:** Smooth, glossy plastic or glazed-toy shading with clear soft highlights.
- **Palette:** `#7ed957` `#4fc3f7` `#ffd54f` `#ff8a65` `#f5f5f5` `#8d6e63` `#ba68c8`. Bright, clean primaries and pastels: grass green, sky blue, yellow, coral.
- **Lighting:** Bright, soft overhead light with gentle shadows.
- **Texture and surface:** Almost none; smooth moulded surfaces with simple painted colour areas. Grass and water are simplified glossy shapes.
- **Atmosphere and post-processing:** Strong tilt-shift blur at the top and bottom of the frame to give a miniature scale; light bloom.
- **Camera and framing:** High three-quarter view (50 to 60 degrees down) with a long lens.
- **UI and typography:** Panels are rounded glossy plaques with soft drop shadows, and icons are small chunky toy models of the items they stand for. Type is a friendly rounded sans in white or cream. Counters are bold rounded numerals that pop in with a small bounce, with grass green, sky blue, yellow and coral accents.
- **VFX and motion:** Particles are simple chunky shapes: puffy white smoke balls, star bursts, glossy leaf and water blobs. A hit gives a quick squash, a white flash and a pop. Motion is bouncy with squash and stretch, short waddling steps and a toy-like wobble.

## Fits

- **Genres:** `action-adventure`, `puzzle`, `simulation`, `exploration`, `tower-defense`, `survival-craft`
- **Moods:** cheerful, cosy, whimsical
- **Settings:** island village, tabletop dungeon, toy town, seaside meadow

## Unity recipe

### Assets

Small rounded toy-like forms: stubby characters with bead eyes, trees as glossy lumps, houses like moulded play-set pieces. Cute low-poly and cartoon packs fit after smoothing: subdivide and round them in Blender background mode, bevel every edge generously and recalculate smooth normals. Remove textures and assign simple painted colour areas per material slot. Grass is a smooth green surface, not blades; water is a glossy blue shape. Lay the world out as a compact tabletop diorama with a visible edge.

### Materials

`Universal Render Pipeline/Lit`, metallic 0, smoothness 0.6 to 0.75 for a moulded plastic or glazed finish with clear soft highlights, no normal maps. Water is opaque or slightly transparent Lit at smoothness 0.9. Bead eyes are black with smoothness 0.95. Unlike a brick look there are no seams or studs, and unlike clay there are no surface marks: surfaces are perfectly clean. No custom shader needed.

### Lighting and atmosphere

Bright, soft overhead light: a directional light at a steep angle with soft shadows at moderate strength, bright sky ambient. A baked reflection probe of a soft bright environment for the highlights. Shadow distance matched to the diorama size, four cascades not needed: one or two. SSAO on, gentle. No fog; a plain pastel backdrop.

### Post-processing

The tilt-shift is a custom effect, because Depth Of Field alone follows depth, not screen position. Add a Full Screen Pass Renderer Feature after post-processing that blurs the top and bottom bands of the frame: blur radius grows with vertical distance from a focus band centred on the player's screen height, using a separable or disc blur. Combine with a raised camera on a long lens. Light Bloom (threshold 1, low intensity), saturation +10, Neutral tonemapping. SMAA.

### UI and effects

Panels are rounded glossy plaques with soft drop shadows; icons are small chunky toy models rendered to sprites by an editor step. Font asset from a friendly rounded sans such as Nunito ExtraBold or Fredoka, white or cream; bold numerals pop in with a small bounce. Particles are simple chunky meshes: puffy white smoke balls, star bursts, glossy leaf and water blobs with the same Lit material. A hit gives a quick squash, a white flash and a pop. Add a toy-like wobble with a damped spring on scale.

## Do / Do not

Do:

- Round every form like a moulded toy.
- Blur the top and bottom of the frame.
- Use glossy clean materials.
- View from a high angle with a long lens.

Do not:

- Do not add fingerprints and matte clay; that reads as `048`.
- Do not build from studded bricks; that reads as `052`.
- Do not use low-poly blurry-textured forms without gloss; that reads as `037`.
- Do not use pixel sprites; that reads as `047`.

## Nearest styles

- `048` Claymation: surfaces here are smooth, glossy and clean, in many bright colours; `048` is matte clay with fingerprints and tool marks, in fewer colours.
- `037` N64 filtered fog: scenes here are bright, with smooth rounded glossy forms and blur only at the top and bottom of the frame; `037` has angular low-polygon models, blurry matte textures and distance fog.
- `052` Brick toy: this style has freeform rounded shapes in a wide range of soft bright colours; `052` assembles everything from studded bricks in a few strong solid plastic colours.

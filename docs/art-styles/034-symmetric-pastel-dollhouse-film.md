# Symmetric pastel dollhouse film

Reference works: The Grand Budapest Hotel.

## References

- *The Grand Budapest Hotel* (2014), Wes Anderson, live-action film. https://en.wikipedia.org/wiki/The_Grand_Budapest_Hotel
- *Moonrise Kingdom* (2012), Wes Anderson, live-action film. https://en.wikipedia.org/wiki/Moonrise_Kingdom
- *The Royal Tenenbaums* (2001), Wes Anderson, live-action film. https://en.wikipedia.org/wiki/The_Royal_Tenenbaums
- *Fantastic Mr. Fox* (2009), Wes Anderson, stop-motion film. https://en.wikipedia.org/wiki/Fantastic_Mr._Fox_(film)
- *Asteroid City* (2023), Wes Anderson, live-action film. https://en.wikipedia.org/wiki/Asteroid_City

## Visual definition

- **Shape language and proportions:** Real objects arranged like a dollhouse: boxy rooms seen straight-on, symmetric facades, tidy rows of props, model-like buildings and vehicles.
- **Line and outline:** No outline.
- **Shading model:** Photographic and smooth but flat: soft frontal light with weak shadows.
- **Palette:** `#f4b6c2` `#c75b7a` `#6b3fa0` `#f6e3b4` `#e8763a` `#7fb7be` `#8b2f2f`. Curated pastels: pink, lilac, cream and powder blue with red, purple and orange accents. Every object is colour-matched to the scheme.
- **Lighting:** Soft, even, frontal. Little contrast; no dramatic shadows.
- **Texture and surface:** Clean real materials: painted plaster, carpet, lacquer, uniforms. Tidy, not weathered.
- **Atmosphere and post-processing:** Slight warm grade, mild vignette, flat depth. Optional 4:3 framing.
- **Camera and framing:** Perfect one-point perspective, centred, level; planimetric framing with the camera perpendicular to the back wall; whip pans at 90 degrees.
- **UI and typography:** Centred, symmetric panels that look like title cards, hotel stationery and luggage labels, with thin double-rule borders; icons are flat badges and stamps. Titles use a hand-lettered sign-painter script, labels use widely spaced geometric sans capitals, and counters use tidy typewriter numerals. UI colours are pink `#f4b6c2` and cream `#f6e3b4` with dark red `#8b2f2f` text.
- **VFX and motion:** Effects look like stage props: small cotton-wool smoke puffs, paper confetti and neat dust puffs, with a tidy pop on impact and no sparks. Motion is brisk and deadpan: characters move in straight lines and right angles, hold poses, and start and stop suddenly, with a slight stop-motion feel.

## Fits

- **Genres:** `puzzle`, `detective-mystery`, `exploration`, `simulation`, `stealth`, `platformer`
- **Moods:** whimsical, deadpan, nostalgic
- **Settings:** grand alpine hotel, summer camp island, eccentric family townhouse, desert roadside town

## Unity recipe

### Assets

Clean, tidy interior and architecture packs: hotel rooms, lobbies, trains, offices, model-like buildings and vehicles. Arrange them like a dollhouse with boxy rooms open toward the camera and props in symmetric rows; write the placement step to mirror each room about its centre plane. Recolour every material to the curated scheme (pink, lilac, cream, powder blue with red, purple and orange accents) and remove weathering: delete dirt masks and even out roughness. Keep light material detail such as carpet pile and plaster.

### Materials

`Universal Render Pipeline/Lit` with matte settings: smoothness 0.1 to 0.3 for plaster, cloth and carpet, up to 0.6 for lacquer only. Normal maps stay but at low strength. The editor step applies `_BaseColor` tints from a palette table per object category so every object matches the scheme. No custom shader, no outline, no emissive glow.

### Lighting and atmosphere

Soft, even and frontal. Place large baked area lights behind the camera position for each room and a weak directional light with very soft shadows at reduced strength. Bake lightmaps and Adaptive Probe Volumes so rooms fill with bounced light and contrast stays low. No fog. SSAO on at low intensity for gentle contact. Reflection probes baked, low intensity.

### Post-processing

Neutral tonemapping, a slight warm White Balance, saturation -5, mild Vignette. No Depth Of Field: depth should look flat and everything stays sharp. No Bloom, no grain. A lens of 40 to 50 mm or an orthographic camera, always perpendicular to the back wall, centred and level; camera moves are lateral tracks and 90 degree turns. Optionally letterbox to 4:3 with UI bars. SMAA or MSAA 4x.

### UI and effects

Centred, symmetric panels like title cards, hotel stationery and luggage labels, with thin double-rule borders; icons are flat badges and stamps. Titles from a sign-painter script such as Yellowtail or Lobster; labels in widely spaced geometric capitals such as Josefin Sans; counters in typewriter numerals such as Courier Prime. `#f4b6c2` and `#f6e3b4` with `#8b2f2f` text. Effects are stage props: small cotton-wool smoke meshes, paper confetti quads, neat dust puffs with a tidy pop. Step some animation to twos and start and stop moves abruptly.

## Do / Do not

Do:

- Frame symmetric, centred and perpendicular to the back wall.
- Match every prop to a limited pastel scheme.
- Light softly from the front.
- Arrange props in ordered rows.

Do not:

- Do not use dramatic side light or deep shadow.
- Do not add atomic-age boomerang shapes and chrome; that reads as `099`.
- Do not miniaturise with blur and glossy plastic; that reads as `057`.
- Do not flatten to unlit isometric colour faces; that reads as `059`.

## Nearest styles

- `099` Atomic-age Googie: this style is boxy, matte and seen straight-on in soft muted pastels; `099` has glossy enamel and chrome, upswept curves and starbursts, and stronger turquoise and coral.
- `057` Toy-diorama tilt-shift: this style shows real-size plaster, carpet and cloth in sharp focus with muted pastels; `057` shows glossy moulded toys in brighter colours, with the top and bottom of the frame blurred like a photographed miniature.
- `059` Isometric pastel impossible architecture: this style is photographed rooms with soft continuous shading, seen straight-on; `059` is unlit geometric blocks seen from an isometric angle, each face one flat tone.

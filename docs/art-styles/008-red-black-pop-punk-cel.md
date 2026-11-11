# Red-black pop-punk graphic cel

Reference works: Persona 5.

## References

- *Persona 5* (2016), Atlus (P-Studio), video game. https://en.wikipedia.org/wiki/Persona_5
- *Persona 5 Royal* (2019), Atlus (P-Studio), video game. https://en.wikipedia.org/wiki/Persona_5
- *Persona 5 Strikers* (2020), Omega Force and P-Studio, video game. https://en.wikipedia.org/wiki/Persona_5_Strikers
- *Persona 3 Reload* (2024), Atlus (P-Studio), video game. https://en.wikipedia.org/wiki/Persona_3_Reload

## Visual definition

- **Shape language and proportions:** Slim anime proportions. The environment is cut into jagged, slanted shapes: torn-paper edges, star bursts, diagonal bars and skewed type blocks.
- **Line and outline:** Black outline of medium weight (2 to 4 px) on characters and props; white keylines around black shapes.
- **Shading model:** Two bands. Shadow is solid black or deep red, covering large areas.
- **Palette:** `#e60012` `#0d0d0d` `#ffffff` `#f5d400` `#3a3a3a` `#8c000a`. Pure red, black and white with one small yellow accent. Most of the frame is red or black.
- **Lighting:** Graphic, not physical: a hard key from one side so half of each form drops to black.
- **Texture and surface:** Flat fills with halftone dot gradients in red areas and rough torn-paper edges.
- **Atmosphere and post-processing:** Hard contrast. Optional posterise. No haze.
- **Camera and framing:** Dutch angles of 10 to 20 degrees, low wide shots, tight crops.
- **UI and typography:** UI is a main part of the image: skewed black and red panels with torn or jagged edges, white keylines and star bursts, layered at clashing angles. Type mixes heavy condensed sans capitals with ransom-note cut-out letters of mixed size and tilt. Numbers are large slanted white digits on black with a red offset shadow.
- **VFX and motion:** Hits trigger full-screen graphic cuts: red and black splash panels, star bursts, radiating speed lines and halftone wipes. Motion is snappy, with strongly held key poses, fast smears between them and freeze frames on finishing blows.

## Fits

- **Genres:** `rpg`, `stealth`, `hack-and-slash`, `fighting`, `detective-mystery`
- **Moods:** stylish, rebellious, tense
- **Settings:** modern Tokyo, night city, surreal palace

## Unity recipe

### Assets

Slim anime-proportioned character packs, and environments cut into jagged, slanted shapes. Build scenery from scratch with the Mesh API: skewed blocks, torn-edge planes, star-burst cut-outs, diagonal bars. On store assets remove all textures and assign red, black or white only, with `#f5d400` kept for one small accent per scene. Generate a halftone dot gradient texture and torn-paper edge masks by script.

### Materials

Write `Style/PunkCel`. `UniversalForward` takes `GetMainLight(shadowCoord)` and a single `step` on NdotL set so about half of each form falls in shadow; the shadow band outputs solid `#0d0d0d` or `#8c000a` per material. In red lit areas, a screen-space dot pattern (rotated grid, dot radius driven by NdotL) gives the halftone gradient. Outline by inverted hull in an `SRPDefaultUnlit` pass at 2 to 4 px in black; black-surfaced materials switch the hull to white so black shapes carry a white keyline. Include `ShadowCaster`, `DepthOnly`, `DepthNormals`.

### Lighting and atmosphere

One hard directional key from the side, hard shadows, soft shadows off, shadow colour treated as pure black by the shader. Ambient near zero in the shader maths; set a flat ambient only for particles. No fog, no SSAO, no reflection probes. Background is flat red or black.

### Post-processing

Tonemapping None. Color Adjustments with contrast +30. A Full Screen Pass Renderer Feature before post-processing posterises luminance to three levels and snaps hue to the red, black and white set; a second optional pass draws a white keyline at depth edges that border black regions. No Bloom, haze or grain. Tilt gameplay cameras 10 to 20 degrees.

### UI and effects

UI is part of the picture: skewed black and red panels with jagged edges and white keylines, stacked at clashing angles. Use Anton for heavy condensed capitals; make ransom-note text by setting each character in a different font asset, size and rotation through TextMeshPro rich text and per-character vertex edits. Numbers are slanted white digits with a red underlay offset. Hits trigger full-screen UI cuts: red and black splash panels, star bursts, radial speed-line sprites and a halftone wipe driven by a threshold animation, with a short freeze.

## Do / Do not

Do:

- Keep nearly the whole frame in red, black or white.
- Tilt the camera and shear the geometry.
- Let shadows drop to solid black.
- Use white keylines to separate black from black.

Do not:

- Do not add more hues; that reads as `004`.
- Do not remove red and keep only black with one small colour spot; that reads as `069`.
- Do not use muted colours under heavy black; that reads as `010`.
- Do not apply halftone over the full frame with colour offsets; that reads as `009`.

## Nearest styles

- `069` Selective-colour ink noir: this style floods the frame with pure red next to black and white; `069` is black and white with only one small spot of colour.
- `010` Heavy-black gothic comic: this style is dominated by pure bright red, with halftone gradients and torn-paper edges; `010` uses muted slate, olive and ochre under heavier black, with perfectly flat colour.
- `080` Constructivist agit poster: this style is a dark frame of red and black with outlined characters; `080` sits on light yellowed paper with unoutlined flat shapes and thin ruled lines.

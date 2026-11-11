# Manga screentone monochrome

Reference works: Berserk; Akira (manga).

## References

- *Berserk* (1989), Kentaro Miura, manga. https://en.wikipedia.org/wiki/Berserk_(manga)
- *Akira (manga)* (1982), Katsuhiro Otomo, manga. https://en.wikipedia.org/wiki/Akira_(manga)
- *Lone Wolf and Cub* (1970), Kazuo Koike and Goseki Kojima, manga. https://en.wikipedia.org/wiki/Lone_Wolf_and_Cub
- *Vagabond* (1998), Takehiko Inoue, manga. https://en.wikipedia.org/wiki/Vagabond_(manga)

## Visual definition

- **Shape language and proportions:** Realistic to semi-realistic drawing with dramatic foreshortening. Any subject; forms are described by line density.
- **Line and outline:** Black pen line with clear weight variation on every contour. Speed lines and focus lines radiate from the subject.
- **Shading model:** Tone comes from screentone: regular dot patterns at 2 or 3 fixed densities, plus solid black. No grey pixels; grey is always dots.
- **Palette:** `#000000` `#ffffff` `#8c8c8c` `#4d4d4d` `#d9d9d9`. Pure black and white. The grey values listed are the apparent tones of screentone at viewing distance.
- **Lighting:** Strong directional light so forms split into white, toned and black areas.
- **Texture and surface:** Dot screens at 45 degrees, fine pen hatching on rough materials, white highlights scratched out of tone.
- **Atmosphere and post-processing:** Threshold to two values. Optional panel border in black.
- **Camera and framing:** Dramatic angles, close-ups and wide establishing shots; any lens.
- **UI and typography:** White panels with black borders laid out like manga page frames, plus speech balloons and jagged shout balloons. Text is hand-lettered comic capitals in black, with heavy brush-drawn sound-effect lettering for emphasis. Damage numbers and counters are thick black brush numerals with a white edge; bars are solid black or filled with dot tone, never grey.
- **VFX and motion:** Effects are ink marks: radial speed lines, black ink splashes, white slash arcs scratched across tone, dust clouds drawn as outlined shapes with dot tone, and large sound-effect lettering on impact. Animation holds strong poses on twos or threes, with a one-frame black and white inversion on heavy hits.

## Fits

- **Genres:** `hack-and-slash`, `soulslike`, `fighting`, `action-adventure`, `survival-horror`, `detective-mystery`
- **Moods:** grim, intense, dramatic
- **Settings:** feudal Japan, dark medieval battlefield, post-apocalyptic city, demon-haunted castle

## Unity recipe

### Assets

Any realistic or semi-realistic pack works because colour is discarded; pick models with strong forms that split well under hard light. Remove colour textures and keep only a greyscale value per material (white, tone A, tone B or black). Keep normal maps at reduced strength for rough materials. Generate by script: dot screen tiles at two or three fixed densities, a pen-hatch tile, and radial speed-line and focus-line sprites.

### Materials

Write `Style/Screentone`. `UniversalForward` computes a tone value from `GetMainLight(shadowCoord)`, NdotL and the material's base value, then selects one of four outputs: white, light dots, dense dots, or solid black. Dots are drawn in screen space on a grid rotated 45 degrees with a fixed pixel pitch (about 6 px at 1080p) and fixed radius per density, and the output is strictly 0 or 1: no grey is ever written. A `_HATCH` keyword swaps dots for pen hatching on rough materials. A specular threshold cuts pure white highlights out of tone. The pen outline is an `SRPDefaultUnlit` hull pass with width varied by vertex colour and view angle. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`.

### Lighting and atmosphere

One strong directional light with hard shadows so each form divides into white, tone and black. Ambient ignored. No fog, GI, SSAO or probes. The background is white, like an open page.

### Post-processing

A Full Screen Pass Renderer Feature after post-processing thresholds the final image to pure black and white as a safety net and adds inner crease lines from depth and normals. Tonemapping None, HDR off. Anti-aliasing off or MSAA only on geometry edges; do not blur dots, and keep render scale at 1 so the dot pitch stays regular. Optionally draw a black panel border.

### UI and effects

White panels with black borders arranged like page frames, speech balloons and jagged shout balloons. Hand-lettered capitals from a comic face such as Bangers or Comic Neue Bold; brush sound-effect lettering from a heavy brush face such as Dela Gothic One or Rock Salt. Bars are solid black or dot-filled, never grey. Effects are ink marks: radial speed-line sprites, black splash flipbooks, white slash arcs, outlined dust clouds with dot fill. On heavy hits invert the frame for one frame, and hold poses on twos or threes.

## Do / Do not

Do:

- Output only pure black and pure white pixels.
- Use dot screens at fixed densities for tone.
- Vary pen line weight.
- Add radial speed or focus lines for action.

Do not:

- Do not use ordered or noise dithering over the full frame at low resolution; that reads as `041`.
- Do not build tone from long parallel engraved lines; that reads as `072`.
- Do not allow grey or coloured fills.
- Do not add a single colour accent; that reads as `069`.

## Nearest styles

- `041` One-bit dither: `041` is a dark, low-resolution image where pixel-sized dither patterns cover the whole frame and there is no pen line; this style is a mostly white page with drawn pen outlines and clean dot tone in chosen areas.
- `072` Engraved crosshatch print: `072` builds all its tone from long parallel and crossed engraved lines; this style builds tone from regular dot screens and solid black.
- `073` Graphite pencil sketch: `073` has soft grey pencil tones and smudged edges on paper; this style has only pure black and pure white with sharp pen edges.

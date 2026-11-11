# Neon grid cyberspace

Reference works: Tron.

## References

- *Tron* (1982), Steven Lisberger (Walt Disney Productions), live-action and computer-animated film. https://en.wikipedia.org/wiki/Tron
- *Tron: Legacy* (2010), Joseph Kosinski (Walt Disney Pictures), live-action film. https://en.wikipedia.org/wiki/Tron:_Legacy
- *Tron 2.0* (2003), Monolith Productions, video game. https://en.wikipedia.org/wiki/Tron_2.0
- *Rez* (2001), United Game Artists, video game. https://en.wikipedia.org/wiki/Rez_(video_game)

## Visual definition

- **Shape language and proportions:** A digital world of smooth dark geometric solids: slabs, towers, ramps, discs and vehicles with clean chamfered forms. Bodies and vehicles carry thin circuit-like light lines. The ground is an infinite grid.
- **Line and outline:** No dark outline. Bright emissive lines trace edges and circuit paths on dark surfaces.
- **Shading model:** Surfaces are near-black with faint glossy reflection; almost all visible form comes from emissive lines and their glow.
- **Palette:** `#020308` `#0a1220` `#18e0ff` `#ff7a1a` `#e8fbff` `#123a5a`. Black and deep blue-black, with cyan-white light for one faction and orange for the other.
- **Lighting:** Self-illumination only. Emissive strips cast soft coloured glow onto nearby dark surfaces and reflect in the glossy floor.
- **Texture and surface:** None apart from circuit line patterns and the floor grid.
- **Atmosphere and post-processing:** Strong bloom on emissive lines, light trails behind moving vehicles, slight reflection blur.
- **Camera and framing:** Low wide shots along the grid; fast lateral tracking.
- **UI and typography:** Frames are thin glowing cyan lines with chamfered corners on black, with no filled panels; icons are single-weight line glyphs. Text is a wide geometric sans in capitals with squared letterforms. Counters use a monospaced digital face, cyan-white for the player and orange for enemies and warnings.
- **VFX and motion:** A hit breaks the target into glowing square fragments that scatter and fade; vehicles leave solid light trails or light walls, and thrown discs leave thin arcs. Motion is fast and precise, with sharp 90-degree turns, constant speed and little easing.

## Fits

- **Genres:** `racing`, `vehicle-combat`, `fps`, `third-person-shooter`, `fighting`, `top-down-shooter`
- **Moods:** cold, sleek, tense
- **Settings:** inside a computer, digital arena, light-cycle grid

## Unity recipe

### Assets

Smooth dark geometric solids with clean chamfers: slabs, towers, ramps, discs, vehicles and suited figures. Build them from scratch with ProBuilder's API or use clean sci-fi packs with textures removed. Light lines are designed, not edge-detected: an editor step generates thin emissive strip geometry along chosen edges and circuit paths, or paints an emission mask in a second UV set. The ground is an infinite grid plane.

### Materials

Body surfaces use `Universal Render Pipeline/Lit`: albedo near-black `#020308` to `#0a1220`, smoothness 0.8 to 0.9, metallic 0, so they stay dark but reflect glow. Light strips use Lit with `_EMISSION` or `Universal Render Pipeline/Unlit` with HDR colour (cyan-white `#18e0ff` or orange `#ff7a1a` at intensity 3 to 6); faction colour is a shared material property. The floor uses a custom shader, `Style/GridFloor`, calling `UniversalFragmentPBR` with a procedural anti-aliased grid (using `fwidth` on world XZ) written to emission and high smoothness for reflections. Standard Lit passes. Light walls and trails are emissive transparent meshes.

### Lighting and atmosphere

Self-illumination only. No directional light, no sky: black background and near-black ambient. For glow cast on nearby surfaces, attach small point lights or short-range spot lights to major strips (Forward+ for count), and mark static emissive strips as contributing to baked GI with Adaptive Probe Volumes. Reflections on the glossy floor need a realtime or frequently updated reflection probe for the hero area, or a mirrored-camera planar reflection texture for the floor. Faint deep-blue fog (`#123a5a`) for depth. No SSAO.

### Post-processing

Strong Bloom: threshold 1, intensity 1.5 to 2.5, scatter 0.7, with high quality filtering. Neutral tonemapping to keep line colours pure. Slight Vignette. No grain, scanlines or Chromatic Aberration. HDR on, MSAA 4x or SMAA to keep thin strips stable.

### UI and effects

Frames are thin glowing cyan lines with chamfered corners on black, no filled panels; icons are single-weight line glyphs. Font asset from a wide squared geometric sans such as Orbitron or Michroma in capitals; counters in a monospaced digital face such as Share Tech Mono; cyan-white for the player, orange for enemies and warnings. A hit swaps the target for glowing cube fragments that scatter and fade. Vehicles leave solid light walls (procedural mesh extended each frame) and discs leave thin `TrailRenderer` arcs. Motion uses constant speed, sharp 90-degree turns and almost no easing.

## Do / Do not

Do:

- Keep surfaces near-black and glossy.
- Trace edges and circuits with emissive lines.
- Use at most two emissive colours.
- Add strong bloom and a grid floor.

Do not:

- Do not draw wireframe only without solid surfaces; that reads as `040`.
- Do not add a magenta sunset and purple gradients; that reads as `090`.
- Do not add rain, haze and many sign colours; that reads as `089`.
- Do not light surfaces with white diffuse light.

## Nearest styles

- `040` Vector display glow: this style has solid near-black surfaces with glossy reflections under the light lines; `040` is glowing lines only on empty black, with nothing solid.
- `090` Synthwave sunset grid: this style is almost wholly black with one or two line colours; `090` has a bright gradient sky, a striped sun, and magenta, purple and orange together.
- `089` Rain-soaked tech-noir: this style has clean black solids lit only by their own lines; `089` is a fully shaded realistic wet city with haze, grime and many sign colours.

# Shadow-puppet cut-out

Reference works: The Adventures of Prince Achmed.

## References

- *The Adventures of Prince Achmed* (1926), Lotte Reiniger, silhouette animated film. https://en.wikipedia.org/wiki/The_Adventures_of_Prince_Achmed
- *Tales of the Night* (2011), Michel Ocelot, animated film. https://en.wikipedia.org/wiki/Tales_of_the_Night_(film)
- *Badland* (2013), Frogmind, video game. https://en.wikipedia.org/wiki/Badland_(video_game)

## Visual definition

- **Shape language and proportions:** All figures and scenery are flat black cut-outs with intricate lace-like perforations: filigree costumes, leaf-by-leaf trees, ornate arches. Figures are in strict profile with jointed limbs.
- **Line and outline:** No line. The silhouette edge is the drawing.
- **Shading model:** None. Foreground shapes are solid black; depth layers behind are progressively lighter translucent tones.
- **Palette:** `#000000` `#f2a23a` `#d9482b` `#2a6f97` `#f6e3b4` `#7a3b69`. Black over a luminous coloured background: amber, red-orange, or deep blue, with a soft bright centre.
- **Lighting:** Back-lit screen: a glowing light source behind translucent layers.
- **Texture and surface:** None in the black. The backlight has a soft gradient and faint paper or tissue mottling.
- **Atmosphere and post-processing:** Slight glow bleeding around silhouette edges; vignette.
- **Camera and framing:** Fixed, flat, orthographic side view.
- **UI and typography:** All UI is black cut-out: filigree frames, perforated borders and silhouette icons laid over the glowing backdrop. Type is an ornate cut-paper display face with thin serifs and curled flourishes, in solid black or cut through so the backlight shows as amber letters. Numbers are plain black silhouette numerals.
- **VFX and motion:** Effects are silhouettes too: black paper sparks and leaves, smoke as layered translucent tissue, and magic as bright holes of backlight that flare through the black. Figures move like jointed puppets, with limbs that pivot at pin joints, a slight frame-by-frame jitter and held profile poses.

## Fits

- **Genres:** `platformer`, `puzzle`, `action-adventure`, `stealth`, `exploration`
- **Moods:** enchanted, eerie, theatrical
- **Settings:** Arabian Nights palace, enchanted forest, fairy-tale kingdom

## Unity recipe

### Assets

All figures and scenery are flat cut-outs. Build them from scratch: draw silhouettes with lace-like perforations by script (filigree costumes, leaf-by-leaf trees, ornate arches) into high-resolution alpha textures (2048 to 4096 px, since the edge is the whole drawing), or generate true meshes from vector outlines. Figures are in strict profile, split into limb pieces joined at pin joints and animated by rotating the pieces. Store 3D models can be rendered side-on to silhouette masks by an editor step camera. Arrange layers at set depths in front of a backdrop plane.

### Materials

Foreground cut-outs use `Universal Render Pipeline/Unlit`, black, alpha clip with a high-resolution mask (or an SDF mask for a crisp edge at any zoom). Deeper layers use a transparent unlit shader whose colour is a lighter translucent tone, lerped toward the backdrop by layer depth. The backdrop is an unlit HDR shader: a radial gradient from a soft bright centre (`#f6e3b4`) to amber, red-orange or deep blue, multiplied by faint tissue mottling. No lighting functions and no shadow passes anywhere; `DepthOnly` is optional.

### Lighting and atmosphere

No lights. Shadows off in the URP asset, no fog, no SSAO, no probes. Use an orthographic camera or a long lens facing the screen. Depth is shown by layer tone only.

### Post-processing

Bloom makes the backlight bleed around silhouette edges: threshold just under the backdrop's brightness, low intensity, medium scatter. Vignette 0.4. Tonemapping Neutral, HDR on. MSAA 8x or SMAA so the perforations stay clean. No grain: this is a glowing coloured screen, not a grey foggy film image.

### UI and effects

All UI is black cut-out: filigree frames, perforated borders, silhouette icons over the backdrop. Font asset from an ornate thin-serif display face such as Cinzel Decorative or Fredericka the Great, in solid black, or inverted so letters are holes showing amber. Numerals are plain black silhouettes. Effects are silhouettes: black paper sparks and leaves as alpha-clipped particles, smoke as layered translucent tissue shapes, magic as bright holes that open in the black (emissive sprites above the bloom threshold). Add a slight per-frame positional jitter and step limb rotation on twos.

## Do / Do not

Do:

- Keep all foreground shapes solid black.
- Cut fine perforations into silhouettes.
- Use a glowing coloured backdrop with a bright centre.
- Stage in flat profile with an orthographic camera.

Do not:

- Do not use grey fog and film grain without colour; that reads as `070`.
- Do not add incised line detail inside figures on an orange ground; that reads as `087`.
- Do not light the figures from the front.
- Do not use a few coloured flat shapes without black dominance; that reads as `064`.

## Nearest styles

- `070` Silhouette fog monochrome: backdrops here glow amber, red-orange or deep blue; `070` is entirely grey, with fog and film grain.
- `087` Greek black-figure pottery: figures here are pure black, with detail only as holes cut through to a glowing backlight; `087` scratches fine light lines inside its black figures and sets them on a flat, unlit terracotta ground.
- `064` Mid-century cut-paper poster: this style is dark, with black shapes filling most of the frame over a glowing backdrop; `064` is a bright poster of a few flat coloured paper shapes with little black.

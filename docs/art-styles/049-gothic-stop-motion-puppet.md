# Gothic stop-motion puppet

Reference works: The Nightmare Before Christmas; Coraline.

## References

- *The Nightmare Before Christmas* (1993), Henry Selick (Touchstone Pictures and Skellington Productions), stop-motion film. https://en.wikipedia.org/wiki/The_Nightmare_Before_Christmas
- *Coraline* (2009), Laika (Henry Selick), stop-motion film. https://en.wikipedia.org/wiki/Coraline_(film)
- *Corpse Bride* (2005), Tim Burton and Mike Johnson, stop-motion film. https://en.wikipedia.org/wiki/Corpse_Bride
- *ParaNorman* (2012), Laika, stop-motion film. https://en.wikipedia.org/wiki/ParaNorman
- *Frankenweenie* (2012), Tim Burton, stop-motion film. https://en.wikipedia.org/wiki/Frankenweenie_(2012_film)

## Visual definition

- **Shape language and proportions:** Thin, elongated puppets: stick limbs, tiny waists, very large heads with huge round eye sockets. Sets are crooked: leaning houses, spiral hills, twisted fences and bare trees.
- **Line and outline:** No outline. Painted stripes and stitches act as graphic line.
- **Shading model:** Smooth, photographed-miniature shading with hard theatrical shadows.
- **Palette:** `#14141c` `#3b3350` `#6b6f7a` `#c9c2b0` `#d9772b` `#5a7a4a` `#8a2f3a`. Dark blue-violet and grey with bone white, and pumpkin orange or sickly green accents.
- **Lighting:** Low-key stage lighting: strong back and side light, long distorted shadows, a large moon disc.
- **Texture and surface:** Hand-made miniature materials: painted resin, wire, fabric, scratched wood, with visible paint strokes and stitched seams.
- **Atmosphere and post-processing:** Vignette, slight depth of field, light fog; animation stepped on twos.
- **Camera and framing:** Low and wide for sets, tilted compositions; macro-like for faces.
- **UI and typography:** Frames are twisted wrought iron with curled spiral ends, or stitched fabric patches; icons are small props such as buttons, keys, bones and pumpkins. Lettering is a tall, spindly hand-drawn serif with uneven letter heights and curled tails. Counters are thin scratchy numerals in bone white `#c9c2b0` on dark violet `#3b3350`, with pumpkin orange `#d9772b` for highlights.
- **VFX and motion:** Effects look hand-made: cotton fog, paper bats and leaves, flickering candle glow, sickly green wisps, a puff of dust on impact. Animation runs on twos with slightly jerky stop-motion timing, long gliding strides, spidery limb gestures and sharp held poses.

## Fits

- **Genres:** `action-adventure`, `platformer`, `stealth`, `puzzle`, `exploration`, `survival-horror`
- **Moods:** macabre, whimsical, eerie
- **Settings:** haunted town, graveyard hill, crooked old house, twisted forest

## Unity recipe

### Assets

Thin, elongated puppets: scale bones or edit meshes for stick limbs, tiny waists and very large heads with deep round eye sockets. Sets are crooked: shear and bend pack buildings, fences and trees with a lattice or vertex transform in an editor step so nothing is vertical; build spiral hills from scratch. Repaint textures as hand-painted miniatures: flat muted base colours with visible paint strokes, painted stripes and stitched seams drawn in by script. Keep modest normal maps for fabric and scratched wood.

### Materials

`Universal Render Pipeline/Lit` with low to mid smoothness: painted resin about 0.4, fabric 0.1, wire as dark metal. Stripes and stitches live in the albedo and act as graphic line; no outline shader. A large moon disc is an unlit emissive mesh. Candle and wisp glow use emissive Lit materials plus small point lights. No custom lighting model is needed; what separates this from a clay look is thin shapes, a dark palette and hard theatrical light, not the shader.

### Lighting and atmosphere

Low-key stage lighting. Strong spot lights from behind and the side with hard shadows (soft shadows off or low) so long distorted shadows fall across the set; place lights low to stretch them. A cold blue directional moon light as rim. Ambient dark blue-violet (`#14141c` to `#3b3350`). Light exponential fog in violet-grey, plus cotton-like fog cards near the ground. Bake a dim probe set if interiors need fill. SSAO on, low. Shadow distance short for miniature scale.

### Post-processing

Vignette 0.4 to 0.5, slight Depth Of Field in Bokeh mode, Neutral tonemapping with lowered saturation except orange and green accents (use Color Curves hue-versus-saturation, or keep accents emissive). No Bloom beyond candle flames, no Motion Blur. SMAA.

### UI and effects

Frames are twisted wrought iron with spiral ends or stitched fabric patches as sprites; icons are small props (buttons, keys, bones, pumpkins) rendered from models. Font asset from a tall spindly hand-drawn face such as Amatic SC or Mountains of Christmas, with a per-character baseline jitter applied through TextMeshPro vertex edits. Thin numerals in `#c9c2b0` on `#3b3350`, `#d9772b` for highlights. Effects look hand-made: paper bats and leaves as textured quads, candle flicker by light-intensity noise, sickly green wisps, a dust puff on impact. Step animation on twos with sharp held poses.

## Do / Do not

Do:

- Elongate limbs and enlarge heads.
- Twist and lean every building.
- Backlight with a moon and cast long shadows.
- Paint stripes and stitches on surfaces.

Do not:

- Do not use chunky rounded clay in bright colours; that reads as `048`.
- Do not go fully greyscale with painted-on shadows on flat sets; that reads as `071`.
- Do not use photoreal stone architecture and fog; that reads as `031`.
- Do not use flat black silhouettes; that reads as `070`.

## Nearest styles

- `048` Claymation: `048` is bright and warm, with chunky rounded clay figures; this style is dark and muted, with thin elongated puppets.
- `071` Expressionist painted set: `071` is nearly monochrome, with light and shadow painted onto flat sets; this style has real smooth light on 3D miniatures and orange or green colour accents.
- `031` Gothic dark-fantasy realism: `031` is photoreal, with dense stone and material detail; this style looks like hand-made miniatures, with a limited palette and simple painted surfaces.

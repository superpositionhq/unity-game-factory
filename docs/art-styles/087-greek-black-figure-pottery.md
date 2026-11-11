# Greek black-figure pottery

Reference works: Exekias; Apotheon.

## References

- *Achilles and Ajax playing a board game (Vatican amphora)* (c. 540-530 BC), Exekias, black-figure amphora. https://en.wikipedia.org/wiki/Exekias
- *Francois Vase* (c. 570 BC), Kleitias and Ergotimos, black-figure krater. https://en.wikipedia.org/wiki/François_Vase
- *Apotheon* (2015), Alientrap, video game. https://en.wikipedia.org/wiki/Apotheon
- *Hercules* (1997), Walt Disney Feature Animation, animated film. https://en.wikipedia.org/wiki/Hercules_(1997_film)

## Visual definition

- **Shape language and proportions:** Figures as black silhouettes in strict profile: profile head with frontal eye, frontal torso, profile legs; long limbs, pointed beards and feet. Shields, spears, horses, chariots. Bands of ornament divide the surface.
- **Line and outline:** Fine incised lines inside the black figures, showing the clay colour: muscles, hair, armour patterns, drapery folds.
- **Shading model:** None. Flat black on flat orange.
- **Palette:** `#c96a2b` `#1a1512` `#e08a45` `#7a2f1a` `#f2e2c4` `#5a2a1a`. Orange terracotta ground and glossy black, with small added dark red and white (cream) details.
- **Lighting:** None in the image. On a real vessel, a soft highlight on the curved glazed surface.
- **Texture and surface:** Ornament bands: meander (Greek key), palmettes and lotus chains, rays at the base, tongues at the shoulder. Slight clay speckle; brush streaks in the black gloss.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Side-on frieze view, orthographic; or a product view of a vessel.
- **UI and typography:** Panels are terracotta-orange fields or black bands edged with a meander strip; icons are black silhouettes with incised detail (helmet, shield, lyre, amphora). Text is in monoline capitals with the angular letterforms of Greek inscriptions, black on orange or cream on black. Numbers use the same face, with dark red for damage.
- **VFX and motion:** Particles are flat black or cream shapes: dust as scalloped silhouettes, blood as dark red drops, fire as stylised flame tongues. A hit flashes the figure cream or dark red for one frame, with short radiating lines. Animation is stiff profile poses on twos, with limbs that rotate like jointed cut-outs.

## Fits

- **Genres:** `hack-and-slash`, `platformer`, `action-adventure`, `fighting`, `sports`, `strategy`
- **Moods:** heroic, mythic, austere
- **Settings:** ancient Greece, Mount Olympus, the underworld, Trojan battlefield

## Unity recipe

### Assets

Figures are black silhouettes in strict profile with frontal eye and torso, long limbs, pointed beards and feet; shields, spears, horses, chariots. Build them as flat jointed cut-out meshes (separate limb pieces rotating at pivots) from script-drawn outlines, each with an incision texture: fine lines for muscles, hair, armour patterns and drapery folds. Generate ornament bands by script: meander, palmette and lotus chains, rays, tongues. For a 3D variant, wrap the frieze onto vessel-shaped or cylindrical surfaces. Generate a clay-speckle texture and a brush-streak texture for the black gloss.

### Materials

Write `Style/BlackFigure`, essentially unlit. `UniversalForward` outputs terracotta `#c96a2b` with clay speckle for the ground, and for figures glossy black `#1a1512` with faint brush streaks; where the incision texture is set, output the clay colour instead, so interior lines are the ground showing through, never white or drawn in a lighter paint. Added dark red `#7a2f1a` and cream `#f2e2c4` details come from two more mask channels. On curved vessels, add one soft specular highlight from `GetMainLight()` restricted to the black gloss. Passes: `DepthOnly`; no shadows.

### Lighting and atmosphere

None in the image: flat ambient, shadows off, no fog, SSAO or probes. The optional directional light only feeds the single soft highlight on curved glaze. The background is the flat orange ground, unlit and without gradient or glow.

### Post-processing

None. Tonemapping None; no Bloom, vignette or grain. MSAA 8x or SMAA so incised lines stay fine and clean. Orthographic or long-lens camera.

### UI and effects

Panels are terracotta fields or black bands edged with a meander strip; icons are black silhouettes with incised detail (helmet, shield, lyre, amphora). Text in monoline capitals with angular inscription letterforms: a font asset from a face such as GFS Neohellenic or Julius Sans One, black on orange or cream on black; dark red for damage. Particles are flat shapes: scalloped dust silhouettes, dark red drops, stylised flame tongues. A hit tints the figure cream or dark red for one frame and adds short radiating lines. Animate stiff profile poses on twos by rotating limb pieces in steps.

## Do / Do not

Do:

- Draw figures as black profile silhouettes on orange.
- Incise fine clay-coloured detail lines inside figures.
- Add meander and palmette bands.
- Keep everything on a baseline frieze.

Do not:

- Do not use a glowing gradient backlight with lace-like perforations; that reads as `058`.
- Do not reverse to orange figures with black background without incised lines (that is red-figure, a different target).
- Do not add shading or perspective.
- Do not add more colours; that reads as `086`.

## Nearest styles

- `058` Shadow-puppet cut-out: this style has a flat orange ground and fine clay-coloured lines cut inside the black figures; `058` has a glowing gradient backdrop and pure black silhouettes with lace-like perforations and no interior lines.
- `086` Insular illuminated manuscript: this style uses only black and orange with small touches of dark red and cream; `086` uses many strong colours on a cream vellum ground.
- `064` Mid-century cut-paper poster: this style has dark figures with incised detail on orange, between regular ornament bands; `064` is a lighter picture of plain cut shapes with crooked edges and no interior detail.

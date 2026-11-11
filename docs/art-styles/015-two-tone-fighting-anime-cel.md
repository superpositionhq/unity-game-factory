# Two-tone fighting-anime cel

Reference works: Guilty Gear Xrd.

## References

- *Guilty Gear Xrd* (2014), Arc System Works, video game. https://en.wikipedia.org/wiki/Guilty_Gear_Xrd
- *Dragon Ball FighterZ* (2018), Arc System Works, video game. https://en.wikipedia.org/wiki/Dragon_Ball_FighterZ
- *Guilty Gear Strive* (2021), Arc System Works, video game. https://en.wikipedia.org/wiki/Guilty_Gear_Strive
- *Naruto: Ultimate Ninja Storm* (2008), CyberConnect2, video game. https://en.wikipedia.org/wiki/Naruto:_Ultimate_Ninja_Storm

## Visual definition

- **Shape language and proportions:** Dynamic anime figures: long legs, sharp angular hair chunks, oversized weapons and belts. Forms are designed so shadow shapes look drawn.
- **Line and outline:** Clean black outline, 2 to 3 px, tapering to nothing at some points; a few drawn inner lines (muscle, folds).
- **Shading model:** Two bands with a crisp edge whose shape is art-directed (edited normals). Shadow colour is a hue-shifted, saturated tint. Hard-edged specular shapes on hair and metal.
- **Palette:** `#141414` `#e63946` `#f1faee` `#ffb703` `#219ebc` `#8338ec` `#ffd6a5`. Strong character colours (red, gold, blue, purple) with pure white highlights.
- **Lighting:** Light direction follows the character, not the scene, to keep shadow shapes attractive.
- **Texture and surface:** Flat colour. Inner lines are stored as straight, axis-aligned texture strokes so they stay sharp.
- **Atmosphere and post-processing:** Bright bloom on effects only; otherwise clean.
- **Camera and framing:** Side-on fighting view or dramatic close-ups with speed lines.
- **UI and typography:** Sharp angled health and tension bars with black frames, gold trim and red or blue fills; character portraits sit in slanted cut frames. Text is a heavy italic display face with pointed corners, joined by rough brush-script callouts for round starts and knockouts. Combo and damage counters are large slanted white numerals with a black outline that punch in at oversize and settle.
- **VFX and motion:** Effects look hand-drawn: flat-colour slash arcs, jagged impact stars, smoke drawn as solid shapes and bright beams with bloom. Animation uses snappy held poses with stepped timing, hit-stop freezes on contact, smear frames and brief full-screen flashes.

## Fits

- **Genres:** `fighting`, `hack-and-slash`, `action-adventure`, `rpg`, `roguelike`
- **Moods:** intense, flashy, heroic
- **Settings:** tournament arena, ninja village, ruined gothic city, floating sky fortress

## Unity recipe

### Assets

Anime character packs with long legs, sharp hair chunks and oversized weapons. This style needs mesh work more than textures: in Blender background mode, edit vertex normals (data transfer from simple proxy shapes on faces and hair) so the shadow edge is a clean designed curve, and store a shadow-bias value in vertex colour to force or forbid shadow in chosen areas. Replace textures with flat colours. Inner lines are a separate small texture of straight, axis-aligned strokes mapped with rectangular UV islands so they stay sharp at any size.

### Materials

Write `Style/FightCel`. In `UniversalForward`, light direction is not the scene's: a script sets a per-character `_CharLightDir` so shadow shapes stay attractive. Use `step(threshold - vertexColor.r, NdotL)` for two bands with a crisp edge; the shadow colour is the base hue-shifted and more saturated, supplied as a second colour or texture. Add hard specular shapes on hair and metal with a thresholded half-vector term, and multiply by the inner-line texture. The outline is an `SRPDefaultUnlit` hull pass, black, 2 to 3 px, with width scaled by a vertex colour channel so lines taper to nothing at chosen points. Add `ShadowCaster`, `DepthOnly`, `DepthNormals`. Stage geometry can use the same shader with the scene light.

### Lighting and atmosphere

One directional light for the stage, hard shadows; characters ignore received shadow on the body (`_RECEIVE_SHADOWS_OFF`) and drop a simple blob or a hard cast shadow on the floor only. Flat ambient. No fog, SSAO or probes.

### Post-processing

Bloom is for effects only: give effect materials HDR colours above the threshold (about 1.2) and keep character colours below it. Tonemapping Neutral. No grain or vignette. MSAA 4x. Full-screen white flashes on heavy hits come from a UI overlay, one or two frames long.

### UI and effects

Angled health and tension bars with black frames, gold trim and red or blue fills; portraits in slanted cut frames. Heavy italic display face such as Russo One or Anton set italic, with a brush script such as Permanent Marker for round calls. Combo numerals punch in at 160 percent and settle. Effects are flipbook slash arcs, jagged impact stars and solid smoke shapes at 12 to 15 frames per second, plus HDR beams. Use hit-stop by pausing both animators for a few frames, and stepped clip timing.

## Do / Do not

Do:

- Edit normals so shadow edges are simple drawn curves.
- Pick shadow colours by hand per region.
- Taper outline width to zero at spikes and tips.
- Use hard-edged specular shapes.

Do not:

- Do not use the mesh's raw normals on faces; noisy shadow shapes break the look.
- Do not add graffiti textures and uniform fat lines; that reads as `004`.
- Do not soften bands and add gradient ramps and haze; that reads as `018`.
- Do not add hatching; that reads as `001`.

## Nearest styles

- `018` Soft open-world anime cel: `018` has thin tinted outlines, soft shadow edges, pastel colour and light haze; this style has black tapered outlines, razor-sharp shadow edges and strong colour.
- `004` Graffiti street cel: `004` wraps everything in fat lines of one width and covers walls and clothes with graffiti art; this style tapers its lines to points and keeps surfaces as plain flat colour.
- `019` Mecha panel-line cel: `019` shows white armoured machines with a few primary colour blocks and straight panel lines; this style shows organic characters in many strong colours with curved, drawn shadow shapes.

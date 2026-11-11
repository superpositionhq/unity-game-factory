# Mid-century cut-paper poster

Reference works: Saul Bass title sequences.

## References

- *Anatomy of a Murder (title sequence and poster)* (1959), Saul Bass, film title design. https://en.wikipedia.org/wiki/Anatomy_of_a_Murder
- *Vertigo (title sequence and poster)* (1958), Saul Bass, film title design. https://en.wikipedia.org/wiki/Vertigo_(film)
- *The Man with the Golden Arm (title sequence and poster)* (1955), Saul Bass, film title design. https://en.wikipedia.org/wiki/The_Man_with_the_Golden_Arm
- *Catch Me If You Can (title sequence)* (2002), Kuntzel + Deygas, film title design. https://en.wikipedia.org/wiki/Catch_Me_If_You_Can
- *Gerald McBoing-Boing* (1950), United Productions of America, animated short film. https://en.wikipedia.org/wiki/Gerald_McBoing-Boing

## Visual definition

- **Shape language and proportions:** Rough cut-paper shapes: figures and objects reduced to jagged, slightly crooked silhouettes with uneven straight cuts. Limbs are separate angular pieces. Strong diagonals and off-balance layouts.
- **Line and outline:** No outline. Shapes are solid.
- **Shading model:** None. Each shape is one flat colour.
- **Palette:** `#e8501e` `#111111` `#f4ead2` `#1f4e79` `#f2b632`. Three to five colours: one strong field colour (orange, red or blue), black, off-white and one accent.
- **Lighting:** None.
- **Texture and surface:** Flat ink with slight paper or print grain; edges are sharp but irregular as if cut with scissors.
- **Atmosphere and post-processing:** None.
- **Camera and framing:** Flat, frontal, graphic composition; orthographic.
- **UI and typography:** Panels are crooked cut-paper blocks of flat colour laid at slight angles, with no borders; icons are jagged one-colour silhouettes. Text is uneven hand-cut block capitals with letters that jump off the baseline, in black `#111111` or off-white `#f4ead2` on the field colour; numbers use the same cut letterforms, with yellow `#f2b632` for scores.
- **VFX and motion:** Effects are flat paper shapes: impacts are jagged starbursts, smoke and dust are torn-edge blobs, and transitions are bars that slide across the frame. Animation is limited, on twos or threes, with shapes that slide, pivot and snap between held poses.

## Fits

- **Genres:** `detective-mystery`, `stealth`, `puzzle`, `platformer`
- **Moods:** suspenseful, jazzy, bold
- **Settings:** 1950s city, crime thriller, heist caper, courtroom

## Unity recipe

### Assets

Flat cut-paper shapes on one frontal plane. Build them from scratch: an editor step generates silhouettes as polygons with jagged, slightly crooked straight cuts (perturb vertex positions, never use curves) and triangulates them to meshes; limbs are separate angular pieces that pivot. Store models can be rendered to masks and re-cut into polygons with a coarse simplification. Use three to five colours for the whole game: one field colour, black, off-white and one accent. Generate a subtle paper and print grain texture.

### Materials

`Universal Render Pipeline/Unlit` with a solid `_BaseColor` per shape is enough. Order shapes by small depth offsets or sorting order. An optional custom unlit shader multiplies a faint grain in screen space. No lights are read, there are no shadow passes and no drop shadows between pieces: this is a flat print, not physical paper.

### Lighting and atmosphere

None. No lights, shadows, fog, SSAO or probes. Orthographic camera facing the plane; the clear colour is the field colour (`#e8501e`, or red or blue). Compose with strong diagonals and off-balance layouts.

### Post-processing

Tonemapping None so the few colours are exact. One optional Full Screen Pass Renderer Feature after post-processing multiplies paper grain at low strength and adds very slight ink unevenness inside flat areas. No Bloom, blur or vignette. MSAA 8x keeps cut edges sharp.

### UI and effects

Panels are crooked cut-paper blocks of flat colour at slight angles with no borders: generate them with the same shape tool. Icons are jagged one-colour silhouettes. Lettering is uneven hand-cut block capitals: use a face such as Londrina Solid or Bowlby One and apply per-character baseline offset and rotation through TextMeshPro vertex edits; black or `#f4ead2` on the field colour, `#f2b632` for scores. Effects are flat shapes: jagged starburst meshes on impact, torn-edge blobs for smoke and dust, bars that slide across the frame as transitions. Animate on twos or threes: shapes slide, pivot and snap between held poses with no easing in between.

## Do / Do not

Do:

- Cut shapes with uneven straight edges.
- Use a few flat colours: one field colour, black, off-white and one accent.
- Break figures into separate angular pieces.
- Compose with strong diagonals.

Do not:

- Do not add paper thickness, folds and soft shadows; that reads as `050`.
- Do not use precise ruled geometry, photomontage and red-black type bars; that reads as `080`.
- Do not use depth layers with a graded colour ramp; that reads as `060`.
- Do not use clean circles, squares and triangles in primaries; that reads as `098`.

## Nearest styles

- `080` Constructivist agit poster: `080` uses ruler-straight bars, wedges and circles with photomontage and type bars on pale paper; this style uses crooked scissor-cut silhouettes on a strong colour field, with no photographs.
- `060` Layered flat-colour wilderness: `060` stacks many flat layers into the distance along a graded colour ramp; this style is one frontal plane with a few contrasting flat colours and no depth.
- `050` Papercraft: `050` shows real paper with thickness, folds and soft drop shadows; this style is a flat print with no shadows and no folds.

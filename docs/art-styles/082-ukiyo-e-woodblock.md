# Ukiyo-e woodblock

Reference works: Hokusai.

## References

- *The Great Wave off Kanagawa* (1831), Katsushika Hokusai, woodblock print. https://en.wikipedia.org/wiki/The_Great_Wave_off_Kanagawa
- *Fine Wind, Clear Morning* (1831), Katsushika Hokusai, woodblock print. https://en.wikipedia.org/wiki/Fine_Wind,_Clear_Morning
- *The Fifty-three Stations of the Tokaido* (1834), Utagawa Hiroshige, woodblock print series. https://en.wikipedia.org/wiki/The_Fifty-three_Stations_of_the_Tōkaidō
- *Sudden Shower over Shin-Ohashi Bridge and Atake* (1857), Utagawa Hiroshige, woodblock print. https://en.wikipedia.org/wiki/Sudden_Shower_over_Shin-Ōhashi_Bridge_and_Atake

## Visual definition

- **Shape language and proportions:** Stylised nature and travel scenes: waves with claw-like foam fingers, a conical mountain, pines with layered flat canopies, bridges, small figures in straw hats. Flattened space with high horizon or diagonal layout.
- **Line and outline:** Even, fine, dark keyline around every shape (carved line), slightly irregular, dark blue-black rather than pure black.
- **Shading model:** None on objects. Flat colour areas; skies and water have one smooth printed gradient (bokashi) from a dark band at the top edge to paper.
- **Palette:** `#1d3557` `#3d6a9e` `#f1e3c4` `#c9d6c2` `#c8553d` `#2b2b2b` `#e8c98a`. Prussian blue in several strengths, pale buff paper, soft green, with small accents of brick red and ochre.
- **Lighting:** None. Rain is drawn as thin dark parallel lines; mist as blank paper bands.
- **Texture and surface:** Paper fibre and faint wood-grain in large colour areas; slight colour misregistration against the keyline.
- **Atmosphere and post-processing:** Paper overlay; optional title cartouche block.
- **Camera and framing:** Flat, elevated views; large foreground element framing a small distant subject.
- **UI and typography:** Panels are buff paper rectangles with a fine blue-black keyline, shaped like title cartouches; icons are flat woodblock motifs, and red seal stamps mark alerts and confirmations. Text is brush-written calligraphic lettering in blue-black, set in vertical or cartouche blocks. Counters and damage numbers are brush-written numerals in blue-black, with brick red for critical values.
- **VFX and motion:** Splashes, smoke and dust are flat keylined shapes: claw-fingered foam, curled cloud bands, thin parallel rain lines. Hits show as short radiating line bursts or a spray of paper-coloured droplets. Motion uses held poses animated on twos or threes, with scenery layers that slide like printed sheets.

## Fits

- **Genres:** `action-adventure`, `exploration`, `hack-and-slash`, `stealth`, `strategy`, `soulslike`
- **Moods:** serene, contemplative, dramatic
- **Settings:** Edo-period Japan, coastal fishing village, mountain road, stormy sea

## Unity recipe

### Assets

Stylised nature and travel scenes: waves with claw-like foam fingers, a conical mountain, pines with layered flat canopies, bridges, small figures in straw hats. Build key shapes from scratch as flat or shallow meshes with designed outlines; stage them in flattened space with a high horizon. Store models need textures removed and flat colours assigned. Generate by script: a paper-fibre texture, a faint wood-grain tile for large colour areas, rain-line and cloud-band sprites, and a red seal stamp.

### Materials

Write `Style/Woodblock`, unlit. `UniversalForward` outputs a flat palette colour multiplied by the wood-grain tile at low strength (a few percent) in screen or object space. No shading on objects. Sky and water materials add one smooth vertical gradient (bokashi) from a dark Prussian blue band at the top edge to paper colour, computed from screen-space V or object height. Add `DepthOnly` and `DepthNormals` for the keyline; no `ShadowCaster`. Each colour is treated as a separate printing block: a small per-material screen-space offset (1 to 2 px) of the colour relative to the keyline imitates misregistration.

### Lighting and atmosphere

None. No lights, shadows off, flat ambient, no fog component. Mist is blank paper: flat horizontal bands in `#f1e3c4` placed between layers. No SSAO or probes.

### Post-processing

A Full Screen Pass Renderer Feature before post-processing draws the keyline from depth and normals: an even, fine line of about 1.5 px in blue-black `#1d3557` mixed with `#2b2b2b`, never pure black, with a very small noise displacement so it is slightly irregular like a carved line but constant in width. A second pass after post-processing multiplies the paper-fibre texture. Tonemapping None; no Bloom or grain. SMAA.

### UI and effects

Panels are buff paper rectangles with a fine blue-black keyline, shaped like title cartouches; text may run in vertical blocks. Font asset from a brush-written calligraphic face such as Yuji Syuku or Kaisei Tokumin, blue-black; brick red `#c8553d` for critical values. Red seal stamps mark alerts and confirmations with a quick stamp-down scale tween. Effects are flat keylined shapes: claw-fingered foam and curled cloud bands as meshes, thin parallel rain lines, short radiating line bursts or paper-coloured droplets on hits. Animate on twos or threes; scenery layers slide like printed sheets.

## Do / Do not

Do:

- Outline every shape with an even fine keyline.
- Use flat colour with one edge gradient in sky or water.
- Build the palette around Prussian blue and buff paper.
- Stylise foam, clouds and trees into repeated motifs.

Do not:

- Do not use variable brush strokes with wash and two tones; that reads as `022`.
- Do not use clean white ground and brighter colours without paper texture; that reads as `011`.
- Do not add whiplash ornament, gold halos and floral borders; that reads as `083`.
- Do not add smooth shading.

## Nearest styles

- `022` Sumi-e ink wash: this style puts an even fine keyline around every shape and fills it with flat colour; `022` has calligraphic brush strokes of changing width, ink washes in two tones and visible brush texture.
- `011` Clear-line adventure comic: this style prints on buff paper with visible fibre and wood grain, builds its colours around Prussian blue and has a gradient band in the sky; `011` has a clean white ground, brighter varied colours and no paper texture.
- `083` Art Nouveau ornamental poster: this style keeps colour areas plain and the palette small and blue-led; `083` surrounds tall figures with dense ornament, gold halos and floral borders in many muted pastels.

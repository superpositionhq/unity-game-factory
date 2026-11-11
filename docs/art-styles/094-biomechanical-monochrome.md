# Biomechanical monochrome

Reference works: H. R. Giger; Scorn.

## References

- *Necronom IV* (1976), H. R. Giger, airbrush painting. https://en.wikipedia.org/wiki/H._R._Giger
- *Alien* (1979), Ridley Scott (creature and derelict design by H. R. Giger), live-action film. https://en.wikipedia.org/wiki/Alien_(film)
- *Scorn* (2022), Ebb Software, video game. https://en.wikipedia.org/wiki/Scorn_(video_game)
- *Dark Seed* (1992), Cyberdreams, video game. https://en.wikipedia.org/wiki/Dark_Seed_(video_game)

## Visual definition

- **Shape language and proportions:** Fusion of anatomy and machinery: ribbed tubes, vertebra-like columns, pelvis-shaped arches, pistons that look like tendons, cable bundles like muscle fibre. Strong bilateral symmetry and repetition of segments.
- **Line and outline:** No outline.
- **Shading model:** Smooth, airbrushed gradients with a wet, semi-gloss sheen; deep occlusion in every recess.
- **Palette:** `#0c0c0d` `#2b2a28` `#5b5852` `#8c877c` `#b9b2a2` `#3f3a36`. Monochrome: black, cold grey, bone and gunmetal, with at most a faint sepia or blue-green cast.
- **Lighting:** Dim, soft, directionless light with a few rim highlights; forms emerge from darkness.
- **Texture and surface:** Very dense relief: closely spaced ribs, grooves, pores, rivet-like nodes and interwoven tubes covering all surfaces.
- **Atmosphere and post-processing:** Deep ambient occlusion, slight haze, fine grain, vignette.
- **Camera and framing:** Symmetric frontal views of corridors and portals, or close views of surface detail.
- **UI and typography:** Frames look grown, not built: ribbed bone-grey borders, vertebra dividers and socket-shaped slots, with icons as embossed relief glyphs. Type is a thin, tall, condensed engraved capital face in bone `#b9b2a2`. Counters are small and sparse in the same bone tone, with no colour; health can be an organ-like gauge.
- **VFX and motion:** Slow drips, viscous strands, pale mist and puffs of spore-like dust; hits land as dull wet impacts with dark grey spray, never bright flashes. Motion is slow and heavy: tubes pulse, pistons flex like tendons, and creatures unfold deliberately.

## Fits

- **Genres:** `survival-horror`, `exploration`, `puzzle`, `fps`, `soulslike`
- **Moods:** oppressive, grotesque, unsettling
- **Settings:** derelict alien ship, living machine temple, bone-walled labyrinth

## Unity recipe

### Assets

Forms that fuse anatomy and machinery: ribbed tubes, vertebra-like columns, pelvis-shaped arches, tendon-like pistons, cable bundles like muscle fibre. Few packs fit; generate much of it by script in Blender background mode: sweep ribbed profiles along curves, array vertebra segments, mirror everything for strict bilateral symmetry, and repeat segments in rows. Sculpt-like detail comes from generated height maps (closely spaced ribs, grooves, pores, nodes, interwoven tubes) baked to normal and occlusion maps at 2048 to 4096 px. Remove all colour from any store asset used.

### Materials

`Universal Render Pipeline/Lit`: albedo in the bone-to-gunmetal range (`#b9b2a2` down to `#2b2a28`), smoothness 0.55 to 0.7 for a wet semi-gloss sheen, low metallic, strong normal maps, and occlusion maps at full strength. A custom variant can deepen recesses by multiplying albedo and smoothness by a cavity mask, and add an airbrushed look by widening the highlight with a second, broader specular lobe; it calls `UniversalFragmentPBR` and keeps the Lit pass set. Pulsing tubes animate vertex offset along normals with a travelling sine. No emission and no colour.

### Lighting and atmosphere

Dim, soft and nearly directionless: low grey ambient from baked Adaptive Probe Volumes, a few weak large-radius point lights, and two or three narrow rim lights with no visible source to pick out ribs. Soft shadows. Deep occlusion is essential: the SSAO renderer feature at high intensity with a medium radius, plus baked occlusion maps. Reflection probes with a dim, low-contrast environment for the wet sheen. Thin grey exponential fog so forms emerge from darkness.

### Post-processing

Monochrome guard: Color Adjustments saturation -90, with at most a faint sepia or blue-green colour filter. ACES tonemapping, low exposure. Fine Film Grain, Vignette 0.45. No Bloom: nothing glows. Slight Depth Of Field optional. TAA.

### UI and effects

Frames look grown: ribbed bone-grey borders, vertebra dividers and socket-shaped slots, rendered from the 3D kit to sprites; icons are embossed relief glyphs. Font asset from a thin, tall, condensed capital face such as Big Shoulders Display Light or Six Caps, in `#b9b2a2`. Counters are small and sparse with no colour; health can be an organ-like gauge that pulses. Effects: slow drips and viscous strands (stretched mesh or `LineRenderer` with a sag), pale mist, spore-like dust puffs, and dull wet impacts with dark grey spray using lit particles. No bright flashes. Motion is slow and heavy.

## Do / Do not

Do:

- Merge bone and machine shapes.
- Cover every surface with ribs and tube relief.
- Keep the image monochrome.
- Use bilateral symmetry and repeated segments.

Do not:

- Do not use flat manufactured panels, labels and signal lights; that reads as `092`.
- Do not use gothic masonry and lantern colour; that reads as `031`.
- Do not use rubble and military hardware in daylight; that reads as `030`.
- Do not add colour accents.

## Nearest styles

- `092` Industrial used-future: this style has no colour, and every surface is covered in ribs and interwoven tubes; `092` has flat painted panels, stencil labels and amber, red and teal lights.
- `031` Gothic dark-fantasy realism: this style stays in one cold grey range and is built from bone-and-machine forms; `031` is stone masonry warmed by lantern and candle light.
- `030` Gritty desaturated war realism: this style is dim and enclosed, with smooth, wet organic relief; `030` is daylight rubble with chipped, scratched hard surfaces and military hardware.

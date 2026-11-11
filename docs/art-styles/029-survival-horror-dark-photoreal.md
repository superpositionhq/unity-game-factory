# Survival-horror dark photoreal

Reference works: Resident Evil.

## References

- *Resident Evil 2* (2019), Capcom, video game. https://en.wikipedia.org/wiki/Resident_Evil_2_(2019_video_game)
- *Resident Evil 7: Biohazard* (2017), Capcom, video game. https://en.wikipedia.org/wiki/Resident_Evil_7:_Biohazard
- *Resident Evil Village* (2021), Capcom, video game. https://en.wikipedia.org/wiki/Resident_Evil_Village
- *Resident Evil 4* (2023), Capcom, video game. https://en.wikipedia.org/wiki/Resident_Evil_4_(2023_video_game)
- *Silent Hill 2* (2024), Bloober Team, video game. https://en.wikipedia.org/wiki/Silent_Hill_2_(2024_video_game)

## Visual definition

- **Shape language and proportions:** True-to-life proportions and scale. Cluttered, decayed interiors: narrow corridors, heavy doors, stacked furniture, exposed pipes.
- **Line and outline:** No outline.
- **Shading model:** Physically based, smooth, with accurate specular on wet and glossy surfaces.
- **Palette:** `#0b0c0d` `#2a2622` `#5a4a3a` `#7d1f1a` `#8c8676` `#3c4a3e` `#c9b990`. Near-black shadow, dirty browns and greys, sickly green and deep blood red accents.
- **Lighting:** Very low key. A single flashlight cone or a few weak practical lamps; most of the frame is in darkness. Hard contact shadows.
- **Texture and surface:** High-frequency realism: stains, peeling paint, wood grain, mould, wet patches with sharp reflections.
- **Atmosphere and post-processing:** Film grain, strong ambient occlusion, volumetric dust in the light cone, slight chromatic fringe and vignette.
- **Camera and framing:** Over-the-shoulder or first-person, 35 to 50 mm equivalent, tight interior framing.
- **UI and typography:** Minimal, almost frameless UI: a small grid inventory with thin grey borders and photographic item icons, and health shown as a heartbeat trace that turns from green to red. Text is a plain narrow grotesque sans, with a typewriter face for found documents; the ammo counter is small white numerals. UI colours are pale khaki `#c9b990` and grey `#8c8676`, with blood red `#7d1f1a` for danger.
- **VFX and motion:** Realistic muzzle flashes that light the room for an instant, blood spray with wet decals, sparks, and dust drifting in the light beam. Motion is weighty and motion-captured: slow, deliberate player movement and lurching enemies.

## Fits

- **Genres:** `survival-horror`, `third-person-shooter`, `fps`, `stealth`, `puzzle`
- **Moods:** tense, oppressive, claustrophobic
- **Settings:** derelict police station, rotting farmhouse, fog-bound town, underground laboratory

## Unity recipe

### Assets

Photoreal interior packs: corridors, heavy doors, stacked furniture, pipes, clutter. Use the highest-quality scanned or PBR assets available and keep everything: full-resolution albedo, normal, mask and occlusion maps at 2048 to 4096 px with anisotropic filtering. Add decay instead of removing detail: stain, mould and peeling-paint decals, and wet patches painted into smoothness by script. True-to-life scale is mandatory; check door and ceiling heights.

### Materials

`Universal Render Pipeline/Lit` with all maps, and `Universal Render Pipeline/Complex Lit` for wet or lacquered surfaces. The editor step converts built-in materials, assigns mask maps, raises `_Smoothness` on wet areas and enables detail maps. Use the Decal renderer feature and `DecalProjector` components for stains and blood. No stylised shader anywhere.

### Lighting and atmosphere

Very low key. The main source is the player's flashlight: a realtime spot light with a cookie texture and hard-edged shadows at high resolution. A few weak practical lamps with shadows. No directional light indoors. Bake Adaptive Probe Volumes with low-intensity lighting so darkness is not pure flat black, and bake reflection probes with box projection in every room for sharp wet reflections. SSAO renderer feature on, high intensity, with direct lighting strength raised. Black exponential fog at low density. Volumetric dust in the cone is a particle system of small lit sprites parented to the light plus a faint additive cone mesh.

### Post-processing

ACES tonemapping with low post exposure. Film Grain medium, Vignette 0.4, slight Chromatic Aberration, mild Bloom on lamp bulbs. Depth Of Field is optional for aiming. Motion Blur low. TAA, HDR on, render scale 1. Keep the black point true: no lifted shadows.

### UI and effects

Nearly frameless: a small grid inventory with thin grey borders and rendered item icons (photograph items with an editor step camera). Health is a heartbeat trace drawn with a `LineRenderer` or a scrolling shader, green turning to `#7d1f1a`. Text from a plain narrow grotesque such as Archivo Narrow; found documents in a typewriter face such as Special Elite. Effects: muzzle flashes that spawn a one-frame point light, blood spray with decals that keep high smoothness, short sparks and dust in the beam.

## Do / Do not

Do:

- Light with one narrow source and leave the rest dark.
- Add wet low-roughness patches.
- Layer stains, peeling and mould.
- Apply film grain and vignette.

Do not:

- Do not raise ambient light; an evenly lit grey scene reads as `030`.
- Do not use gothic spires and blue moonlit fog; that reads as `031`.
- Do not use industrial sci-fi panels and teal monitors; that reads as `092`.
- Do not add neon signs and rain; that reads as `089`.

## Nearest styles

- `031` Gothic dark-fantasy realism: this style shows cluttered modern interiors under a flashlight, in many dirty browns, greens and reds; `031` shows ornate carved stone under cold moonlight and fog, in a narrow blue-grey range.
- `092` Industrial used-future: here surfaces rot, with mould, stains and peeling paint in near-total darkness; `092` has worn but orderly painted metal panels lit by amber beacons and teal monitors, with a little more light.
- `085` Baroque chiaroscuro: colour here is cold and dirty and detail is sharp and grimy; `085` has warm golden light on smooth glazed surfaces.

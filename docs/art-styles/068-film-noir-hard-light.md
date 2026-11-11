# Film noir hard light

Reference works: The Third Man.

## References

- *The Third Man* (1949), Carol Reed, live-action film. https://en.wikipedia.org/wiki/The_Third_Man
- *Double Indemnity* (1944), Billy Wilder, live-action film. https://en.wikipedia.org/wiki/Double_Indemnity
- *Touch of Evil* (1958), Orson Welles, live-action film. https://en.wikipedia.org/wiki/Touch_of_Evil
- *The Maltese Falcon* (1941), John Huston, live-action film. https://en.wikipedia.org/wiki/The_Maltese_Falcon_(1941_film)
- *L.A. Noire* (2011), Team Bondi, video game. https://en.wikipedia.org/wiki/L.A._Noire

## Visual definition

- **Shape language and proportions:** Real-world 1940s urban settings: wet cobbled streets, stairwells, offices with blinds, arches and tunnels. Realistic proportions.
- **Line and outline:** No outline.
- **Shading model:** Photographic and smooth, in black and white, with very high contrast: deep blacks, bright highlights, narrow midtone range.
- **Palette:** `#050505` `#2a2a2a` `#6e6e6e` `#b5b5b5` `#f0f0f0`. Greyscale only.
- **Lighting:** Hard, low-angle single sources: long shadows, light through window blinds in stripes, silhouettes in doorways, wet-street reflections, backlit haze.
- **Texture and surface:** Real materials in monochrome: wet cobbles, brick, plaster, wood grain, with film grain over all.
- **Atmosphere and post-processing:** Black-and-white conversion, strong contrast curve, film grain, vignette, slight halation around bright lights.
- **Camera and framing:** Tilted (Dutch) angles, low or high viewpoints, wide lens with deep focus.
- **UI and typography:** Thin white rule frames and plain black cards, like film title cards and case-file sheets; icons are simple white silhouettes. Titles are high-contrast serif capitals in the manner of 1940s film credits, with a typewriter face for notes, evidence and numerals, all in white `#f0f0f0` and grey `#b5b5b5` on black.
- **VFX and motion:** Muzzle flashes light the whole room white for one frame; cigarette smoke and steam drift through light shafts; rain splashes on wet streets. Motion is weighty and realistic, with slow deliberate movement and long shadows that swing across walls.

## Fits

- **Genres:** `detective-mystery`, `stealth`, `third-person-shooter`, `action-adventure`
- **Moods:** tense, cynical, brooding
- **Settings:** 1940s city at night, post-war Vienna, detective office, sewer tunnels

## Unity recipe

### Assets

Realistic 1940s urban packs: cobbled streets, stairwells, offices with window blinds, arches, tunnels, period cars and props. Keep full PBR maps; value and reflectance matter even though colour is discarded. Check albedos in greyscale and adjust them in an editor step so neighbouring materials differ in value. Wet the streets with a puddle mask raising smoothness. Build window-blind and grille geometry as real slats so they cast real stripes.

### Materials

`Universal Render Pipeline/Lit` with all maps. Wet cobbles and asphalt: smoothness 0.8 or more in puddles. Keep materials in colour; the conversion to black and white happens in post, which lets a Channel Mixer choose how colours map to grey (for example darker skies and lighter skin). Haze sheets for backlit streets are transparent unlit quads with depth fade. No stylised shaders and no outline.

### Lighting and atmosphere

Hard, low-angle single sources. Each scene has one dominant light: a spot or directional light with hard shadows (soft shadows off, 4096 shadow map) at a low angle for long shadows. Light through blinds comes from real slat geometry or a striped light cookie. Add no fill light; keep ambient very low and bake only a faint Adaptive Probe Volume so blacks keep slight shape. Reflection probes with box projection for wet streets. Thin fog in mid grey, and bright haze cards behind silhouettes in doorways. SSAO on.

### Post-processing

Black-and-white conversion with Color Adjustments saturation -100, preceded by Channel Mixer weights for the grey mix. A strong S-curve in Color Curves (master) for deep blacks, bright highlights and a narrow midtone range; ACES tonemapping. Film Grain at medium to high intensity, Vignette 0.4. Halation: Bloom with a threshold near 1, low intensity and high scatter, so only lamps and wet glints glow. No Chromatic Aberration. TAA, HDR on.

### UI and effects

Thin white rule frames and plain black cards like film title cards and case-file sheets; white silhouette icons. Titles from a high-contrast serif in capitals such as Playfair Display or Bodoni Moda; notes, evidence and numerals in a typewriter face such as Special Elite; `#f0f0f0` and `#b5b5b5` on black. Effects: muzzle flashes that fire a bright shadow-casting point light for one frame, lit cigarette smoke and steam drifting through light, rain streaks and splash rings on wet streets. Swing a practical lamp to move long shadows across walls.

## Do / Do not

Do:

- Convert to pure black and white.
- Light with one hard low-angle source.
- Cast blind-slat or railing shadow patterns.
- Tilt the camera and add film grain.

Do not:

- Do not threshold to two values with a colour spot; that reads as `069`.
- Do not paint jagged shadows on distorted flat sets; that reads as `071`.
- Do not use flat black silhouettes in grey fog; that reads as `070`.
- Do not leave any colour in the frame.

## Nearest styles

- `069` Selective-colour ink noir: `069` reduces everything to pure black and pure white shapes with bold keylines and one spot of colour; this style keeps the full grey range of a photograph, with film grain and no lines or colour.
- `070` Silhouette fog monochrome: `070` shows flat black silhouettes against pale, blurred grey fog layers; this style shows lit, detailed surfaces under hard light with deep black shadow.
- `085` Baroque chiaroscuro: `085` has the same single hard light out of darkness, but in warm painted colour with flesh tones and brown shadows; this style is black-and-white film with no colour.

# Oily concept-art realism

Reference works: Dishonored.

## References

- *Dishonored* (2012), Arkane Studios, video game. https://en.wikipedia.org/wiki/Dishonored
- *Dishonored 2* (2016), Arkane Studios, video game. https://en.wikipedia.org/wiki/Dishonored_2
- *Deathloop* (2021), Arkane Lyon, video game. https://en.wikipedia.org/wiki/Deathloop
- *BioShock Infinite* (2013), Irrational Games, video game. https://en.wikipedia.org/wiki/BioShock_Infinite

## Visual definition

- **Shape language and proportions:** Realistic scale with caricatured faces and hands (long angular features) and elongated, top-heavy architecture. Industrial Victorian shapes with heavy metal fixtures.
- **Line and outline:** No outline.
- **Shading model:** Smooth physically based shading, but with broad, simplified material response: wide soft highlights and little micro detail.
- **Palette:** `#2e3138` `#6b5a4a` `#8c8f8a` `#a23b2a` `#c9b68c` `#3f4f5c` `#d8d4c8`. Cold greys and slate blue with rusty brown, brass and a deep red accent. Overall low saturation.
- **Lighting:** Overcast daylight through tall windows, or lamps with soft pools; gentle contrast.
- **Texture and surface:** Textures look like oil studies: large soft brush areas, blurred wear, painted rather than photographed detail.
- **Atmosphere and post-processing:** Light fog, soft ambient occlusion, slight desaturation and a cool grade.
- **Camera and framing:** First-person, 28 to 35 mm equivalent, interiors with tall verticals.
- **UI and typography:** Painted icons in round engraved-brass or carved-bone frames, and parchment panels with ink sketches. Headings use a narrow Victorian serif and labels a plain small-caps serif; counters are plain off-white numerals. UI colours are off-white `#d8d4c8` and brass `#c9b68c` on slate `#2e3138`, with deep red `#a23b2a` for alerts.
- **VFX and motion:** Restrained effects: soft smoke, dark ash-like wisps for supernatural powers, brief dull sparks when steel meets steel. Motion is weighty and realistic, with slightly exaggerated, readable poses for first-person hands and enemies.

## Fits

- **Genres:** `stealth`, `fps`, `action-adventure`, `detective-mystery`, `exploration`
- **Moods:** oppressive, grim, conspiratorial
- **Settings:** plague-ridden port city, Victorian industrial districts, aristocratic mansions, whaling docks

## Unity recipe

### Assets

Realistic-scale Victorian and industrial packs: tall interiors, heavy metal fixtures, brass fittings. Elongate architecture by non-uniform vertical scale and top-heavy cornices; give characters longer, more angular faces and hands through blend shapes or bone scale. Keep PBR maps but paint them down: blur albedo and smoothness into large soft areas with a wide kernel, soften wear into blurred patches, and halve normal-map strength so micro detail disappears. 1024 to 2048 px, bilinear, trilinear mips.

### Materials

`Universal Render Pipeline/Lit` throughout. The editor step sets `_BumpScale` to about 0.5, keeps smoothness in a mid range (0.3 to 0.6) so highlights are wide and soft, and removes detail maps. Brass uses metallic 1 with tarnished albedo (`#c9b68c`) and stays a small accent. Skin can use Lit with low smoothness; no special subsurface work is needed. No custom lighting, no outline. Because everything is standard Lit, all passes (`UniversalForward`, `ShadowCaster`, `DepthOnly`, `DepthNormals`, `Meta`) are already present.

### Lighting and atmosphere

Overcast daylight through tall windows: a directional light at low intensity with soft shadows, plus baked area lights at windows. Bake lightmaps and Adaptive Probe Volumes; indirect light does most of the work and contrast stays gentle. Lamps are warm point lights with soft pools. Baked reflection probes with box projection per room. Light grey-blue exponential fog. SSAO on with a soft, wide radius.

### Post-processing

ACES tonemapping, Color Adjustments with saturation -20 and a slight cool filter, White Balance toward cool. Mild Vignette. An optional weak Kuwahara fullscreen pass (radius 2 px) can soften the remaining photographic detail. No Bloom beyond a trace on lamps, no Chromatic Aberration. TAA.

### UI and effects

Painted icons in round engraved-brass or carved-bone frames, and parchment panels with ink sketches. Headings from a narrow Victorian serif such as Playfair Display SC or IM Fell English SC; labels in a plain small-caps serif; plain off-white numerals. `#d8d4c8` and `#c9b68c` on `#2e3138`, `#a23b2a` for alerts. Effects are restrained: soft lit smoke with `Universal Render Pipeline/Particles/Lit`, dark ash-like wisps for powers (alpha-blended, not additive, with noise-driven motion), and brief dull sparks.

## Do / Do not

Do:

- Keep texture marks large and soft.
- Stretch architecture vertically.
- Hold saturation low with one red or brass accent.
- Use wide soft highlights.

Do not:

- Do not add sharp photographic micro detail; that reads as `029` or `032`.
- Do not quantise light into blocks; that reads as `021`.
- Do not add visible stroke-by-stroke brushwork; that reads as `024`.
- Do not cover everything in polished brass; that reads as `095`.

## Nearest styles

- `021` Brush-block martial painterly: this style has smooth gradients and grey rooms with little colour; `021` shows light in three to five visible steps and floods each room with one strong colour.
- `095` Brass steampunk: here cold grey and slate blue dominate and brass is a small accent; `095` fills the frame with warm brass, copper and furnace glow.
- `029` Survival-horror dark photoreal: scenes here are lit by soft daylight or lamp pools and textures look softly painted; `029` is mostly black, with sharp photographic detail.

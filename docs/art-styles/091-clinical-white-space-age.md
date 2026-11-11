# Clinical white space-age

Reference works: 2001: A Space Odyssey.

## References

- *2001: A Space Odyssey* (1968), Stanley Kubrick, live-action film. https://en.wikipedia.org/wiki/2001:_A_Space_Odyssey
- *THX 1138* (1971), George Lucas, live-action film. https://en.wikipedia.org/wiki/THX_1138
- *Moon* (2009), Duncan Jones, live-action film. https://en.wikipedia.org/wiki/Moon_(2009_film)
- *Portal 2* (2011), Valve, video game. https://en.wikipedia.org/wiki/Portal_2
- *Oblivion* (2013), Joseph Kosinski, live-action film. https://en.wikipedia.org/wiki/Oblivion_(2013_film)

## Visual definition

- **Shape language and proportions:** Clean engineered interiors: curved corridors, padded or moulded wall panels in a regular module, recessed light strips, round hatches, rotating ring sections. Spacecraft exteriors are white modular hulls with fine panel detail.
- **Line and outline:** No outline.
- **Shading model:** Smooth, soft, high-key. White surfaces are modelled by gentle gradients from large light panels.
- **Palette:** `#f4f4f1` `#dcdcd8` `#b9bcbf` `#1a1a1c` `#c4302b` `#8fa3b0`. White and pale grey almost everywhere, black for screens and space, with very small red or orange accents (a lamp, a seat, a suit).
- **Lighting:** Bright, even, built-in lighting: glowing floor or ceiling panels and wall strips. No visible hard shadows inside. Exteriors: one hard sun with black shadows.
- **Texture and surface:** Subtle panel seams, quilted padding, small labels and vents. Clean, not weathered.
- **Atmosphere and post-processing:** None, or very slight bloom from light panels. Crisp focus.
- **Camera and framing:** Symmetric one-point perspective down corridors, wide lens, level and centred.
- **UI and typography:** Thin-line panels in white and pale grey with rounded corners, like instrument readouts; icons are simple single-weight pictograms. Type is a clean geometric sans in widely spaced small capitals. Counters are plain tabular numerals in black or white, with red `#c4302b` only for warnings.
- **VFX and motion:** Sparse and clean: soft white light pulses, thin puffs of pale vapour, small red indicator flashes on hits. Motion is slow, smooth and deliberate, with gliding doors and steady weightless drift; no camera shake.

## Fits

- **Genres:** `puzzle`, `exploration`, `simulation`, `stealth`, `fps`
- **Moods:** sterile, calm, eerie, lonely
- **Settings:** space station, lunar base, test laboratory, orbital spacecraft

## Unity recipe

### Assets

Clean engineered interiors: curved corridors, padded or moulded wall panels on a regular module, recessed light strips, round hatches, ring sections; white modular hull exteriors. Sci-fi interior packs work after cleaning: recolour to white and pale grey, remove dirt, decals of wear and emissive clutter. Building the module by script (a panel, a strip, a hatch, a corridor arc) gives the most regular result. Keep subtle seams, quilted padding normals, small labels and vents at 2048 px.

### Materials

`Universal Render Pipeline/Lit`: `_BaseColor` `#f4f4f1` and `#dcdcd8`, smoothness 0.5 to 0.65 for moulded panels and 0.2 for padding, normal maps for seams and quilting at moderate strength. Light panels and strips use emissive Lit (`_EMISSION`, intensity 1.5 to 3) and are marked as static emitters for baking. Screens are black glossy Lit with emissive graphics. Accents (`#c4302b`) are small. No custom shader. Whites must keep detail, so albedo stays below 0.9.

### Lighting and atmosphere

Bright, even built-in light. Bake it: emissive panels and strips contribute to lightmaps and Adaptive Probe Volumes, supported by baked area lights behind large panels; raise indirect intensity so there are no visible hard shadows indoors. Few or no realtime shadow-casting lights inside. Baked reflection probes with box projection in each module. SSAO on at low intensity to mark seams. No fog. Exteriors are the opposite: one hard directional sun with hard shadows, black ambient and a black star sky.

### Post-processing

Neutral tonemapping with exposure set so whites stay just below clipping, which separates this from an overexposed outdoor look. Very slight Bloom from light panels. No Depth Of Field, grain, vignette or Chromatic Aberration: crisp focus. TAA or MSAA 4x, HDR on.

### UI and effects

Thin-line panels in white and pale grey with rounded corners, like instrument readouts; single-weight pictogram icons. Font asset from a clean geometric sans such as Jost or Montserrat Light in widely spaced small capitals; plain tabular numerals in black or white, red only for warnings. Effects are sparse: soft white light pulses, thin pale vapour puffs, small red indicator flashes on hits. Doors glide with eased motion, objects drift weightlessly, and the camera never shakes.

## Do / Do not

Do:

- Build from a regular module of white panels.
- Light with built-in glowing panels.
- Frame symmetrically in one-point perspective.
- Limit colour to one tiny red or orange accent.

Do not:

- Do not add outdoor sun, rooftops and several accent colours; that reads as `035`.
- Do not add grime, pipes and dim lighting; that reads as `092`.
- Do not facet red figures in an empty white room; that reads as `063`.
- Do not use raw concrete; that reads as `097`.

## Nearest styles

- `035` White city with primary accents: this style is a sealed interior of seamed white panels under soft built-in light, with whites that keep their detail; `035` is a sunlit outdoor city whose whites burn out, with several bright primary accents.
- `063` White-and-red faceted minimal: surfaces here are smoothly curved with soft gradients and pale grey panel detail; `063` breaks every form into flat facets and uses only white, red and a few neutrals.
- `092` Industrial used-future: this style is bright, white and clean everywhere; `092` is dark grey-green, grimy and dim, with exposed pipes and amber warning lights.

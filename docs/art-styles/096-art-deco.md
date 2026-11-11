# Art Deco streamline

Reference works: Chrysler Building; BioShock.

## References

- *Chrysler Building* (1930), William Van Alen, architecture. https://en.wikipedia.org/wiki/Chrysler_Building
- *BioShock* (2007), 2K Boston and 2K Australia, video game. https://en.wikipedia.org/wiki/BioShock
- *Autoportrait (Tamara in a Green Bugatti)* (1929), Tamara de Lempicka, oil painting. https://en.wikipedia.org/wiki/Autoportrait_(Tamara_in_a_Green_Bugatti)
- *The Great Gatsby* (2013), Baz Luhrmann, live-action film. https://en.wikipedia.org/wiki/The_Great_Gatsby_(2013_film)
- *Metropolis* (1927), Fritz Lang, silent film. https://en.wikipedia.org/wiki/Metropolis_(1927_film)

## Visual definition

- **Shape language and proportions:** Symmetric, vertical, stepped: ziggurat setbacks, sunbursts, fan and fountain motifs, chevrons, fluted pilasters, stacked arcs, streamlined rounded corners with speed lines. Stylised heroic statues with smooth simplified anatomy.
- **Line and outline:** No outline. Thin inlaid metal lines form geometric patterns.
- **Shading model:** Smooth, polished: glossy stone, lacquer and metal with long clean highlights; figures have tubular, airbrushed modelling.
- **Palette:** `#0f1a24` `#c9a24b` `#1f4e4a` `#e8dcc0` `#7a1f2b` `#2b2b2b` `#8fa3a8`. Black, deep teal and oxblood with gold or brass, cream marble and chrome.
- **Lighting:** Dramatic uplighting and cove lighting, strong vertical light shafts, reflections on polished floors.
- **Texture and surface:** Flat polished materials with inlaid geometric patterns: sunburst floors, chevron bands, repeating fan grilles, marble veining.
- **Atmosphere and post-processing:** Soft bloom on light fixtures; otherwise clean.
- **Camera and framing:** Symmetric frontal views looking up at towering verticals; wide lens.
- **UI and typography:** Symmetric gold-line frames with stepped corners on black or deep teal panels, divided by sunburst and chevron bands; icons are geometric single-line emblems. Type is a tall geometric display sans in capitals with contrasting thin and thick strokes. Counters are tall gold `#c9a24b` numerals on black.
- **VFX and motion:** Clean and theatrical: radiating light rays, gold glints, sweeping spotlight beams and brief sunburst flashes on hits. Motion is smooth and elegant, with poised held poses and streamlined sweeps; doors and panels slide and fan open symmetrically.

## Fits

- **Genres:** `detective-mystery`, `fps`, `action-adventure`, `stealth`, `racing`, `strategy`
- **Moods:** glamorous, grand, decadent, ominous
- **Settings:** 1920s skyscraper, underwater city, luxury ocean liner, grand hotel lobby

## Unity recipe

### Assets

Symmetric, vertical, stepped forms: ziggurat setbacks, sunbursts, fan and fountain motifs, chevrons, fluted pilasters, stacked arcs, streamlined rounded corners with speed lines, heroic statues with smooth simplified anatomy. Build architecture by script with strict mirror symmetry; deco packs fit if cleaned of dirt and wear. Generate inlay patterns by script as masks: sunburst floors, chevron bands, fan grilles, with a marble-veining texture for stone. Surfaces are flat and polished, so remove noisy normal maps.

### Materials

`Universal Render Pipeline/Lit`. Polished stone and lacquer: black `#0f1a24`, deep teal `#1f4e4a`, oxblood `#7a1f2b` or cream marble, smoothness 0.85 to 0.95. Inlay is done in one material with a mask: where the mask is set, metallic 1 and gold `#c9a24b` or chrome albedo; elsewhere stone. This gives thin inlaid metal lines without outlines. `Universal Render Pipeline/Complex Lit` with clear coat suits lacquer. Statues use smooth metal or stone with no detail maps so highlights run long and clean. Light fixtures use emissive Lit.

### Lighting and atmosphere

Dramatic architectural light: uplights (spot lights aimed up walls and pilasters), cove lighting from emissive strips with baked contribution, and strong vertical shafts from spot lights with additive cone meshes. Soft shadows. Reflections on polished floors are essential: box-projected reflection probes in each hall, at high resolution, or a planar reflection texture for main floors. Bake lightmaps and Adaptive Probe Volumes. Dark ambient. No fog, or a trace for shafts. SSAO on, low.

### Post-processing

Clean. Soft Bloom on light fixtures only (threshold above 1.1). ACES or Neutral tonemapping with good contrast. No grain, Chromatic Aberration or heavy vignette. TAA or MSAA 4x; HDR on.

### UI and effects

Symmetric gold-line frames with stepped corners on black or deep teal, divided by sunburst and chevron bands; icons are geometric single-line emblems. Font asset from a tall geometric display face with thin and thick strokes such as Poiret One or Limelight, in capitals; tall gold numerals on black. Effects are clean and theatrical: radiating ray meshes, gold glints (small additive four-point sprites), sweeping spotlight beams, a brief sunburst flash on hits. Doors and panels slide and fan open symmetrically with smooth eased tweens.

## Do / Do not

Do:

- Step and stack forms symmetrically.
- Use sunburst, chevron and fan motifs.
- Polish surfaces: brass, chrome, lacquer, marble.
- Uplight strong verticals.

Do not:

- Do not use organic whiplash curves and floral ornament; that reads as `083`.
- Do not cover machines in rivets, gears and tarnish; that reads as `095`.
- Do not use pastel boomerangs and starbursts with tail fins; that reads as `099`.
- Do not leave concrete raw; that reads as `097`.

## Nearest styles

- `095` Brass steampunk: surfaces here are smooth and polished, with a few flat inlaid patterns; `095` covers its machines in rivets, gears, tarnish and soot.
- `083` Art Nouveau ornamental poster: this style has no drawn outline, straight stepped geometry and polished rounded modelling; `083` has dark contour lines, flat colour fills and flowing floral curves.
- `099` Atomic-age Googie: this style is dark and formal in black, gold and teal; `099` is bright, sunny and playful in turquoise, coral and pink.

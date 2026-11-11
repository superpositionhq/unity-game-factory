# Selective-colour ink noir

Reference works: Sin City.

## References

- *Sin City* (2005), Robert Rodriguez and Frank Miller, live-action film. https://en.wikipedia.org/wiki/Sin_City_(film)
- *Sin City (comics)* (1991), Frank Miller (Dark Horse Comics), comic series. https://en.wikipedia.org/wiki/Sin_City
- *MadWorld* (2009), PlatinumGames, video game. https://en.wikipedia.org/wiki/MadWorld
- *Schindler's List* (1993), Steven Spielberg, live-action film. https://en.wikipedia.org/wiki/Schindler's_List

## Visual definition

- **Shape language and proportions:** Realistic figures and city settings reduced to stark graphic shapes: silhouettes with white rim shapes, rain as white streaks, blinds and bricks as white lines on black.
- **Line and outline:** Where a black form meets a black ground, a white keyline or rim separates them; where a white form meets white, a black line does. Lines are bold.
- **Shading model:** Two values only: pure black and pure white, with no greys. Shadow shapes are large and designed.
- **Palette:** `#000000` `#ffffff` `#c40000` `#f2d21b` `#1a1a1a`. Black and white plus one small area of a single saturated colour (red lips or dress, yellow skin, blue eyes).
- **Lighting:** Extreme hard side or back light; negative-space lighting where figures are white outlines on black.
- **Texture and surface:** None in tone. Rain streaks, brick lines and spatter are solid white or black marks.
- **Atmosphere and post-processing:** Hard threshold; selective colour mask; optional slight glow on white.
- **Camera and framing:** Dramatic low and high angles, strong perspective, silhouettes against light.
- **UI and typography:** Solid black panels with bold white borders, or the reverse, like comic caption boxes; icons are stark two-value silhouettes. Text is heavy hand-inked comic block capitals in white `#ffffff` on black; the one key colour, red `#c40000` or yellow `#f2d21b`, marks health, damage numbers and the selected item.
- **VFX and motion:** Blood, spatter and muzzle flashes are flat ink shapes in solid white or the one key colour; rain is white streaks, and a hit flips the frame to its negative for an instant. Animation is punchy, with strong held poses and fast smears between them.

## Fits

- **Genres:** `hack-and-slash`, `detective-mystery`, `third-person-shooter`, `fighting`, `stealth`, `action-adventure`
- **Moods:** brutal, lurid, hardboiled
- **Settings:** corrupt city at night, rain-soaked alleys, docks, seedy bar

## Unity recipe

### Assets

Realistic figures and city sets with strong silhouettes; detail is irrelevant, so mid-poly packs are fine. Remove all textures. Replace surface detail with marks that will survive a hard threshold: brick courses, blinds and rain as thin white line geometry or mask textures. Tag one element per scene (lips, a dress, eyes) with a selective-colour material. Design scenes for large shadow shapes, with lights placed by hand.

### Materials

Write `Style/InkNoir`. `UniversalForward` computes `NdotL * shadowAttenuation` from `GetMainLight(shadowCoord)` plus additional lights and outputs pure white or pure black by one `step`; a mask texture adds white marks on black (bricks, rain) and black marks on white. A rim term with a hard threshold draws a white rim on the unlit side so black figures separate from black grounds. Selective-colour materials output the key colour (`#c40000` or `#f2d21b`) flat and write a flag (alpha channel or a stencil bit) so post keeps it. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`.

### Lighting and atmosphere

Extreme hard side or back light: one directional or spot light, hard shadows, no fill, ambient black. Back-lit set-ups make figures white outlines on black through the rim term. No fog, GI, SSAO or probes. Background black.

### Post-processing

A Full Screen Pass Renderer Feature before post-processing with depth and normal requirements does three jobs. It thresholds luminance to exactly 0 or 1, so no grey remains. It adds bold keylines: at depth or normal edges, if both sides are black it draws a white line, and if both are white a black one. It passes flagged selective-colour pixels through untouched. Then optional Bloom at low intensity for a slight glow on white. Tonemapping None, no grain. MSAA on geometry is fine, but the threshold runs last so edges stay hard.

### UI and effects

Solid black panels with bold white borders or the reverse; stark two-value silhouette icons. Heavy inked block capitals from a comic face such as Bangers or Anton, white on black; the key colour marks health, damage numbers and the selected item. Effects are flat shapes: white or key-colour spatter flipbooks, white rain streaks from stretched particles, flat muzzle-flash shapes. A hit inverts the frame for one frame through a flag in the fullscreen material. Use strong held poses and fast smears.

## Do / Do not

Do:

- Threshold to pure black and white.
- Keep exactly one small selective colour.
- Use white keylines on black forms.
- Design large shadow shapes.

Do not:

- Do not keep grey gradients and film grain; that reads as `068`.
- Do not fill colour areas with muted flats; that reads as `010`.
- Do not use dot screentone for greys; that reads as `020`.
- Do not flood the frame with red; that reads as `008`.

## Nearest styles

- `010` Heavy-black gothic comic: `010` also has heavy black shadows, but fills the lit areas with muted flat colours; this style leaves them pure white and allows one small spot of strong colour.
- `020` Manga screentone monochrome: `020` is mostly white paper with fine ink lines and dot screentone for greys; this style is mostly black, with solid shapes and no dot tones.
- `068` Film noir hard light: `068` is photographic black and white with smooth grey gradients and film grain; this style has no greys, only solid black and white shapes with keylines.

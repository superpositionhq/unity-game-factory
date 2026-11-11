# Brush-textured 3D drama

Reference works: Arcane.

## References

- *Arcane* (2021), Fortiche and Riot Games, animated TV series. https://en.wikipedia.org/wiki/Arcane_(TV_series)
- *Puss in Boots: The Last Wish* (2022), DreamWorks Animation, animated film. https://en.wikipedia.org/wiki/Puss_in_Boots:_The_Last_Wish
- *Teenage Mutant Ninja Turtles: Mutant Mayhem* (2023), Nickelodeon Movies and Mikros Animation, animated film. https://en.wikipedia.org/wiki/Teenage_Mutant_Ninja_Turtles:_Mutant_Mayhem
- *Klaus* (2019), The SPA Studios, animated film. https://en.wikipedia.org/wiki/Klaus_(film)

## Visual definition

- **Shape language and proportions:** Realistic anatomy with slightly sharpened planes on faces and props. Architecture is dense and ornate with art-deco and industrial detail.
- **Line and outline:** Occasional dark painted accents at creases and under forms; no continuous outline.
- **Shading model:** Light is broken into four to six painted tone planes with visible stroke edges. Highlights are drawn as distinct brush marks.
- **Palette:** `#1f2a44` `#c2553f` `#e3a857` `#3e8e8c` `#7a3e65` `#d9cdb8` `#12141c`. Dark teal-blue shadow against warm orange and gold light; magenta and green accents.
- **Lighting:** Dramatic, low-key: strong warm practicals and cool fill, hard rim lights.
- **Texture and surface:** Every surface looks painted: directional brush strokes follow the form, with scumbled edges and painted speculars.
- **Atmosphere and post-processing:** Painted-looking smoke and glow drawn as 2D shapes; light bloom; subtle film grain.
- **Camera and framing:** Cinematic, shallow depth, 50 to 85 mm equivalent for characters, wide for cities.
- **UI and typography:** Art-deco frames with thin gold lines and angular corner ornaments, and painted icons with visible strokes. Titles use a tall condensed deco sans; damage numbers are rough hand-painted numerals. UI colours are gold `#e3a857` and cream `#d9cdb8` on near-black `#12141c`, with magenta or teal accents.
- **VFX and motion:** Smoke, sparks and explosions are hand-painted 2D shapes animated on twos over full-rate 3D motion; hits flash with magenta or teal painted bursts. Character motion is weighty and realistic, with sharp accents on impacts.

## Fits

- **Genres:** `action-adventure`, `third-person-shooter`, `fighting`, `stealth`, `detective-mystery`, `rpg`
- **Moods:** dramatic, gritty, tense
- **Settings:** steampunk undercity, art-deco upper city, industrial slums, back-alley laboratories

## Unity recipe

### Assets

Realistic-anatomy characters and dense, ornate architecture with art-deco and industrial detail. Keep geometry detailed, but repaint every texture: in an editor step run a directional smear along the UV-space tangent flow, then stamp brush strokes that follow the surface direction, with scumbled edges. Keep normal maps but replace their fine detail with a stroke-relief normal generated from the stroke texture. Generate a brush-stroke tile and painted highlight-mark sprites by script. 2048 px for hero assets.

### Materials

Write `Style/BrushDrama`. `UniversalForward` gathers `GetMainLight(shadowCoord)` and additional lights, then breaks the lighting into four to six tone planes: quantise the diffuse value after offsetting it with the stroke texture sampled along the UVs, so each plane boundary is a visible stroke edge. Colour the planes from a ramp that runs dark teal-blue (`#1f2a44`) to warm orange and gold. Specular is drawn as distinct marks: threshold the highlight and multiply by a stroke mask so it appears as separate dabs. Add a hard rim term. Passes `ShadowCaster`, `DepthOnly`, `DepthNormals`, `Meta`. No continuous outline; dark accents at creases come from the occlusion map multiplied in.

### Lighting and atmosphere

Low-key and dramatic: warm practical point and spot lights, a cool dim fill, hard rim lights behind characters. Use Forward+ for many lights, shadows on the main practicals. Bake Adaptive Probe Volumes for a cool base. Dark teal fog at low density. SSAO on, medium. Reflection probes at reduced intensity.

### Post-processing

A Full Screen Pass Renderer Feature before post-processing applies a Kuwahara filter with a 5 to 6 px radius, masked by depth so near characters keep detail. Then light Bloom, subtle Film Grain, Depth Of Field in Bokeh mode for character shots, ACES tonemapping and Split Toning toward teal shadows and orange highlights. TAA.

### UI and effects

Art-deco frames with thin gold lines and angular corner ornaments; icons painted with visible strokes. Titles from a tall condensed deco face such as Poiret One or Limelight; damage numbers from a rough painted face such as Rock Salt. `#e3a857` and `#d9cdb8` on `#12141c`. Smoke, sparks and explosions are hand-painted flipbooks played at 12 frames per second over full-rate 3D motion; hits flash a magenta or teal painted burst.

## Do / Do not

Do:

- Orient strokes along the form.
- Break tone boundaries along stroke edges.
- Paint highlights as discrete marks.
- Light with warm practicals against cool fill.

Do not:

- Do not blur strokes away into broad blocks; that reads as `021`.
- Do not light evenly with saturated zone colours; that reads as `023`.
- Do not cover the frame with thick swirling strokes and outlines; that reads as `076`.
- Do not add halftone dots; that reads as `009`.

## Nearest styles

- `021` Brush-block martial painterly: this style shows directional brush strokes and painted highlight marks on every surface; `021` smooths them into broad soft tone blocks with no small marks.
- `028` Expressionist oil isometric: strokes here follow the form in an ordered way under dramatic warm and cool light; `028` has thicker paint, short strokes running in many directions, unmixed colours and flat overcast light.
- `026` Oily concept-art realism: here light breaks into stepped planes with stroke edges and strong colour; `026` has smooth gradients and a greyer look.

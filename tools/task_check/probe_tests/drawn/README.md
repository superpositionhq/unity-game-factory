# drawn family tests (`drawn` and `Hooks.GlowRender`)

Setup used: a Unity 6000.3.28f1 URP 17.3 project (Forward renderer, HDR on, render scale 1, linear colour space). The
probe player is a non-development Mono build on D3D12.

- `Editor/BuildDrawnScenes.cs` goes in `Assets/Editor/Drawn/`. Run it with
  `probe.py exec <proj> DrawnTest.BuildDrawnScenes.Run --graphics` (graphics so the lightmap bakes). It builds
  `Assets/Scenes/DrawnTest.unity` and `Assets/Scenes/DrawnBaked.unity` (it bakes a lightmap and 50 light probes with
  the CPU lightmapper in about 30 s).
- `Scripts/*.cs` go in `Assets/Scripts/Drawn/`, one MonoBehaviour per file. Several in one file have no MonoScript,
  and the player then crashes loading the scene with "level1 is corrupted".
- `Assets/GlowNoEmission.shader` goes in `Assets/Drawn/`. It is a hand-written URP shader with a `_Glow` property and
  no `_EmissionColor`.
- `specs/`: the plays. `show.py <play dir>` prints the samples. `pngdiff.py a.png b.png` compares two screenshots.

DrawnTest scene, under things a drawn render must not show: a strong orange sun with shadows, a blue point light,
exp2 fog, a realtime reflection probe, and a global volume (bloom 3, post exposure 0.7, saturation -60, red colour
filter).

## Plays and what they gave

### `drawn_main.json` (16 s, every 0.5 s)

All values below come from the final run.

| query | proves | value |
|---|---|---|
| qRed (URP Lit, plain colour sRGB 0.8, 0.2, 0.1) | base colour = the material's linear colour; motion 0 | base (0.6038, 0.0331, 0.0100) = linear exactly; motion 0 every sample; null at the first |
| qChecker (Lit, red/blue checker base map) | base from a texture | (0.4998, 0, 0.5002) |
| qTint (shared white Lit + MaterialPropertyBlock 0.1, 0.6, 0.3) | base from a property block | (0.0100, 0.3185, 0.0732) = linear exactly |
| qGlowLitBase (Lit, albedo 0.2, 0.4, 0.6, emission 2, 1, 0.5) | emission is not base colour | (0.0331, 0.1329, 0.3186) |
| qLitWhite (Lit white) / qShProbe (custom shader, tint white: shows the ambient itself) | the probe's white ambient is 1/0.96, so URP Lit reads its albedo | 1.0000 / 1.0416 |
| qTwoToneTop / qTwoToneLow (red slab over blue slab; band y >= 1, or y_relative -0.3..0) | depth and the height band; the near views aren't flipped | (1, 0, 0) / (0, 0, 1) |
| qRedBand (y 1.2..3 of a cube spanning y 0.5..1.5) | the height band cuts pixels | 1116 of 3056 pixels, same base |
| qSpin (a cube turning 90 deg/s) | motion from a turning mesh | motion 0.973-0.98 |
| qPan (a quad whose base map pans) | motion from a material animation | motion 0.83-0.93; base_change <= 0.0003 |
| qSparks (transparent URP Particles/Unlit) | translucent particles: drawn, motion, no base | drawn 1, 1356 then about 5000 pixels, motion 0.77-0.99, base null |
| qLate (a cube activated at 5 s) | an object that appears mid-play | drawn 0 up to 5.0 s; at 5.5 s drawn 1, motion 1, base_change 0 (its first base) |
| qEmpty (empty point inside a 64 m sphere) | an enclosing renderer is left out | primitives 0, drawn 0 (with a 50 m sphere, under 20x the place size: primitives 1, drawn 0, since the backfaces draw nothing) |
| qRedMotionOnly (fields drawn, motion only) | no base pass when no base_ field is asked | base null; 4.7-5.0 ms against 7-11 ms with base |
| qBeam (a cube growing from 0.5 to 9 m along +x between 2 and 12 s); line (70,1,0)->(80,1,0), r 0.3 | reach, length | t 0.5: reach 0.486, length 0.508; t 5: 3.017 / 3.051 (true 3.05); t 10: 7.236 / 7.288 (true 7.3); from t 12: 8.923 / 8.983 (true 9) |
| qLine (a LineRenderer growing the same way) | the same for a LineRenderer | same values as qBeam |

`play.log` lines `GLOWTEST ...` come from GlowReport, which calls `Hooks.GlowRender` by reflection every 15 frames:

| renderer | brightest | glow | check |
|---|---|---|---|
| GlowLit (Lit, emission 2, 1, 0.5, 1 m cube) | 1.1765 | 1.7601 | luminance of the emission = 1.1765; x 1.5 (a quarter of 6 m2) = 1.765 |
| GlowLitBig (same, 2 m) | 1.1765 | 7.0404 | x4 for twice the size |
| GlowLitBright (emission 4, 2, 1) | 2.353 | 3.5202 | x2 for twice the brightness |
| GlowLitTilted (scale 2 x 0.5 x 1, turned 30/45/10) | 1.1765 | 2.0571 | 1.1765 x 7/4 = 2.059 |
| UnlitBright (URP Unlit 3, 3, 3 sRGB) | 11.21 | 16.77 | 3^2.2 linear |
| CustomGlow / CustomGlowBig (no _EmissionColor) | 1.5 | 2.244 / 8.976 | as rendered; x4 for size |
| CustomGlowSphere | 1.5 | 1.009 | a sphere fills part of its box |
| GlowSparks (live particles) | 0.26 | 0.46-0.48 | |
| DarkCube, LitWhiteCube, RedCube (lit by a strong sun) | 0 | 0 | no light reaches a glow render |

- Budget: 12 named renders, then 70 distinct BudgetCubes in the same frame gave 52 ok and 18 refused (64 in total).
- Cache: the same renderer again in the same frame takes 0.005-0.01 ms.
- LeakWatch compares, every frame in Update, RenderSettings, every Light, every reflection probe, every renderer's
  layer, forceRenderingOff, lightmapIndex, light probe and reflection probe usage, and the URP asset's HDR and
  render scale with the previous frame. It found 0 leak lines over 480 frames in every play.

### `drawn_screen_only.json` vs `drawn_main.json`: the game's frame is unchanged

The particle systems use a fixed seed, so plays repeat frame for frame.

- Two screen-only plays: the luminance series are identical (0 of 34 samples differ).
- With the realtime reflection probe (refresh every frame) in the scene, a play with queries differs from a
  screen-only play by about 1e-5 relative. It differs just as much when every render is skipped (a temporary
  `-drawnKeep all` switch), so the cause is that probe, not the renders.
- With that probe switched off (`-- -drawnScene noprobe`, handled by LeakWatch), the screen-only play and the play
  with all 18 drawn queries plus about 400 GlowRender calls have identical series (0 of 34 samples differ).

### `drawn_baked.json`: lightmaps and light probes

A white (0.9) Lit cube that is lightmapped (index 0) and a Lit sphere lit by light probes, both under a red baked
light, read base 0.7874 = linear(0.9) and glow 0.

### Renderer variants

The main and baked plays were run again with the project's URP renderer switched (the asset then put back):

- Forward+, with the URP asset's HDR off and render scale 0.75: every value is identical, glow above 1 included.
- Deferred: every value is identical, except that the hand-written test shader reads 0. It has only a
  `UniversalForward` pass, so URP's deferred path doesn't draw it, in the game or in the probe.

## Cost (this machine, RTX 5060 laptop, D3D12)

- drawn near a point with base (12 renders: 4 views x white + depth + dark): 6-11 ms a sample, 7-8 ms on average.
- drawn near a point, drawn and motion only (8 renders): about 5 ms.
- drawn along a line (4 renders, 128 x 128): about 4 ms.
- drawn with nothing in the place: 0.2 ms.
- GlowRender: 2.5-4 ms a call (first call 7-8 ms); 0.005 ms from the cache.

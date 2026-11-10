# The light family: `light`, `grading`, `audio` and the probe's audio tap

What the package's `LightQuery`, `GradingQuery`, `AudioQuery`, `LightKit` and the core's `AudioTap` promise
(`docs/task-probes.md` 2.7, 2.8, 2.16), checked against what Unity itself draws and mixes: a white diffuse card in the
frame where the light is measured, the checker's own `tools/task_check/colour.py` against a graded frame, the mix the
listener hears against the volumes the measure reads. `tests.py` holds every number; this file says what each scene
holds and what each play proves. The scenes and their assets are made by `Editor/LightScenes.cs` (namespace
`ProbeTests.Lighting`: a namespace `ProbeTests.Light` would hide `UnityEngine.Light` from every other family's code).

## Scenes

- **LightLab**: closed rooms (10 x 4 x 10 m) with a point lamp, a second one switched on at 3.5 s (a warm colour at
  2700 K), a spot lamp, and lamps behind a wall across the room: without shadows, with shadows, with shadows at half
  strength; an open field under a sun (4000 K, shadows on) with a roof on nothing; a row of lamps whose shadows are
  on, each with something between it and its point (a housing around the bulb, a crate the point is inside, a trigger,
  the Ignore Raycast layer, a 2D collider, the player's capsule, a plain slab). A white Simple Lit card (no specular)
  lies at each measured point; the camera (no post-processing) looks down at one card a second (`LightTour`), and
  `LightEvents` changes the lighting between visits: at 7.5 s point and spot shadows switched on in the URP asset (for
  the measure only: the project's asset has none, so the build strips their shader variants and the frame can't show
  them) and the sun's shadow strength at 0.5 for 2 s; the ambient through gradient, skybox (before and after
  `DynamicGI.UpdateEnvironment`) and flat at intensity 2; then additional lights off, then the main light off.
  `LightCull` logs what the engine itself holds: each Light's `VisibleLight.finalColor` and `bakingOutput`.
- **BakeLab**: three lamps over static floors, baked with light probes around them and the ambient black: one
  Baked, one Mixed (baked indirect), one set to Baked after the bake (never baked). A moving white card under each.
- **SkyLab**: saved with skybox ambient and never baked; a white sun, a card; the camera renders post-processing with
  no volume in the scene (an untouched stack: the project's default profile). The environment is made at 2 s.
- **GradeLab**: a camera carrying an unlit card of linear 0.18 grey that fills its view, under a global grade (white
  balance, contrast, saturation, colour filter, lift/gamma/gain, tonemapping None, bloom); the player walks into a
  local volume (a 10 m box, blend distance 10 m, post exposure 1, bloom, vignette) from 6 s. Also a volume of weight
  0.5, a disabled one, one on a layer the camera's volume mask leaves out, and two directional lights of one
  intensity.
- **AudioLab** / **AudioLab2**: sine-tone sources of every kind around the listener (3D logarithmic, 2D, muted,
  through a -20 dB mixer group, a custom curve, a streaming clip, one that ignores the listener's pause, one just
  under the audible floor of 0.001), and
  `LightAudioDirector`'s events: a clip that ends, a source started and one paused, `PlayOneShot` on a source without
  a clip and on one with its own, `PlayClipAtPoint`, `AudioListener.pause`, `timeScale` 0, a second listener on, the
  second alone, no listener, a scene load to AudioLab2. Each listener carries a `LightEar` ahead of the probe's tap
  (the mix as it reaches the tap) and gets a `LightEarAfter` behind it (`LightEarKeeper`: what the machine would
  play).
- **AudioRolloff**: one tone moved through logarithmic, linear and custom rolloff, a half-2D blend, 2D, the -20 dB
  group, and `AudioListener.volume` at 0.5, 2 s a step.
- **Stray**: a listener and a quiet tone, played by the probe and started without one (`LightStrayBoot`,
  `-lightstray`).

## Plays

- **lamps**: every term of `light` against URP's own maths, written out in `tests.py` (`RealtimeLights.hlsl`
  `DistanceAttenuation` and `AngleAttenuation` with the constants `UniversalRenderPipelineCore` prepares; the colour
  as the engine's own `finalColor`, its colour temperature applied); and against the frame: at each card the frame's
  luminance is each Light's contribution times the cosine of its angle to the card, plus the ambient, within the
  HDR target's and the 8-bit screenshot's rounding. A wall stops a Light only where URP draws its shadows: a lamp
  without them, or with them where the URP asset draws none, lights through it, in the frame as in the measure; the
  sun's shadow stops it, and at strength 0.5 lets half through. With point light shadows switched on in the asset a
  housing around the bulb, a trigger, the Ignore Raycast layer, a 2D collider and the player never stop a lamp; a
  crate the point is inside and a slab do. The ambient is the ambient probe straight up in every
  mode, walls or not (URP doesn't shade it at run time): flat ambient ignores its intensity, gradient ambient mixes
  sky, equator and ground. Also: a point at an object, a point that doesn't resolve, a query without a point, and
  grading's neutral constants for a camera without post-processing and its sun.
- **lamps_builtin**: the render pipeline switched off before the first frame: `light` still computes URP's terms,
  `grading` is neutral without `post:` values, and each query says so once in `query_errors`.
- **baked**: what URP draws at run time for a baked lamp (nothing: the engine leaves it out, its light is in the
  lightmaps and the light probes), a Mixed one (real time, its bounce baked) and one set to Baked but never baked
  (real time); the measure reads the light probes there as a moving card is lit, and the frame agrees.
- **sky**: a never-baked skybox scene's ambient probe is what the measure reads, before and after it is made; an
  untouched volume stack gives exactly grey 0.18 and cast 0 through `colour.py`.
- **grade**: the grade's constants are URP's (`ColorBalanceToLMSCoeffs`, `PrepareLiftGammaGain`); every kind of `post:`
  value (a float, an int, a bool, an enum, an unset texture, a colour's and a vector's channel by either spelling,
  a default, a volume of weight 0.5, a disabled volume and one off the camera's mask) and every kind of `post:` error;
  the local volume's blend as the camera walks in (VolumeManager's `1 - d^2 / blend^2`); through `colour.py` the
  frame's centre pixel and its luminance. `colour.py` applies the post exposure as URP's uber pass does (2^EV before
  the grading lookup): inside the local volume the frame's centre pixel is `colour.py`'s grade with post exposure 1.
- **grade_script**: the camera's volumes updated by script only: URP renders with the stack it made once, and the
  measure reads that stack (`source` `camera_stack`): inside the local volume the frame still shows the global grade.
- **audio**, **audio_again**: every source kind at its volume at the listener through the director's events (a mixer
  group selects by its own name, not its parent's; 0.001 is the audible floor); the mix's level of a single source;
  which listener Unity mixes through with two on; the tap on every enabled listener, hidden from the game's
  `FindObjectsByType` (its `GetComponents` sees it), and nothing leaving it. `audio_again` plays the same and must read the
  same in every field but the mix's (which runs in real time).
- **rolloff**: each rolloff step's volume against the formula, and the mix's RMS against the volume (a 0.5 sine at
  volume 1 is 0.25 in the mix, panned -3 dB into each channel; the mixer group's -20 dB and `AudioListener.volume`
  only in the mix).
- **stray**: in a probe play the tap silences the tone; the player started without `-taskProbe`, with a tap the game
  added itself, lets it through (the test's own `LightMute`, last in the chain, keeps the machine quiet).

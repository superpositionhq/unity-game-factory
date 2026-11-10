# light family tests: `light`, `grading`, `audio`

Unity 6000.3.28f1, URP 17.3.0, LDR colour grading, linear colour space. Query files:
`TaskProbe/Runtime/Queries/LightKit.cs` (shared), `LightQuery.cs`, `GradingQuery.cs`, `AudioQuery.cs`.

## Reproduce

1. Copy `editor/LightTestScenes.cs` to `<proj>/Assets/Editor/` and `scripts/*.cs` to `<proj>/Assets/Scripts/LightTests/`.
2. `python probe.py exec <proj> LightTests.EditorSteps.LightTestScenes.Run`. This writes the sine WAVs, the
   `TestMix.mixer` with a -20 dB `SFX` group, the volume profiles, the grey material and five scenes under
   `Assets/Scenes/LightTests/`.
3. `python probe.py build <proj> Assets/Scenes/LightTests/{LightLab,GradeLab,AudioLab,AudioLab2,AudioRolloff}.unity`
4. `python probe.py play <proj> specs/<light|grade|audio|rolloff>.json`, then run the matching checker in `specs/`
   (`expect_light.py probe.json play.log`, `check_grade.py <play dir> <tools/task_check>`, `check_audio.py`,
   `check_rolloff.py`).

`results/<play>/` holds each play's probe.json, probe.log and the test scripts' lines from the player log.

## LightLab (`specs/light.json`, 14 s): `light`

There are three closed rooms (10 x 4 x 10 m, 0.2 m walls) and an open field. The test computes the expected values
by hand in `expect_light.py`, which writes out URP's formulas separately from the C# code.

| query | set-up | expected (hand) | probe |
|---|---|---|---|
| qA | point light I=2, range 10, 2 m above the point | 0.498401 | 0.498401 |
| qA after 3 s | second point light switched on: (1, .5, .25) at 2700 K, I=1.5, 4.69 m away | +0.014532 | +0.014532 |
| qB1 | spot straight down, 60/30 degrees, I=3, 2 m: inside the inner cone | 0.747602 | 0.747602 |
| qB2 | 0.8 m off-axis (21.8 degrees, in the falloff) | 0.251582 | 0.251584 |
| qB3 | 3 m off-axis (56 degrees, outside the cone) | 0 | 0 |
| qC1 | point light behind a wall | 0 | 0 |
| qC2 | same light, same side | 0.248459 | 0.248459 |
| qD1 | open field, sun I=1.2 at 4000 K | engine `finalColor` luminance 0.83179 | directional 0.831791 |
| qD2 | under a 6 x 6 m roof slab | 0 (sun and sky blocked) | directional 0, sky 0 |
| qObj | `{"object": {"name": "PointA"}, "offset": [0, -2, 0]}` | same as qA | 0.498401, point [0, 1, 0] |
| qNone | an object that doesn't exist | null | null |

The LightDirector culls the scene in `beginCameraRendering` and logs each visible light's `VisibleLight.finalColor`.
In every case that value equals what the probe computes: `color.linear * intensity * Mathf.CorrelatedColorTemperatureToRGB(T)`.
For example, the sun is (1.2, 0.76183, 0.44006) and SwitchedA is (1.5, 0.12807, 0.00735).

Ambient (qD1 `sky`, open sky so all 9 rays are clear) compared with the ambient probe's upward value:

- Flat (0.2, 0.3, 0.4): probe up = the colour, linear. Luminance 0.06901. Probe: 0.06901.
- Trilight with sky (0.5, 0.4, 0.3): probe up = (0.1208, 0.0767, 0.0444), luminance 0.08377. This is not the sky colour
  (0.214, 0.133, 0.073), because the gradient's SH mixes in the equator and ground colours. Probe: 0.08377.
- Skybox, intensity 1.5: probe up luminance 0.51935. Probe: 0.51935.
- Flat with `ambientIntensity` 2 (from 12 s): the engine's probe doesn't change (0.06901), so the intensity doesn't
  apply to Flat. Probe: 0.06901.

## GradeLab (`specs/grade.json`, 22 s): `grading`, `screen`, the `light` exposure

A global Volume sets white balance (30, -20), contrast 25, saturation -30, colour filter (1, .9, .8), lift/gamma/gain
(1, 1, .9, .02) / (.95, 1, 1.05, 0) / (1.05, 1, .95, .1), tonemapping None and bloom 0.5. An unlit quad of linear 0.18
grey, parented to the camera, fills the view. The player stands still until 6 s, then walks +z at 2 m/s into a local
box volume (10 m box, blend distance 10 m, priority 1) that overrides only post exposure 1, bloom 2 and vignette 0.4.

Frame against `colour.py`, with the probe's grading value at 1.5 s and a white key light (`check_grade.py`):

| step | rgb (linear) |
|---|---|
| start | 0.18, 0.18, 0.18 |
| white balance | 0.18260, 0.18644, 0.12681 |
| contrast | 0.17331, 0.17788, 0.10958 |
| colour filter | 0.17331, 0.14007, 0.06617 |
| gain, lift | 0.22641, 0.17456, 0.05652 |
| gamma | 0.20043, 0.17827, 0.07388 |
| saturation | 0.19293, 0.17742, 0.10435, which is sRGB 121.5, 116.9, 90.9 |
| **frame** (shot_00 centre) | sRGB **121, 117, 91**, which is linear 0.1912, 0.1779, 0.1046 |

`colour()` gives `grey` = 0.175445. The frame's `screen` luminance is 0.17543. They agree to 8-bit quantisation, and
no step differs.

One mismatch: `colour.py` doesn't apply `post_exposure`. URP's UberPost multiplies the colour by 2^postExposure
before the LUT. Inside the local volume (post exposure 1), the frame reads 0.38889. `colour()` still says 0.17545.
With 0.36 (0.18 x 2^1) fed in, it says 0.39275, which is 1 % off the frame. The remaining 1 % is the vignette and
bloom, which are active there.

The local volume's blend over the walk follows VolumeManager's weight `1 - d^2/blend^2` with a one-frame lag of the
test clock. For example, at 16 s the expected weight is 0.75: postExposure read 0.7433, bloom 1.6149 (0.5 + 1.5w) and
vignette 0.2973. At 20 s inside the box, all three read 1, 2 and 0.4. The `light` exposure at the camera goes
1 -> 1.4148 -> 1.9843 -> 2.

Other `post:` fields:

| field | value |
|---|---|
| `post:Vignette.color.r` | 0.2 |
| `post:Tonemapping.mode` | 0 (None) |
| `post:Bloom.highQualityFiltering` | 0 |
| `post:MotionBlur.intensity` | 0 (its default; no volume sets it) |

These come back null with a `query_errors` line:

| field | error |
|---|---|
| `post:Vignette.color` | "name a part" |
| `post:Nope.x` | "no volume component Nope" |
| `post:Bloom.nope` | "Bloom has no parameter nope" |

## AudioLab (`specs/audio.json`, 21 s, `"sound": true`): `audio`

The listener is on the player's camera. All clips are 0.5-amplitude sine WAVs. Expected volumes and what the probe
read:

| source | set-up | expected | probe |
|---|---|---|---|
| Loop3D | 3D log, min 1, max 50, volume 0.8, 5 m | 0.16 | 0.16 |
| Music2D | 2D, volume 0.5 | 0.5 | 0.5 |
| Muted | muted | 0, counted but not audible | 0, counted but not audible |
| Mixed | 2D, volume 1, on the -20 dB SFX group | 1 (mixer left out) | 1 |
| Custom | linear-tangent curve (0,1)-(.5,.25)-(1,0), max 20, 8 m | 0.4 | 0.4 |

The sum is 2.06, from 5 sources with 4 audible; the probe read 2.06.

The select queries read:

| query | select | result |
|---|---|---|
| qTone | `sound: "Tone*"` | 0.16 |
| qSfx | `sound_class: "SFX"` | 1, loudest Mixed550 |
| qOwner | `owner: {name: Loop3D}` | 0.16 |

Events over the play:

| time | event | count / volume / level | what Unity reports |
|---|---|---|---|
| 0-1 s | start | level null | the tap isn't attached until the core's 16-frame Follow |
| 1 s | steady | level 0.168, peak 0.35 | |
| 4 s | Late starts (linear, min 1, max 20, blend 0.5, 10.5 m) | qLate 0.75 (expected 0.75); total 2.81, level 0.242 | |
| 6 s | `PlayOneShot(Shot880)` on a source with no clip | count 7, volume +1, `loudest` "" | `isPlaying` true, `clip` null. `sound: "Shot*"` can't match, but `level` rises to 0.35 |
| 7.5 s | `PlayClipAtPoint(Point990, 3 m)` | qPoint 0.3333 = 1/3 | Unity makes "One shot audio": a playing source with the clip, 3D log, min 1, max 500 |
| 9-10.5 s | `AudioListener.pause = true` | count 0, level 0 | `isPlaying` false on every source |
| 11-12.5 s | `Time.timeScale = 0` | unchanged: 2.81, level 0.242 | sources keep playing |
| 13-14.5 s | every source stopped | level 0 | |
| 14.5 s | listener moved to a second camera | listener "SecondCamera", 0.25, level 0.063 (0.252 per unit volume) | works only after the core change below |
| 17 s | scene load (AudioLab2) | 0.3, level 0.0756 (0.252 per unit volume) | tap attached within a second |

`TapLog` and AudioDirector log which listener carries the tap.

## AudioRolloff (`specs/rolloff.json`, 31 s, `"sound": true`): the rolloff against the real mix

One tone is placed straight ahead of the listener and moved every 2 s. The table compares the probe's volume with the
measured level, normalised to the first step:

| step | probe volume | level ratio |
|---|---|---|
| log 1 / 2 / 4 / 8 m | 1 / .5 / .25 / .125 | 1 / .5 / .25 / .125 |
| **log 80 m (max 50)** | .0125 | .0125 |
| linear 0.5 / 5.75 / 10.5 / 15.25 m | 1 / .75 / .5 / .25 | the same |
| custom 0 / 8 / 14 m | .9992 / .4 / .15 | .9993 / .4 / .15 |
| log 4 m, blend 0.5 | .625 | .625 |
| 2D | 1 | .9999 |
| 2D on the -20 dB group | 1 (mixer left out) | .1005 (the mixer, in `level`) |

The first build clamped the logarithmic distance at max distance, as Unity's documentation says. That gave 0.02 at
80 m, but Unity measured 0.0125 (1/80). Logarithmic rolloff keeps falling past max distance, and the query now
follows the measurement.

## Core change (needed): `Runtime/Core/AudioTap.cs`, `Follow()`

See `AudioTap.core-change.diff`. `FindFirstObjectByType<AudioListener>()` also returns a *disabled* listener
component. When the game disabled the first camera's listener and enabled a second, the tap stayed on the disabled
one. `level` then went null (no buffers), and the game's audio was **audible on the machine** until the next scene
load. The fix picks the first enabled listener on an active object.

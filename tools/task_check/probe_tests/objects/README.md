# Probe tests: objects and components (and the camera, spawns, pieces and ground kinds on the same scene)

What the `objects` and `components` kinds read: every field and select key, `lit` and `glow` from every kind of
source, the state a query keeps from sample to sample, and that nothing they read changes the game. `ObjectsQuery.cs`,
`ComponentsQuery.cs`, `ObjectRead.cs` and `Glow.cs` are tested here; the camera, spawns, pieces and ground kinds are
checked on the same scene (their own tests are `probe_tests/world`). The checks and the values they expect are in
`tests.py`.

## Scenes (made by `Editor/ObjScenes.cs` under `Assets/ProbeTests/objects/Made/`)

- **ObjLab**: one of every thing the six kinds read. The player (a CharacterController driven by the keyboard, a turned
  visor on it), a camera that follows it and a wall that comes between them, a crate that falls, a kinematic lift, a
  fan whose blade spins and carries a trail, an object deactivated and one whose renderer is disabled at 3 s, a
  parent whose child (each with a renderer) is activated at 3 s, nine
  lamps tagged `ObjLamp` on layer `ObjProps` (a Light, URP Lit with emission, URP Unlit, emission through a map, emission
  set at 4 s through a MaterialPropertyBlock, a spot Light enabled at 4 s, a Light set to intensity 0 at 4 s, a custom
  shader without the standard interface, a plain cube), a lamp the game lights at 3.99 s (in the frame an input
  selects it by `has.lit`, before the game's scripts), two bulbs one above the other, a live and a stopped particle
  system, an enabled and a disabled decal, three enemies with a script of every kind of member (it implements an
  interface), a LODGroup, a spawner of clones and pooled objects, a skinned arm whose Animator bends it at 3 s, a
  terrain with trees, and `ObjWatch`, which counts the frames in which a sample left the active render texture, a
  renderer's materials or its property block changed.
- **ObjMore**: what ObjLab lacks. A Light with a colour temperature; a renderer with two materials and a property block
  on the second alone; the built-in Standard shader; two cubes with one emission map, one showing its white half and
  one its black half (as meshes show their parts of an atlas); a material whose `_EMISSION` keyword the game switches
  on; a renderer forced off; two emissions either side of the floor of 0.01; a colour and a vector set on a property
  block at 2 s, each on a plain emissive cube and on one with a white emission map; `ObjFacts`,
  what the engine does with a colour on its way to a shader (whether URP Lit and Standard mark `_EmissionColor`
  `[HDR]`, what a property block gives back); a Shader Graph whose path isn't `Shader Graphs/` (copied from the Shader
  Graph package's unlit template); sprites and a line; two skinned meshes whose root bone is scaled 2 (one emissive,
  one with the custom shader); a VisualEffect when the project has the VFX Graph package; 2D physics (a box that
  falls, a kinematic body, a body spun at 90 deg/s); a NavMeshAgent on a NavMesh of its own; a humanoid stick figure
  whose head bone is named `Skull`; a ragdoll (three bodies on the bones of one skinned mesh) kicked apart at 1 s; an
  object moved by its transform alone and a spinner; an object with nothing but a BoxCollider; the scene's
  AudioListener on an object of its own (where the probe puts its AudioTap).
- **ObjBudget**: 80 cubes drawn with the custom shader, then 4 with an emission map: more renders than one sample may
  make.
- **ObjStress**: 3000 boxes with colliders (every third emissive, every thirtieth spinning, every hundredth with a
  Light, every tenth tagged `ObjEnemy`).

## Plays

- `lab` (ObjLab, the `drive` keys): every objects and components field on the player, the physics bodies, the fan,
  the things that go at 3 s, the lamps before and after their switches at 4 s, the enemies' members, the arm's
  Animator and bones; the selects by component, interface, tag, layer, name, `near` with a height band, `has.lit`,
  `owner`, `mesh`, `visible`, `effect`; row order and `class`; the errors of an unknown field and type; that a sample
  reads a lamp as the game left it in that frame, though an input read it before the game's scripts.
- `world` (ObjLab, the `drive` keys): the camera, spawns, pieces and ground kinds on the same scene.
- `more` (ObjMore): lit and glow of every kind of source (and how each was read); that what a colour's properties
  read is what its render shows: an `[HDR]` colour (URP Lit's emission) as the material holds it, a plain one made
  linear; that a property block's value is rendered (Unity makes a colour set on a block linear and hands a vector on
  as it is, and the block can't say which it holds: `ObjFacts`); sprites and lines as parts, the skinned
  meshes' boxes in their root bone's frame, 2D bodies, the NavMeshAgent's speed, human bones by name only, the
  ragdoll's spread, and that the queries changed nothing.
- `wait` (ObjMore, a 2 s wait at 1 s): speed and spin over the sample after a wait divide by the game time that passed
  (the play's clock holds while the game runs on). Played once: how many frames a wait runs depends on real time, and
  with them x and the float rounding in speed and spin (2.0000041 m/s at 1.5 s, 2.0000267 from 2 s).
- `budget` (ObjBudget): at most 64 renders a sample, in hierarchy order, the same at every sample; past them a mesh
  with an emission map reads its bound and a custom shader has no value.
- `stress_*` (ObjStress): one query alone, sampled every 0.1 s; its cost a sample is its play's real time less the
  empty play's (`stress_none`), over its 101 samples, under a generous bound (`tests.py`).

## What a sample cost (measured)

On the shared 16 GB machine of the run that wrote this, with other Unity jobs running (so take them as upper values),
a sample of one query over the 3004 objects of ObjStress cost (probe.log stamps real time in tenths of a second, so
each is good to about 1 ms):

| query | ms a sample |
|---|---|
| objects, every object, `x y z speed extent_x hidden collision spin` | 24 |
| objects, every object, `lit glow` (1000 emissive boxes read by their properties) | 15 |
| objects, every object, `changed bounds_change spread` | 25 |
| objects, `has.lit` (1022 matches) | 5 |
| objects, tag `ObjEnemy` (300 rows), 2 fields | 2 |
| components, every MeshRenderer (3001), `x spin lit glow changed visible` | 20 |
| pieces, ground (a 32 x 32 grid), spawns, camera | under 1 each |

A render for `lit` or `glow` (a texture, a Shader Graph, a custom shader, a sprite, a line, a live effect) costs a few
ms more each, at most 64 a sample (the drawn family measures it).

## Not tested here, and why

- A gamma-space project: the colour space is a project setting, and these tests build one project (the conversion is
  `QualitySettings.activeColorSpace`'s, in `Find.Linear`).
- A VisualEffect needs the VFX Graph package, which the template doesn't have: the scene has one, and `more` checks
  it (a live effect, active, lit as rendered), only when the project's manifest lists `com.unity.visualeffectgraph`. In
  a project without it, as the shared test project, the VisualEffect path of `effect`, `lit` and `glow` is untested.
- A Shader Graph needs the Shader Graph package (URP brings it); without it the scene has no `LampGraph` and `more`
  skips its two checks.
- A Light's cookie is not read by `lit` or `glow` (documented), so nothing tests it.

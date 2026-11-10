# Probe tests: objects, components, camera, spawns, pieces, ground

## Setup (a Unity 6000.3 URP project with the Input System)

- `Scripts/*.cs` -> `Assets/Scripts/`; `Scripts/ProbeTestGlow.shader` -> `Assets/TestMats/`.
- `Editor/BuildObjectsScenes.cs` -> `Assets/Editor/ObjectsFamily/`. Run
  `python probe.py exec <proj> ObjectsTest.BuildObjectsScenes.Run`. It adds the tags `Lamp`, `Enemy` and layer 8
  `Props`, writes materials, a texture, a skinned mesh, an Animator controller and a tree prefab to
  `Assets/TestMats/`, and saves `Assets/Scenes/ObjTest.unity` and `Assets/Scenes/ObjStress.unity`.
- `python probe.py build <proj> Assets/Scenes/ObjTest.unity Assets/Scenes/ObjStress.unity`.
- `python gen.py` writes the play specs (the copies are in `plays/`). `python show.py <probe.json> [times] [ids]`
  prints a result compactly.

## ObjTest.unity

- **Hero**: the player. Tagged Player, a CharacterController moved by `TestPlayer`, which reads `Keyboard.current`
  W/A/S/D on world axes at 4 m/s, Space to jump. It faces the way it moves. Its child `Visor` is turned 30 degrees.
- **Main Camera**: `FollowCam` follows the hero from (0, 3, -6) and looks the other way from 10 to 11 s. **Wall**
  (`Occluder`) stands between the camera and the hero from 6 to 8 s.
- **Crate**: a Rigidbody that falls from y 8. **Lift**: a kinematic Rigidbody that `KinematicMover` moves at 2 m/s.
- **Fan/Blade**: spins at 180 deg/s and carries **Tracer** (a TrailRenderer).
- **Vanisher**: deactivated at 3 s. **Ghost**: its renderer is disabled at 3 s.
- Lamps, a row at z 10, tagged `Lamp` on layer `Props`:
  - `LampLight`: a point light, intensity 5.
  - `LampEmissive`: URP Lit with emission (4, 3, 2).
  - `LampUnlit`: URP Unlit (1, 0.9, 0.5).
  - `LampMapped`: emission (2, 2, 2) times a half-white emission map that isn't readable.
  - `LampSwitch`: emission black, then (4, 4, 4) through a MaterialPropertyBlock at 4 s.
  - `LampLater`: a spot light, disabled until 4 s.
  - `LampOff`: a light set to intensity 0 at 4 s.
  - `LampCustom`: a custom HLSL shader with no standard interface.
  - `Dark`: plain Lit.
- **Bulb** x2 at (8, 0.5, 8) and (8, 3, 8), for `near` with a height band.
- **Sparks**: a live ParticleSystem. **SparksOff**: a stopped one. **Decal** and **DecalOff**: URP DecalProjectors,
  the second disabled.
- **Enemy_0..2**: tagged Enemy, with `Health`, which has a float, a private int, an enum, a string, a list, a colour
  and a Transform reference.
- **Rock**: a LODGroup with a cube as LOD0 and a sphere as LOD1.
- **Arm**: a code-built SkinnedMeshRenderer on bones Lower/Upper. Its Animator goes Idle -> Bend (Upper slides 0.6 m)
  when `Open` is set at 3 s; `AnimDriver` sets Speed (float), Count (int) and Open (bool).
- **Gun** (`Spawner`): from 1 to 9 s, a `Bullet(Clone)` every 0.5 s (destroyed after 1 s), and a pool of three
  `PoolBullet` objects reused by SetActive (life 0.7 s).
- **Floor**: a 100 x 100 m slab, top at y 0. **Ramp** at (30, 30), turned -20 degrees. **Roof** at (-20, 4, -20).
  **Hills**: a 40 x 40 m Terrain at x 60-100, z -20-20, 6 m high, with 6 trees of a cube + sphere prefab (780
  triangles each).

`FakeGlowRender.cs` (test only, with `-fakeglow`) installs a stand-in for `TaskProbe.Hooks.GlowRender` through
reflection. It reads every renderer as rendered, with brightest 2 and glow 7, so the as-rendered branch runs without
the drawn family.

## play_main.json (16 s, the `drive` keys to 15 s): `results/result_main.json`, `results/result_main_fakeglow.json`

What each query read (t in s):

- `o_hero`:
  - x/z follow the keys: z 4 at 2 s; blocked by LampSwitch at z 8.92 (speed 0, from the CharacterController's
    velocity).
  - At 7 s x 4, yaw 90; at 16 s yaw -90.
  - y 2.27 at 9.5 s (the jump).
  - speed 4.0 while moving; facing_vs_velocity 0 while walking and 34.6 while falling at 10 s, with no value when
    stopped.
  - spin 180 in the sample after each 90-degree turn (6.5, 8.5, 13.5 s), else 0, with no value on the first sample.
  - rel_yaw:Visor 30 throughout. world_yaw:Visor 30, then 120 at 7 s, then -60 at 16 s.
  - forward:Visor.x/z (0.5, 0.866). extent_x 0.5 / 0.618 as it turns.
  - collision 1, hidden 0, active 1, simulating 0, scale 1, count 1.
- `o_phys` (`component: Rigidbody`):
  - Crate: y 7.99 -> 6.72 -> 3.0 -> 0.5. Speed 0.39 / 4.9 / 9.81 (body velocity), then 0. Simulating 1, changed 1,
    bounds_change 7.49. Spin 2.1 for the bounce at 1.5 s.
  - Lift: speed 2.0 (displacement: kinematic), simulating 0.
- `o_fan`: spin 180, changed 1, bounds_change cycling 0.156-1.36, spread 0 (one renderer), extent_x 1.5 <-> 0.15.
- `o_gone` (inactive: true): Vanisher active 1 -> 0 at 3 s, hidden 0 -> 1, changed 0 -> 1, collision 1 -> 0, and
  extent_x has no value once it is gone.
- `o_ghost`: hidden 0 -> 1, changed 0 -> 1, active stays 1, collision stays 1.
- `o_lamps` (tag) and `o_props` (layer): 9 rows each.
  - lit/glow before 4 s / after 4 s:
    - LampLight 1/5.
    - LampEmissive 1/19.3: (4,3,2) linear has luminance 12.86, times a quarter surface of 1.5.
    - LampUnlit 1/1.19.
    - LampMapped 1/3.45: (2,2,2) linear is 4.59, times the map's mean 0.5, times 1.5. This proves the blit mean.
    - LampSwitch 0/0 -> 1/31.7 (MPB).
    - LampLater 0 -> 1/1.11.
    - LampOff 1/2 -> 0/0.
    - Dark 0/0.
    - LampCustom: no lit/glow, `glow_read: unread` (no render hook). With `-fakeglow`: 1/7, `glow_read: render`.
- `o_haslit` (`has: {lit: true}`): 8 objects before 4 s (Sun, LampLight, LampOff, the 3 emissive cubes and unlit
  sphere, 2 Bulbs) and 9 after (LampOff out; LampSwitch and LampLater in). With `-fakeglow`, LampCustom and Sparks
  are in too.
- `o_bulb_hi` (`near` [8,0,8] r 5, `y_min` 2): 1 row, y 3, scale 0.4. `o_bulb_lo` (`y_relative`, `y_max` -1 from
  [8,3,8]): 1 row, y 0.5.
- `o_enemy`:
  - prop:Health.current 90 -> 0 by drain.
  - prop:Health.armour 7 (private).
  - prop:Health.state 0 -> 1 -> 2 (enum).
  - prop:Health.label "grunt" (string).
  - prop:Health.items 3, and items[1] 5.
  - prop:Health.tint.g 0.5.
  - prop:Health.target 1 / 0 (reference).
  - prop:activeSelf 1, prop:localScale.y 1.
  - prop:Health.nothing has no value.
- `o_arm`:
  - anim:Speed = t, anim:Count = whole seconds, anim:Open 0 -> 1 at 3 s; anim:Missing has no value.
  - clip "Idle" -> "Bend".
  - bone:SkinnedMeshRenderer.Upper.x 12 -> 12.6; bone:Animator.Upper.y 1 (a descendant by name: not humanoid).
  - pose_change 0 -> 0.6, changed 0 -> 1, bounds_change 0 -> 0.6, extent_x 0.2 -> 0.5.
- `o_sun`: world_pitch:Light 50, world_yaw:Sun -30, forward:Light.y -0.766, lit 1, glow 1.5.
- `o_rock`: extent_x 0.5, spread 0, hidden 0.
- `o_bad`: the field `nonsense` gives one query_error ("objects: no field nonsense") and is left out of the rows.
- `c_lights`:
  - intensity, on, lit, glow, active per Light: LampOff on 1 -> 0 (intensity 0); LampLater on 0 -> 1 (enabled).
  - visible 1 for all: a non-renderer reads its object's activity.
- `c_lamp_r` (`component: Renderer`, owner tag Lamp): 6 renderer rows, with the same lit/glow as their objects.
- `c_effects` (`effect: true`): Sparks (ParticleSystem), Decal (enabled DecalProjector) and Tracer (TrailRenderer).
  It leaves out SparksOff (stopped) and DecalOff (disabled).
- `c_decal`: DecalOff active 0, Decal 1. `c_decal_live`: Decal only.
- `c_ps_live`: Sparks only. `c_ps`: SparksOff active 0, lit 0 / glow 0 (not live: dark without rendering). Sparks
  active 1, `prop:particleCount` 20, `glow_read: unread` (`-fakeglow`: lit 1, glow 7, sources "effect").
- `c_blade` (name Blade): spin 180, x 5, z -5, speed 0, changed 1, bounds_change, extent_x 1.5 <-> 0.15, visible 1.
- `c_spheres` (`mesh: Sphere`): 7 -> 4 as the bullets stop.
- `c_visible` (`visible: true`, near Vanisher/Ghost): 2 -> 0 after 3 s.
- `c_health`: prop:current per component, active 1, speed 0.
- `c_smr`: pose_change 0 -> 0.6, changed 0 -> 1, lit 0.
- `c_rb`: Crate simulating 1, Lift 0, speed 2 for Lift. extent_y has no value (a Rigidbody is neither a renderer
  nor a collider).
- `c_col` (BoxCollider of Crate): extent_y 0.5.
- `c_trail`: active 1, x moving with the blade tip.
- `c_bad`: unknown type -> no rows plus a query_error.
- `cam`: pitch 18.4, fov 60, distance 6.71, height 3. occluded 1 in 6-8 s (the Wall), else 0. player_on_screen 0 in
  10-11 s (the camera looks away), else 1.
- `sp` (`spawns`, Projectile): spawned/destroyed 4/1 at 2 s, 16/13 at 5 s, 34/34 from 10 s (17 clones + 17 pool
  reuses). `sp_bad`: value null plus a query_error.
- `p_all` (no select): count 33 at 2 s, then 29 once the bullets are gone. visible drops by 1 after Ghost's renderer
  is disabled. Vanisher is no piece once inactive.
- `p_terrain`: 6 trees, 1 component, 1 object, 4680 triangles. `p_trees_near` (near (70,0,-10) r 8): 2 trees.
- `p_sphere` (`mesh: Sphere`): 6 -> 3. Rock_LOD1 is not counted (LOD 1).
- `p_rock` (owner Rock): 1 piece, 12 triangles (LOD0 only).
- `p_near` (near the player r 6): 7 / 9 / 2 as the hero walks.
- `g_origin` height 0. `g_roof` 4.1, and `g_roof_floor` (`select` name Floor) 0, traced through the roof.
  `g_ramp` 0.532. `g_none` (500, 500): height null, hit 0.
- `g_hills` (box over the Terrain, grid 8): min 0.583, max 5.55, mean 3.0, range 4.97, hits 64/64. `g_hills_sel`
  (TerrainCollider only): the same.

## Stress: ObjStress.unity (3000 boxes, every 3rd emissive, 100 spinning, 30 lights, 300 tagged Enemy)

Each `plays/stress_<kind>.json` runs one query alone for 10 s, sampled every 0.1 s (101 samples). The cost per
sample is (play clock wall time - the empty play's) / 101. The empty play's wall time is 0.6 s for 300 frames.

| query | per sample |
|---|---|
| objects, select {} (3004 rows), 8 fields (x y z speed extent_x hidden collision spin) | ~56 ms |
| objects, select {}, lit + glow | ~50 ms |
| objects, select {}, changed + bounds_change + spread | ~60 ms |
| objects, select {}, count only | ~43 ms |
| objects, has.lit (1000+ matches) | ~18 ms |
| objects, tag Enemy (300 rows), 2 fields | ~6 ms |
| components, MeshRenderer (3000 rows), x spin lit glow changed visible | ~60 ms |
| pieces (no select) | ~2 ms |
| ground, box grid 32 (1024 rays) | ~1 ms |
| spawns (counted every frame) | ~0 ms |
| camera | ~0 ms |

Timed inside the sample, about 35 ms of each 3000-object `objects` sample is the core `Find.Objects` sort into
hierarchy order. The rows themselves take 10-20 ms. At the default `every` 0.5 s, a 20 s play with one full-scene
query costs about 2 s more.

## sib.json

This play shows that in a built player every scene root reports `Transform.GetSiblingIndex() == 0`
(`prop:Health.sibling`). The core's hierarchy order is therefore not stable between plays. The index in
`scene.GetRootGameObjects()` (`prop:Health.rootIndex`) is stable across plays of one build: 17, 27 and 32 in all
three runs.

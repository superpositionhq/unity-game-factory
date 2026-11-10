# world: camera, spawns, pieces, ground

The query kinds that read the scene as a whole rather than a selection's rows: `camera` (the player's camera against
the player), `spawns` (objects appearing and going), `pieces` (placed mesh pieces) and `ground` (the lie of the land).
`Editor/WldScenes.cs` builds two scenes.

## WorldLab.unity

- **Camera.** The player (`WldHero`, tagged Player) has its pivot at its feet and a capsule collider 1 m up; the main
  camera stands 6 m behind it and 1.5 m up, looking along +z, with a collider of its own. Between them: a trigger, a
  pane on the Ignore Raycast layer, and a wall that `WldDirector` shows only from 1.25 to 1.75 s of game time; at
  3.25 s the camera turns round. `WldOrtho` makes the camera orthographic when the player is started with `-wldOrtho`.
- **Spawns.** `WldDirector` runs a timeline: a shot (`WldShot`, from an inactive template) every 0.5 s from 0.25 s,
  six of them, each destroying itself 0.5 s later; a pool of three objects switched on and off with `SetActive` at 0.4,
  1.4 and 2.4 s; a shot made and destroyed in one frame at 2.1 s; a `WldShot` added to an existing object at 2.6 s; an
  object whose `WldShot` is disabled, there from the start and destroyed at 3.1 s; `WorldSide.unity` (two shots) loaded
  additively at 3.6 s and unloaded at 4.1 s. `WldShot` derives from `WldShotBase` and implements `IWldShot`.
- **Pieces**, under `PieceArea`: three cubes; a mesh of two triangle submeshes; a mesh of lines and one of points; one
  of a triangle submesh and a line submesh; a mesh saved without read access; a SkinnedMeshRenderer, and one whose mesh
  has only lines; a LODGroup of three LODs (LOD 1 shares LOD 0's renderer); a disabled renderer; an inactive one; one
  marked Static; a mesh drawn every frame with `Graphics.RenderMesh` (`WldPainter`); and a terrain with eight trees of
  two prototypes, one a prefab with a LODGroup, the other two cubes.
- **Ground**, x 100 to 140, z 0 to 40: a floor at y 0 with a hole at x 118 to 122, a hill (y 2), a roof (y 5), a
  trigger, a pane on the Ignore Raycast layer, a 2D collider at y 3, and a collider below y -2000 under the hole. The
  player stands on a floor of its own at the origin.

## The plays

- `camera`: pitch, yaw and fov; distance and height to the player's pivot; `occluded` only while the wall stands (the
  trigger, the Ignore Raycast pane, the camera's and the player's own colliders never occlude); `player_on_screen`
  until the camera turns round. The checker computes distance and height from the camera and track rows: the same
  numbers.
- `camera_none`: a play whose player select matches nothing: the camera's own fields, the player's null.
- `camera_ortho`: an orthographic camera reads fov 0; a field the kind doesn't have is said once in `query_errors`.
- `spawns`: the counts at every sample, the same for the component's type, its base type and its interface; the
  objects there when the clock starts are not spawned; the shot made and destroyed in one frame is never seen; an
  unknown type or no type has no value, and says so.
- `pieces`: the counts and triangles of every form above; each select key; an owner that matches nothing, or whose
  point doesn't resolve, reads zeros; an unknown type, or the query's own point not resolving, has no value.
- `ground`: heights at points (the roof read through with a select of the floor), the hole's no hit, a box on the
  default lattice, its corners in either order, grids of 1 (read as 2), 2, 7.6 (8) and 40 (32), a select over a box,
  and the definitions that give no value with their errors.

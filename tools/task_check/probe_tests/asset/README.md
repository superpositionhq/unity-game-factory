# asset: the editor pass and the checker's build

Two parts of the package that run in the editor, not in a play: the editor pass that reads `asset` measures from the
project as saved (`TaskProbe.EditorTools.AssetPass`), and the player build the checker makes of a scratch copy
(`TaskProbe.EditorTools.Build`).

## What the builder makes

`AssetScenes.Build` writes everything under `Assets/ProbeTests/asset/Made/`:

- assets: a texture (readable, uncompressed, at most 256), a sound (forced to mono, streamed), a model (global scale
  2, no animation), URP Lit and Unlit materials, a material on the family's own shader (`Assets/Params.shader`: a
  Vector, an Integer and a Colour property), one on the error shader, two at paths with a space, parentheses and
  letters outside ASCII, a ScriptableObject (`AssetWaveSet`: every plain kind of field, a list of structs, references
  set and not set, NaN, infinity, an AnimationCurve, a private field, an enum whose values aren't its indexes), an
  animator controller with two parameters, and a mesh of two parts;
- prefabs: a lamp (`AssetSpinner` on its root; a pole with a collider, a bulb without, a base whose collider is off
  and whose material is the pipeline's default, a light), a variant of it that overrides the spinner, a post with the
  lamp nested in it, and one whose component marks itself changed whenever it loads (`AssetDirtier`);
- `Level.unity`: tagged cubes (one inactive, one with an empty slot), a group of walls (a collider, a parent's
  collider, none, a trigger), the lamp on layer Water, a cube on the error shader, a spinner with a quad on the
  family's shader, the mesh of two parts with one material, the variant, the post, an object that marks itself changed
  when it loads, an instance of a prefab that was deleted, a cube whose material was deleted and a cube whose
  collider is a 2D one;
- `Other.unity`: two cubes, so that measures of two scenes run in one pass;
- `Big.unity`: 5,051 objects (50 rows of 100 cells, and a marker that logs each time the scene loads);
- `Facts.unity`, the scene the play opens: a URP camera and a uGUI image (scripts of packages), two cubes marked
  static that share a material, `AssetFacts` (what the game sees of its player when the scene wakes), and references
  to a material and a sound that were deleted;
- `Deleted.txt`: the deleted assets and their GUIDs.

It also sets the project's own player settings to a new project's least helpful ones: another company, a splash
screen, full screen 1920x1080 and resizable, not running in the background, one instance only, no player log,
IL2CPP, static batching on, code stripping High, a development build.

## The editor pass (`measures.json`, checked by `saved`)

Every field of an `asset` measure on every kind of asset above (`shader:`, `keyword:`, `import:`, `prop:`), every
field of a `scene` or `prefab` measure (`count`, `material_default`, `material:`, `mesh_collision`, `prop:`), every
error the docs list, word for word, and paths that aren't the project's (`..`, backslashes, an absolute path), which
are refused. It also proves that the pass opens each scene once for all of its measures (the marker's lines in the
pass's log) and that assets which mark themselves changed when they load are loaded (their lines in the log) while
the runner finds no file changed. Two more passes on requests the checker never writes show a result that can't be
written arriving through the log's `TASK_PROBES` line, a number as the nonce echoed, and a request without a
`measures` object refused with exit code 2.

## The build (play `facts`)

The play reads, from the game's side, what the checker's build promises whatever the project's own settings are: the
company name the checker deletes saved data by, no splash screen, the Mono backend, not a development build, a
960x540 window, a member that only reflection reads kept through code stripping, and static cubes that keep their own
mesh. The check also reads the build's result (its keys; the played scene's references to assets that are gone, and
no script of a package among them), the project's settings after the build (still its own), and plays two players of
the build at once (both run to their end).

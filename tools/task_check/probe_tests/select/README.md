# select: object selects, points, prop: paths, rows, JSON

What every kind that selects objects shares (`Find.cs`, `Reflect.cs`, `Json.cs`, `Query.cs`): an object select's keys
alone and together, points and `near`, `has`, the depth limit, the probe's own objects (never a match), the order
matches come in, `prop:` paths, rows past 200 with `total` and `full`, JSON in and out, and what a select costs.
`Editor/SelScenes.cs` builds three scenes.

## SelLab.unity

- The player (`SelHero`, tagged Player) and a main camera with an AudioListener (the probe puts its audio tap there).
- `component`: two scripts named `SelTwin` in two namespaces; `SelCoin` implementing the interface `ISelPickup` (a
  template, `CoinT`, is cloned twice at Start, and the additive scene has one more); `SelBase` and `SelDerived`; a
  nested type `SelNest.Inner` added at run time; `SelData`, a C# class no component can be.
- `tag` (`SelTag`, added by the builder), `layer` (`SelLayer`, the first free user layer), names with a dot,
  parentheses, any case and letters outside ASCII; inactive objects and an inactive child of an active one.
- `near`: objects around (10, 0, 0) at several heights, an anchor and a neighbour, and a mark exactly 10 m along the
  camera's view.
- `has`: lights that are on, at intensity 0 and disabled; a drawn and a disabled renderer; a part far from its
  object; an object with nothing but its transform; bodies on children: a Rigidbody, a kinematic one, one on an inactive
  child, a Dynamic and a Kinematic Rigidbody2D; an object saved Static and one not.
- Orders: four roots made one after the other, two UI roots (a RectTransform alone, a Canvas) and four instances of a
  prefab (`SelRootPrefab`), whose order in the player is read from the saved scene file; three children made out of
  name order, an object with two BoxColliders, 300 children `Fill_000`...`Fill_299` at x = 0...299, an object moved to
  the DontDestroyOnLoad scene, `SelSide.unity` (a lower build index than SelLab's) loaded additively at Start, a root
  made at 1 s, a root made every frame from 1.4 to 1.6 s (one in the frame of the 1.5 s sample, after an input
  searched) and a child made a root at 1.5 s (`SelDirector`). `SelRootInfo` reports what the player itself sees of its
  object's place: sibling index, place in its scene's root list, its scene's build index and place in SceneManager's
  list, and the names in that root list.
- `prop:`: `SelProps` holds a member of every kind (numbers of every width, NaN and infinities, enums, strings, vectors
  and colours, structs, arrays, lists, dictionaries, a set, object references set, unset and destroyed, a C# object,
  private members of its base class, a static member, a getter, one that throws, an indexer, one that counts its
  calls); a component of a type it lacks sits on a child. `SelPaint` reports, every frame, what its renderer, mesh
  filter and collider hold, so a read that copied an asset shows; `SelTextLike` has a copying `fontMaterial` as
  TextMeshPro's text has. `SelLocale` puts the game in another culture with `-selLocale <name>`.

## SelBig.unity

`SelCrowd` makes N objects when the scene wakes (`-selCrowd N`, default 3000) in trees of 21, every tenth carrying
`SelMark`. `SelEarlyBefore`/`SelEarlyAfter` (execution order -32001 and -31999) and `SelLateBefore`/`SelLateAfter`
(31999 and 32001) time the probe's own two halves from inside the player: its update half (every query's per-frame
work) and its late half (the samples).

## The plays

- `keys`: every key alone and together (see `tests.py`), each point form, `near`'s height band, the depth limit,
  `has`, and the probe's own objects: the tap on the listener, the hidden camera of a `drawn` query and the probe's
  object are never matched or read.
- `order`: a scene's roots come in the player's root list, not the Hierarchy's order: the check compares the list
  `SelRootInfo` reads with the saved scene file (plain roots by file id; the UI roots and the prefab instances by the
  rule it finds that list follows; it reads the file's names as Unity writes them: plain, in single quotes, or in double
  quotes with escapes, as `Snö☃` is); every root reports sibling index 0 in a player; children in sibling order; the
  DontDestroyOnLoad scene last, an additively loaded scene after the one loaded before it; a root made at run time and a
  child made a root come after the saved roots; two components of one type on one object in the Inspector's order; 300
  matches keep the first 200 rows with `total` and a `full` entry for every field asked for.
- `props`: every `prop:` path and the value it reads; reads through `material`, `materials`, `mesh`, a collider's
  `material` and a `fontMaterial` read the shared asset and copy nothing; a spec nested 100,000 deep ends the player
  with exit code 2 and its reason, not a stack overflow.
- `locale`: the same reads in a game running in de-DE (a decimal comma) give the same values.
- `cost_idle`, `cost3k_*`, `cost20k_*`: a whole-scene select, a component select and `spawns` over 3000 and 20,000
  objects; the measured cost is below.

## Cost

Measured in a non-development Windows player on the machine the family was written on, with other builds running; the
bounds the checks hold are eight times the measure or more, as such numbers vary from machine to machine. The late half
is the probe's sampling, the update half its per-frame work; a cost per sample is the late half's over the play less the
idle play's, per sample.

| Play | Query | Measured | Bound |
|---|---|---|---|
| `cost_idle` | none but the timer's, 3000 objects | late half 0.40 ms a frame, update half 0.02 ms | 5 ms |
| `cost3k_all` | objects `{}` over 3000 objects, field `x` | 7.2 ms a sample, the heap about 180 KB | 60 ms |
| `cost3k_mark` | objects `{"component": "SelMark"}`, 300 of 3000 | 2.0 ms a sample, about 160 KB | 20 ms |
| `cost3k_spawns` | spawns of `SelMark`, 300 of 3000 | 0.16 ms a frame | 5 ms |
| `cost3k_interface` | spawns of `ISelPickup`, 300 of 3000 | 0.60 ms a frame | 5 ms |
| `cost20k_all` | objects `{}` over 20,000 objects, field `x` | 49 ms a sample, about 580 KB | 400 ms |
| `cost20k_mark` | objects `{"component": "SelMark"}`, 2000 of 20,000 | 7.3 ms a sample, about 250 KB | 100 ms |
| `cost20k_spawns` | spawns of `SelMark`, 2000 of 20,000 | 1.0 ms a frame | 20 ms |
| `cost20k_interface` | spawns of `ISelPickup`, 2000 of 20,000 | 2.2 ms a frame | 20 ms |

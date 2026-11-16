# contact

The stages of a contact and what reads one (docs/task-probes.md, sections 1.4 and 2.21).

## Scenes

- `Duel.unity`: a hero (the player, a `ContactHero` that takes damage) facing +z on flat ground; `FoeNear` 6 m and
  `FoeFar` 12 m ahead of it, each a `ContactFoe` that walks 1 m/s along x and takes damage through `IDamageable`
  (returning what it applied, never more than its health); `FoeDead`, a dead foe nearer than both; a `Crate` that
  takes no damage.
- `Stops.unity`: `Stutter` moves 1 m/s and stands still for six frames of its own; `Clock` slows the game's time to a
  quarter for three frames and stops it for two.

## Plays

| Play | What it proves |
|---|---|
| `stage` | `set` (the nearest match, `all`, an enum by name, a private setter), `where` (a boolean, text, two conditions) and `"player": false`, `pin` (`front`, `at` with `offset`, held while the foe walks, released), `damage` (the default source, `from`, the player struck, `damage_taken`), and `inputs_missed` for every stage nothing took |
| `stops` | `frozen` and `world` `time_scale` and `paused` read stops that fall between two samples |

## Not tested

- A pin on an object moved by a Rigidbody, a CharacterController or a NavMeshAgent (the hold places it as a teleport
  places the player: `core`'s `body_*` plays).
- `frozen` on a skinned mesh: the Stutter is one rigid cube.

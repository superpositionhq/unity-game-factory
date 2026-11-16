# contact

The stages of a contact and what reads one (docs/task-probes.md, sections 1.4 and 2.21).

## Scenes

- `Duel.unity`: a hero (the player, a `ContactHero` that takes damage) facing +z on flat ground; `FoeNear` 6 m and
  `FoeFar` 12 m ahead of it, each a `ContactFoe` that walks 1 m/s along x and takes damage through `IDamageable`
  (returning what it applied, never more than its health); `FoeDead`, a dead foe nearer than both; a `Crate` that
  takes no damage. Far from them, `Armored` (its `IDamageable` has optional parameters after the contract's two) and
  `Odd` (an `IDamageable` that isn't the contract's).
- `Stops.unity`: `Stutter` moves 1 m/s and stands still for six frames of its own, during which a child is made and
  destroyed under it, another is made and keeps rising, and a part it had is destroyed; `Clock` slows the game's time to a
  quarter for three frames and stops it for two.

- `Bodies.unity`: a cube under gravity and an agent walking a NavMesh it bakes when the scene starts; `Thrower` (its
  `TakeDamage` throws) and `Mute` (its `TakeDamage` returns nothing).
- `Flat.unity`: a 2D game: a hero facing -x on a 2D floor, a foe with a 2D collider that walks along x.
- `Stops.unity` also holds `Skinned`, a skinned quad whose bone stops for six frames while it stands still.

## Plays

| Play | What it proves |
|---|---|
| `stage` | `set` (the nearest match, `all`, an enum by name, a private setter), `where` (a boolean, text, two conditions) and `"player": false`, `pin` (`front`, `at` with `offset`, held while the foe walks, released), `damage` (the default source, `from`, the player struck, optional parameters, `damage_taken` and no value for an object not struck), a `set` read back, and `inputs_missed` for every stage nothing took |
| `stops` | `frozen` and `world` `time_scale` and `paused` read stops that fall between two samples; children that come, go or move during a stop don't end it |
| `stop_real` | a hit stop timed on the real-time clock reads as short as it is: a play that reads `world` or `frozen` is paced to real time |
| `bodies` | a pin holds a Rigidbody in the air and a NavMeshAgent against its path; a `TakeDamage` that throws, one that returns no number, a `from` nothing matches, a fraction for a whole-number member; a stage's miss past the 400th row |
| `flat` | a pin in a 2D game: `front` along the player's facing in X, no turn, the depth kept; a second pin replaces the first |

## Not tested

- A pin on an object moved by a CharacterController (the hold places it as a teleport places the player: `core`'s
  `body_cc` play).
- A pin `at` a point with no player in the scene, and one whose object ends away from its spot.
- A stage that throws outside the game's own code (the probe's own catch).

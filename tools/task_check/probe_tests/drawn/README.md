# drawn: what is drawn in a place, and light read as rendered

The probe's `drawn` measure and the render behind lit / glow "as rendered" (`Runtime/Queries/DrawnQuery.cs`,
`Runtime/Queries/DrawnRender.cs`, `Runtime/Resources/TaskProbeDepthCopy.shader`). The numbers are checks in
`tests.py`; this file says what each scene holds and what each play proves.

## Scenes (`Editor/DrawnScenes.cs`)

The builder also adds a layer, `DrawnOnly`, and turns on the URP setting that keeps the shader variants of the URP
assets the build's scenes reference (`IncludeAdditionalRPAssets.includeReferencedInScenes`), so the family's own URP
asset can be switched to at run time: renderer 0 Forward (with a full-screen tint feature, and a RenderObjects pass
that alone draws `DrawnOnly`), 1 Forward+, 2 Deferred, 3 the 2D renderer; and a second asset with HDR off and render
scale 0.75.

- **DrawnLab**: under things a probe render must not show (an orange sun with soft shadows, a blue point light,
  exponential fog, a realtime reflection probe rendered once, a global volume with strong bloom and grading):
  - along z 0, what a `drawn` query reads: a red Lit cube, a cube with a red and blue checker texture, a white cube
    tinted by a property block, a red slab on a blue slab, a textured cube turning 90 degrees a second, a quad whose
    texture pans, translucent particles with a fixed seed, a cube activated at 5 s, a cube and a LineRenderer that grow
    along x from 2 to 12 s, a sphere 64 m across around the first places, world-space canvases beside cubes (one on the
    cubes' layer, one on the UI layer), a cube on the UI layer, one on `DrawnOnly`, the victim of the callbacks play,
    and a flat terrain of one even colour with a cube on it;
  - along z 20, light sources named `G_*`: URP Lit emissive cubes (read from their properties), a URP Unlit cube, dark
    and white Lit cubes, and, read as rendered: cubes, a sphere, a one-sided quad, a cube scaled to nothing and a
    cube 1000 m wide (far away) drawn with the family's own glow shader (`Assets/DrawnGlow.shader`: its light is its
    `_Glow` 1.5, no `_EmissionColor`), a skinned cube stretched 2 x 1 x 1 by its root bone, live particles, an
    emissive Lit cube and a white Lit cube each with a second material that draws nothing
    (`Assets/DrawnNothing.shader`, which puts them on the "as rendered" path), and a glow cube on the UI layer;
  - along z 60, 70 small glow cubes `B_00` to `B_69` for the budget of 64 renders a frame;
  - behind the player's camera, shadows off: a watcher cube, an Animator culled when unseen and a particle system
    paused when unseen, once inside a drawn place (z -45) and once in none (z -60);
  - the scripts: `DrawnLeakBefore` and `DrawnLeakWatch` (everything a render changes, as text, just before the probe's
    samples and just after them, and from one frame to the next), `DrawnCallbacks` (with `-drawnCallback`), `DrawnPipeline` (with
    `-drawnPipeline`), `DrawnCrowd` (with `-drawnCrowd`).
- **DrawnBaked**: a white Lit cube with a baked lightmap and a white sphere lit by 50 light probes, under a red baked
  light (the builder bakes with the CPU lightmapper; the runner's setup starts the editor with graphics).
- **DrawnCoin**: two coins as the sample game makes them (a root `Coin` that spins 180 degrees a second about the
  vertical and bobs 0.12 m, its child `Disc` a cylinder turned on its edge, gold, metallic and softly emissive),
  children of `CoinSpawner` at the origin, over a ground plane.

## Plays

- `plain`: DrawnLab with no render of the probe's: its screenshots are what `main` must match.
- `main`: every `drawn` field near a point and along a line (base colours from a property, a texture and a property
  block, emission cancelled, the height band, motion of a turning mesh, a panning texture and particles, a still
  scene reading 0, an object appearing, the enclosing rule, reach and length, a terrain read like a renderer), what
  the views leave out (the UI layer) and keep (a world-space canvas on a chosen layer); lit / glow as rendered through
  `objects` and `components` queries (the glow formula on boxes, a sphere, a one-sided quad, a box of nothing, a huge
  box, a skinned mesh's root-bone frame, particles, one material read from its properties and as rendered, no light
  reaching a render, the UI layer, the budget of 64 renders a frame in hierarchy order, one render a frame per
  renderer); what the game sees of the renders (callbacks, visibility, culled animation and particles, the cameras it
  can find); no state left changed in any frame; the game's screenshots the same as `plain`'s pixel for pixel; the
  cost of a render.
- `callbacks`: the game's camera callback throws at the probe's camera (one `query_errors` line, no value while it
  throws, values again after), switches the sun and fog on inside the render, destroys a renderer the render is
  drawing, and the probe's camera object is destroyed: nothing is left changed and the play goes on.
- `forward`, `forward_plus`, `deferred`, `hdr_off`, `d3d11`: the main play's values under the family's Forward
  renderer (its tint feature left out, its RenderObjects pass kept), Forward+, Deferred (a shader with only a forward
  pass draws nothing there, in the game as in the probe), HDR off with render scale 0.75, and Direct3D 11.
- `builtin`, `renderer_2d`: no render pipeline asset, and URP's 2D renderer: one `query_errors` line each, no `drawn`
  value and no glow as rendered, while what is read from properties still reads. (A player without a graphics device
  can't be played at all: the checker refuses `-nographics`, and the probe's play loop doesn't run without one.)
- `baked`: a lightmapped cube and a probe-lit sphere read their albedo.
- `coin`: the sample game's coin question. A place that follows a coin turning 90 degrees between samples reads motion
  at every sample; a place at the first match of `{"name": "Coin*"}`, the coins' parent at the origin, reads 0.
- `crowd`: 4000 more renderers in the scene, 1100 of them in one place: the first 1024 in hierarchy order are rendered,
  the same ones in both plays, and the cost of a sample in a large scene.

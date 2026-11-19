---
name: unity-mobile-game
description: 'The rules of a unity-game-factory game-building session that hold for a mobile (Android phone) game only. Use with the unity-game-session skill in every session that builds a game made with new-game.ps1 -Platform mobile (its root has a Platform.json), and with the unity-write-tasks and unity-check-tasks skills when writing and checking that game''s tasks. A desktop game''s session reads unity-desktop-game instead.'
---

# Mobile game (Unity)

Your game is an Android phone game, landscape or portrait, played by touch. Everything in the **unity-game-session**
skill holds; this skill is what holds for a mobile game alone, and it takes the place of the **unity-desktop-game**
skill, which you do not read. Where a shared rule names a keyboard, a mouse, Escape, a 1920x1080 window or a Windows
player as the product, the rule here is the one that applies.

## Start

- Create the project with `new-game.ps1 ... -Platform mobile -Orientation landscape` (or `portrait`), as the
  unity-game-session skill's Start says, with those two switches added. The orientation is chosen with the person
  before the project exists and never changes after.
- It writes `Platform.json` at the root (`{"platform": "mobile", "orientation": "..."}`), lays the mobile files over
  the skeleton (`Assets/Editor/Tools/Urp/MobileSetup.cs`, `Assets/Editor/Tools/BuildAndroid.cs`,
  `Assets/Scripts/Phone.cs`) and runs the mobile setup as the fifth run of the first open (`Scripts/unity.ps1 setup`):
  the URP pipeline asset set for a phone, one quality level (`Mobile`), the Android player settings (package name
  `com.<project in lower case>.game`, minSdk 26, targetSdk 34, arm64 alone, IL2CPP, Vulkan alone, the orientation) and
  the Windows player's window at the phone's size. Never edit or delete `Platform.json` or `Phone.cs`, and keep those
  settings as they came: every later tool reads the platform from that file, and the validators hold the project, the
  APK and the dataset to it (`tools/validate-game.py`, rule `mobile`).
- Android only. No iOS target, no tablet-only layout.

## Rendering

- **One renderer everywhere.** The game is drawn with URP's Universal Renderer through the project's one pipeline
  asset (`Assets/Settings/Rendering/URP_Pipeline.asset`) at its one quality level, `Mobile`, on the phone and on this
  PC alike. Never add a quality level, a second pipeline asset or a per-platform override: the Windows player would
  then draw what the phone does not. Change the pipeline asset itself only for something the phone can afford, and say
  why in the workflow row. The phone runs Vulkan; no HDRP, no ray tracing, and no look that depends on a desktop GPU
  (many real-time shadowed lights, heavy post-processing stacks, high MSAA). Light with baked or simple real-time
  lighting and check every material in the built player: a shader written for desktop can come out black or flat.
- **Look at the game as a phone draws it.** On this PC the game is its Windows player in a window of the phone's size:
  1920x1080 (landscape) or 1080x1920 (portrait). `Scripts/unity.ps1 build`, then `Scripts/unity.ps1 play -Render` or
  `autoplay`: `Phone.cs` draws every start of the player at that size, whatever size the command line asks for (on a
  display lower than the phone, full screen with the phone's picture scaled to fit; a bot run and a task play keep a
  real window of the phone's size there, larger than the screen). Every screenshot you judge the game by, the framing screenshots and the README stills come from such a play, never from
  the editor's Game view at another size.
- **Budgets, for a mid-range phone, in any view the player can reach:** at most 500,000 triangles drawn, at most 700
  draw calls, at most 1 GB of textures in memory. Design to them from the first scene (fewer, merged and instanced
  meshes, the SRP Batcher and GPU instancing, texture sizes chosen on purpose, few transparent layers, few real-time
  lights). A task may measure them (unity-write-tasks, the `render` reading, docs/task-probes.md section 2.20).
- The art style still decides the look (unity-game-session, "Art style"): bring it to the phone with materials, baked
  light and colour, not with desktop post-processing.

## Touch

- **Touch only.** Everything the player does is done with fingers on the screen: on-screen buttons, a virtual stick,
  taps, drags and swipes on the world. Nothing in the game is reachable only by a key, a mouse button, mouse movement
  or a gamepad. Build the controls as uGUI objects (or UI Toolkit elements), read through the Input System: its on-screen controls (`OnScreenStick`, `OnScreenButton`), the UI
  module's pointer events, or `Touchscreen.current` / EnhancedTouch for touches on the world. In the Windows player a
  mouse click is a pointer to the UI, so a person can try the game with the mouse; a control that reads the
  Touchscreen alone answers only to a finger (the bot's, a task's). A task presses a control by what a player sees on
  it: a button that shows words is tapped by those words, so give every button that means something a caption a
  player can read. A task names a control by its object's name only when that object already exists at the task's
  start (`seed.commit`), as a desktop click does: a control a task's thread adds has another name in another fair
  build, so its name is never one a task may rely on.
- **The back button.** Android's back button is `<Keyboard>/escape` to the Input System. It does what Escape does on
  a desktop game: it opens the pause menu in play, closes what is open, and goes back one screen in menus. It never
  quits without asking.
- **Sized for a thumb.** Controls a finger must hit are large and apart from each other, inside the screen's safe area
  (`Screen.safeArea`: away from the edges, the camera cut-out and the system gesture bar), and never under where the
  hands rest. Text is readable at phone size.
- **One orientation.** The layout is built for the game's orientation alone and fills it; no screen assumes the other.
- **Pause when the app leaves the foreground** (a call, the home button: `OnApplicationPause(true)`) and come back to
  the pause menu. The template's `runInBackground` stays on: it keeps the Windows player running while it is
  recorded, and Android pauses the app itself.

## Quality bar

- **Quality bar:** main menu, settings (volume, touch sensitivity where the game has a look or aim control), pause on
  the back button, save/load where it fits, HUD, sound, clear win/lose, a Windows x64 release player of the game at
  the phone's size (what is played and recorded here) and, at release, its Android APK (arm64, IL2CPP), which the
  pipeline builds. Recorded and TTS voices are allowed.
- **Room for hard tasks.** A game's tasks come from its own history (unity-write-tasks skill), and strong agents miss
  what only shows when the game runs. So build these in, and work them over several rounds rather than in one commit:
  feedback for every gameplay event (a HUD readout, marker, sound or effect); visible state changes (materials,
  colours, lights, dressing); a pause menu with settings and back navigation on the back button; touch controls whose
  size, place and response a player feels; tuned numbers a player feels (ranges, detection, damage, timers); views
  that stay inside the budgets. Fix each playtest issue in its own commit whose message says what the player saw, so
  the thread can be found and checked later.

## AutoPlay on a mobile game

- `Phone.cs` tells the AutoPlay drop-in the game is a phone game (`AutoPlay.Phone`): a run keeps the window at the
  phone's size and has a virtual Touchscreen from its first frame.
- **The bot plays with fingers.** It acts only through `AutoPlay.Touch(finger, screenPosition)` and
  `AutoPlay.TouchUp(finger)` (a tap is a touch in one frame and its lift in a later one; a virtual stick is a finger
  put down on it and moved; two thumbs are fingers 0 and 1) and `AutoPlay.Hold` / `Release` of `<Keyboard>/escape`,
  the back button. The drop-in refuses every other key, the mouse and the gamepad in a phone game's run
  (docs/autoplay-contract.md, section 4). Find a control's place from its own `RectTransform`, never from a number
  written for one screen size.
- The hand test and the recording are the same commands as a desktop game's (`Scripts/unity.ps1 autoplay`, the
  coordinator's queue); the video is 1920x1080 or 1080x1920.

## Tasks on a mobile game (with the unity-write-tasks skill)

- A mobile game's tasks are played at the phone's size (1920x1080 or 1080x1920) with a touch screen; the task check
  does this itself from `Platform.json`. A task's play never chooses a window size, a quality level or a graphics API
  in its arguments (no task's may: the validator refuses them).
- **Drive the game by touch.** A play's inputs use `tap` and `drag` (docs/task-probes.md section 1.3): a spot on the
  screen as fractions of its width and height, or `{"widget": ...}`; `hold` for a held touch, `finger` for a second
  finger. The back button is the key `<Keyboard>/escape`. **Press a control by what a player sees:** `{"widget": ...}`
  with the words the button shows (`{"widget": "Jump"}` taps the button reading "Jump"), else by a name or type the
  start (`seed.commit`) already has, as a desktop click; never by a widget name the task's thread creates. A control
  that shows no words and that the thread adds is touched at its place on the screen where the instruction or the
  start's layout fixes it. _(why: a control the thread adds has its name only in the reference; another fair build
  names it otherwise, and a correct solution then fails the play. A spot is the last resort: its place differs
  between landscape and portrait)_
- **One finger lifts before it touches again.** Two touches of one finger are at least 0.1 s apart, lift to start, and
  every touch is over by the play's end (the validator refuses a task that asks otherwise). _(why: a finger still down
  from an earlier touch can't touch again, and the touch is a missed input)_
- **A brief written for a mobile game never asks for a key, a mouse, a click, a gamepad or an Escape key**; Android's
  back button is fine. _(why: a phone has none of them, so no touch play can check such an ask, and the Lab's review
  counts it as unchecked whatever the checks are)_
- Good mobile threads to look for in your history: a control that was too small or badly placed and took rounds to
  fix, a layout broken in the game's orientation, a view over a budget brought back under it (the `render` reading,
  in a play of its own with no `drawn`, `lit` or `glow` check), the back button's behaviour, the pause on leaving the
  app.

## Build, recording and dataset

- You build and test the Windows player only (`Scripts/unity.ps1 build`). The release pipeline builds the same player
  from the release commit and, on a machine with the editor's Android Build Support (with OpenJDK and the Android SDK
  & NDK tools), the APK through the game's `Assets/Editor/Tools/BuildAndroid.cs`; it reads the APK back and refuses
  one that is not arm64 alone, at the SDK levels and with the package name above. On a machine without the Android
  toolchain the APK step is skipped and says so (`machine/check.ps1` reports the toolchain, docs/new-machine.md says
  how to install it): the game still plays and records, but **a mobile game is released only with its APK**, so the
  release build and the package are made on a machine that has the toolchain.
- The scenario videos are recorded from the Windows player at the phone's size. The dataset's manifest says
  `"platform": {"kind": "mobile", "orientation": "..."}`, and its `Build/` holds the Windows player and, when it was
  built, the APK.
- `tools/validate-game.py` reads `Platform.json` and holds a mobile game to this skill's project settings (rule
  `mobile`).

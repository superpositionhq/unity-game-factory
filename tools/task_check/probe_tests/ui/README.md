# ui family tests (`widgets`, `ui`, the glyph reader, widget and cursor clicks)

Project: a Unity 6000.3.28f1 URP project with uGUI 2.0 (TextMeshPro), Input System 1.20.1, UI Toolkit module.

## Files

- `BuildUiTest.cs` (goes in `Assets/Editor/UiTest/`): `UiTest.EditorTools.BuildUiTest.Run` builds `Assets/Scenes/UiTest.unity`.
  `ImportTmp` tries `AssetDatabase.ImportPackage` on TMP's essential resources, but in `-batchmode -quit` the import
  never finished (no `Assets/TextMesh Pro`). The test project extracted `TMP Essential Resources.unitypackage` (a tar.gz
  of `<guid>/asset|asset.meta|pathname`) into `Assets/` with a few lines of Python before building the scene.
- `UiTestDriver.cs`, `UitkTestPanel.cs`, `StrokeReadout.cs` (go in `Assets/Scripts/UiTest/`): the scene's logic.
- `ui1.json`: the play spec (20 s, 4 shots, 29 queries, widget clicks and cursor clicks).
- `ocr_harness/`: an offline harness for the glyph reader. `png2raw.py shot.png out.raw`, then copy
  `Runtime/Queries/UiOcr.cs` beside it and run `dotnet run -- out.raw x0 y0 x1 y1` (.NET 10). It reads a screenshot as
  the probe reads a frame.

## The scene

- An Overlay canvas `HudCanvas` with:
  - `ScoreText`: TMP text that counts up 10 per 0.5 s.
  - `LegacyLabel`: a legacy `Text`.
  - `HealthSlider`: falls 5 a second from 100.
  - `FillBar`: a filled Image, 0 to 1 every 10 s.
  - `SoundToggle`: starts on.
  - `HiddenPanel`/`HiddenText`: hidden by a CanvasGroup at alpha 0.
  - `InactivePanel`/`InactiveText`: an inactive panel.
  - `ChangeButton`: when clicked, `ClickLabel` reads `CLICKED n`.
  - `CursorButton`: when clicked, `CursorLabel` reads `CURSOR n`.
  - `OverlapLabel`: a Text at alpha 0.01 over the readout's second line.
- A Screen Space - Camera canvas, `CamCanvas`, with `CamPanel` (a blue box) and `CamText` (TMP), at the bottom right.
- A world-space canvas, `WorldCanvas`, with `WorldText`.
- A UIDocument, `UitkDoc`, with:
  - its PanelSettings asset and a TSS theme `@import url("unity-theme://default");`, both made in code;
  - elements built in code: `UitkLabel` (`UITK n` per second), `UitkButton` (`GO`, which sets `UitkClicks` to
    `CLICKS n`), `UitkProgress` (0 to 100 at 10 a second), `UitkHidden` (`display: none`), `UitkInvisible`
    (`visibility: hidden`), `UitkCursorButton` and `UitkCursorLabel`.
- `StrokeReadout`: OnGUI rotated rectangles along the centre lines of a stroke font, white on a dark box at pixel
  (20,390)-(420,520). Line 1 is `TIME m:ss` and line 2 is `HP n%`.

## What the play proves (values from the last run)

- **widgets**
  - `text`: `ScoreText` read `SCORE 0` and then `SCORE 160`. A regex select `^SCORE \d+$` picks only it.
  - `percent` and `value`:
    - Slider: `percent` 0.977 to 0.577, `value` 97.7 to 57.7.
    - Filled Image: `percent` 0.047 to 0.847.
    - ProgressBar: `percent` 0.047 to 0.847, `value` 4.7 to 84.7.
    - Toggle: `value` 1, then 0 after the widget click.
  - `has_brush`/`brush`: `FillBar` 1 / `UISprite`. A uGUI Button 1 / `UISprite`. A UITK Button 0.
  - `interactable`: 1 on the Slider, Toggle and Buttons.
  - `visible`: 0 for `HiddenPanel` and `HiddenText` (CanvasGroup alpha 0), `InactivePanel` and `InactiveText`
    (inactive), `UitkHidden` and `UitkInvisible`, and the Toggle's `Checkmark` once the toggle is off (its
    CanvasRenderer alpha fades to 0). `select.visible: true` drops all of these.
  - `x y w h`:
    - `ScoreText` (0.0208, 0.0370, 0.3125, 0.0741) = pixels (20, 20, 300, 40).
    - The Camera-canvas `CamPanel` (0.729, 0.667, 0.25, 0.111) = pixels (700, 360, 240, 60), as in the screenshot.
    - `UitkLabel` (0.648, 0.044, 0.208, 0.056) = pixels (622, 24, 200, 30). It was placed at left 620, top 20; the
      default theme offsets it a few pixels.
    - `UitkHidden` (display none) has no `x`/`w`.
  - `component: Button` returns both uGUI and UI Toolkit buttons. `name: Cam*` matches by wildcard.
- **ui**
  - Rows carry `source`, `kind`, `name` and `class`. Overlay, Camera and UITK elements are read; `WorldText` is never
    a ui row.
  - Hidden, inactive and display-none elements are absent.
  - Kinds: TMP, Text and Label are `text`; sprite Images are `image`; `CamPanel` (no sprite), the UITK Button
    background and the ProgressBar's inner bars are `box`. A UITK Button gives a box row and a text row, as a uGUI
    button gives an image and a child text.
  - `text` changes: `CLICKED 1`, `CURSOR 1`, `CLICKS 1`, `UCURSOR 1`, `SCORE 400`, `UITK 20`.
  - A `rect` select keeps the elements whose centre is inside: the box rect [0.6,0.6,1,1] holds `CamPanel` and
    `UitkCursorButton`.
  - Every sample has `rows`.
- **The glyph reader** (`select: {kind: text, rect: [0.022,0.73,0.43,0.96]}`):
  - Line 1 joins as an `ocr` row. It read `TIME 0:00` through `TIME 0:20` in 37 of the 41 samples. The 4 misses are
    the seconds with a `3` (see limits).
  - Line 2 (`HP n%`) is left to `OverlapLabel` (rows show `ugui` `HP` only). Read offline from a screenshot without
    the overlap, it reads `HP 94%` and `HP 96%`.
  - A `text` regex with a rect (`TIME\s*\d+:\d\d`) also reads the frame.
  - The rect [0.03,...] cuts into the `T` stroke: the reader then refuses line 1 (`uOcrCut`: no ocr row).
  - TMP `SCORE n` at 32 px reads nothing: too bold for its size (loose distance > 0.15). Its ugui row stands.
- **Widget clicks**
  - `ChangeButton` sets `ClickLabel` to `CLICKED 1` (onClick through ExecuteEvents).
  - `UitkButton` sets `UitkClicks` to `CLICKS 1` (NavigationSubmitEvent drives Button.clicked).
  - `SoundToggle` turns its value to 0.
  - `NoSuchButton` logs `no visible button matches`.
- **Cursor clicks with the window never focused**
  - A cursor move to the button plus a `<Mouse>/leftButton` press and release clicked the uGUI `CursorButton`
    (`CURSOR 1`), through the EventSystem's InputSystemUIInputModule.
  - The same clicked the UI Toolkit `UitkCursorButton` (`UCURSOR 1`), through the EventSystem integration.
  - This needed no core change: the core's `backgroundBehavior = IgnoreFocus` is the setting the module checks
    (`shouldIgnoreFocus`).

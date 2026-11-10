# ui: widgets, ui, screen, widget and cursor clicks

The queries that read the UI: `widgets` (a uGUI or UI Toolkit widget's own state), `ui` (every element on screen in
the frame drawn after a sample, whatever UI system drew it), `screen` (the frame's brightness), and the inputs that
click it: the widget click (`UiScan.Click`) and the cursor (a `cursor` input, then `<Mouse>/leftButton`). The frame
text reader (`UiOcr`) has its own family, `ocr`; here only what `ui` decides about it is tested (when the frame is
read, and that a line an element already reads isn't read twice).

Two rules say whether a widget shows, and the scenes pin both. `visible` (the `widgets` field and select, and what the
widget click takes) is the original's state: the object active, every Canvas up the chain enabled, its graphic
enabled, the CanvasGroups' alpha above 0.004 (UI Toolkit: displayed, its own visibility visible, the opacity above
0.004), on a canvas or panel drawn on the screen, inside the frame; its colour, its size and clipping don't count. A
`ui` element is drawn: visible so, and its colour and CanvasRenderer alpha above 0.004 too, not culled by a RectMask2D
nor outside an enabled Mask, and of some size. Both read every element of a UI Toolkit panel, the parts a control
builds inside itself too (a Slider's tracker and dragger, a ProgressBar's bar), each named by its name or, unnamed, by
its type, so a `name` wildcard such as `Vis*` also matches an unnamed part (`VisualElement`).

## The scenes (`Editor/UiScenes.cs`, written under `Made/`)

The project needs TextMeshPro's essential resources for TMP text to draw; when it has none, the builder copies them
from the package's own `TMP Essential Resources.unitypackage` into `Made/` (an import through
`AssetDatabase.ImportPackage` never finishes in `-batchmode -quit`), so TMP draws as in a game made from the template.

- **Hud**: a 960x540 frame of every kind of widget, each at a known place. On the left an Overlay canvas: TMP texts
  (one in rich text that `UiHudDriver` sets every frame, a typewriter with `maxVisibleCharacters`, one inside a panel
  that is hidden at 0.5 s and whose text changes at 1 s), legacy Texts with and without rich text, a Slider that falls
  10 a second, a filled Image that rises, a Toggle, a Scrollbar, input fields with and without text (legacy and TMP),
  dropdowns (legacy and TMP), images with and without a sprite or texture, a game's own component on an Image and on
  an object without a graphic (with a text under it), a panel that is only a CanvasGroup, a button whose first label is
  inactive, and a row of `Vis*` objects, one for each way a widget is or isn't on screen (alpha 0, 0.004 and 0.01, a
  CanvasGroup, scale 0, off the frame and half off it, outside and inside a RectMask2D, under a disabled Canvas, a
  disabled Text, a disabled Button whose Image still draws, a non-interactable Button, a CanvasGroup at 0, an inactive
  panel, a Mask that hides its own graphic, a text inside and one outside that Mask, a text under another canvas's
  box), and a row laid out by a HorizontalLayoutGroup whose first box leaves at 1 s. `Rect*` objects are placed every
  other way: turned 45 degrees, on a canvas scaled from 1920x1080, on a Screen Space - Camera canvas, on a camera canvas
  drawn into a render texture, on one whose camera is off, on world-space canvases in front of and behind the camera.
  On the right
  a UI Toolkit document (`UiToolkitHud`): a label in rich text counting frames, an image, boxes made by a background and
  by a border, a progress bar counting frames, sliders, a toggle, a dropdown, text fields with a value and with only a
  placeholder, a scroller, buttons, the `VisUitk*` ways an element is or isn't on screen (display none, visibility
  hidden, a visible child of a hidden parent, opacity 0 and 0.004, off the frame, width 0, disabled), a turned box, a
  label without a name, a password field, a label inside a Box and a box that moves at 1 s; a second document on a
  panel scaled from 1920x1080, a third on a panel drawn into a render texture, and a document without panel settings.
- **Clicks**, **ClicksOld**, **ClicksNone**: the same buttons under the Input System's UI module, under the old
  `StandaloneInputModule`, and with no EventSystem. Each uGUI clickable counts its pointer events and what it fires
  (`UiClickCount`; `UiTriggerCount` for EventTrigger entries; `UiClickWatch` reads the EventSystem's selection); the UI
  Toolkit document (`UiToolkitClicks`) counts its buttons' clicks. Among them: two buttons of one name, a button off the
  frame, one not interactable, one whose Button is disabled, one fully transparent, one under a half-transparent image
  that takes the cursor's raycast, a button that takes no selection (`NavNoneButton`), a Slider, a Slider under a
  parent that takes clicks, an InputField and a Dropdown, a UI Toolkit button that only has a `ClickEvent` callback.
- **Grey**: the camera clears to sRGB grey 64; Overlay images cover the right half with sRGB grey 192 and the top left
  corner with a white and a black box. `-uipost` turns on the camera's post-processing and a volume that doubles the
  exposure; `-uiquit` quits the game in the frame of the 1 s sample.
- **Crowd**: 300 uGUI texts and 200 UI Toolkit labels in a grid.

## The plays (`tests.py` checks every value)

- `widgets` (Hud): every field of each widget type of both systems, `visible` for each way, the rectangles of each
  placement, the selects (`component` by a base type, by a game's own type and, with a `name`, on an object or element
  above; `name`, alone finding a panel with no graphic; `text`, which a button matches through its label as the label
  itself does; `visible`), the order of the rows (siblings in the scene's order); an unnamed part of a UI Toolkit
  control is a widget named by its type; the frame shows the visible child of a hidden UI Toolkit parent.
- `ui` (Hud): which elements are on screen, their kind, source, text (a password as its mask) and rectangle; the
  selects (`kind`, `text`,
  `rect`); a select of text in a rect reads the frame and leaves a line an element reads to that element; a layout
  change made in a sample's frame is in the frame drawn after it (`ui`); at the sample (`widgets`) UI Toolkit's is
  already there (the player loop lays the panels out before LateUpdate) and uGUI's not yet (a canvas is laid out when
  it's drawn).
- `life` (Hud, `-uilife`): an object destroyed after a sample is still a widget at that sample and gone from the frame
  drawn after it; a canvas and a UI Toolkit element made in mid-play; a scene load asked for in mid-play (the frame
  that asks still holds the old scene, for `widgets` and `ui` alike; the next sample reads the new one).
- `errors` (Hud): a regex that doesn't compile, a kind that isn't one and a field that doesn't exist each give their
  line in `query_errors`; the rest of the query still reads.
- `clicks`, `clicks_old`, `clicks_none`: widget clicks (each pointer event, from the enter to the exit; uGUI's under
  either module, and with no EventSystem none, as a player's click: probe.log says so and the game's log stays clean;
  UI Toolkit's always) and cursor clicks (uGUI's only through the Input System's UI module; UI Toolkit's through it,
  or on its own with no EventSystem).
- `screen`, `screen_post` (Grey): the values of known greys over rects of every kind (inverted, empty, on the edge,
  outside the frame, with fractional edges); after post-processing the camera's grey changes and the UI's doesn't.
- `quit` (Grey, `-uiquit`): what the samples of the frame the game quits in hold.
- `crowd_bare`, `crowd_ui`, `crowd` (Crowd): 500 elements, 200 rows kept with `total` and `full`; the cost of a
  sample, from the plays' real times in `probe.log`.

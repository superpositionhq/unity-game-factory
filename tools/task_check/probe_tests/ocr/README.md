# ocr family tests (the ui query's frame reader)

The frame reader (`TaskProbe/Runtime/Queries/UiOcr.cs`) reads text from the frame as drawn, inside the rect of a `ui`
select of text (`"kind": "text"`, or a `text` regex, with a `rect`). These tests check what it reads in a real
player; `harness/` checks that it still gives its reference readings.

## The scene

`Editor/OcrScenes.cs` makes `Made/OcrLab.unity`: a camera with a dark solid background, orthographic at one unit a
pixel, and `OcrLab`, which puts up what a play shows by the play's argument `-ocrlab`. Every readout is an
`OcrReadout`: one line of text drawn without UI components, as strokes along the centre lines of the reader's own glyph
shapes, each segment a rectangle half a stroke longer at both ends, dots and dashes as boxes. A readout is drawn one of
three ways:

- OnGUI: a rotated texture a segment, as a HUD drawn with OnGUI does. The GUI matrix covers a slanted stroke's pixels a
  little differently from the stroke's exact quad, so whether a glyph reads there depends on where it stands to a
  fraction of a pixel. The glyph plays use this way, with the `Plain` font (one shape of the reader's table per
  character).
- GL quads (in OnGUI's repaint) and a mesh the camera draws: both cover exactly the pixels whose centres their quads
  hold. A readout that a play checks a rule with is drawn this way, in the `Steady` font (each character a shape that
  reads at every sub-pixel place at the size it is drawn), so that it reads wherever it stands.

Time is counted in frames, so a sample at play time t sees exactly the text of t. A box the reader gives is checked
against the ink in the screenshot of the same frame, pixel for pixel.

## The plays

- `clock`: a clock (`TIME m:ss.f`, tenths of a second) and a number (`HP n`, 97 less every half second) drawn as a mesh,
  and the clock again in GL quads, change at every sample and read at every sample, through a select of text in a
  rect and through a regex with a rect; the checker's `clock` and `number` (`probes.ui_clock`, `probes.ui_number`) read
  them. The screenshots show the frame holds the displayed sRGB bytes (the background colour set as 0.08, 0.08, 0.12
  reads 20, 20, 30: within a step of 20.4, 20.4, 30.6; linear bytes would be 2, 2, 3).
- `glyphs16`, `glyphs24`, `glyphs36`: every character the reader knows, two of a kind (a sign beside a 4), each in a
  query of its own, drawn with OnGUI at 16, 24 and 36 px. Each reads as itself, or nothing where the reader can't tell
  it for sure (an O is a 0 without its slash; at some sizes D, Q, B, S, I, W and a 2 drawn this way): never as another
  character. `tests.py` says why each refused one is refused.
- `limits`: what the reader refuses, each beside the same readout read: a rect whose edge touches or cuts the first
  stroke; a 3 with short hooks at both ends drawn with OnGUI and 4 px strokes at 36 px (the flat-topped 3 reads);
  strokes too bold or too small for their size; slanted text; a lone character; ink too faint; a rule across the line;
  a background that varies. A frame around a line doesn't stop it.
- `found`: a line under a uGUI text is left to that element (its row, not the line's), while a line under a uGUI box
  still reads; a select with a rect but no kind or text reads the elements alone.
- `select`: only a select of text in a rect reads the frame (kind text or a regex, with a rect; corners given either
  way round); kind text without a rect, a rect alone, kind box or image, a regex without a rect read no line; a rect
  past the frame, of no size, or before it reads nothing and says nothing; a uGUI label's own pixels are not read twice.
- `cap`: 280 lines read in one frame: the sample keeps the first 200 rows and counts and sums every match (`total`,
  `full`).

## harness/

The reader outside Unity, against its reference readings: `python harness/check.py` draws the synthetic frames of
`harness/frames.py` (every shape of the reader's table, HUD strings at HUD sizes, every cap style, anti-aliased and
not, every rule's case, rects of every kind), compiles `UiOcr.cs` with the Unity editor's own compiler, reads them on
the editor's Mono (a player's runtime), and compares each reading with the reader's reference reading of the same
frame (`harness/expected.txt`). About two and a half minutes; no player build. Run it after any change to `UiOcr.cs`:
the plays check the reader in the engine, this checks it still reads as its reference does. It first checks that the
reader's glyph table is the reference table's 121 entries (`harness/table.txt`, which the frames are drawn from) and
that `harness/Read.cs` reads a frame as `Query.cs` does. What it doesn't pin: the order of marks that start in one
column (the sort of a line's marks was compared once with the reference line by line and by traces; no frame is
known whose reading depends on it), and many of the reader's thresholds (of 101 one-token changes
tried, 29 changed a reading here): a change to a threshold needs frames of its own on both sides of it.

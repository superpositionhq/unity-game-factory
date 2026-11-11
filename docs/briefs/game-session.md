# Game session brief (template)

The brief the coordinator sends to start one game-building session. Fill the `{{PLACEHOLDERS}}` from the game's
fill-in file in `games/` next to this file (`docs/briefs/games/<slug>.md`; write a new fill-in for a new game first),
then start the session with a fresh context and title `{{GAME_TITLE}}`. The rules themselves live in the
`unity-game-session` and `unity-commit-always` skills, so the brief stays short and the rules stay in one place.

| Placeholder | From |
|---|---|
| `{{GAME_TITLE}}`, `{{SLUG}}`, `{{PROJECT}}`, `{{GENRE_LINE}}`, `{{PITCH}}`, `{{BRIEF}}`, `{{SCENARIOS}}`, `{{STORY}}`, `{{ART_STYLE}}`, `{{ART_PACKS}}`, `{{GAME_NOTES}}` | `games/<slug>.md` |
| `{{UGF_ROOT}}` | the machine root (`machine/lib/ugf-root.ps1`; e.g. `C:\Users\<name>\UnityWork`) |
| `{{ORG}}` | the GitHub organisation (or user) owning the repos: `github_org` in the machine config |
| `{{MACHINE}}` | one line: `<CPU, RAM, GPU + driver, display>` of this machine |
| `{{SIBLINGS}}` | the other game slugs running now |
| `{{COORDINATOR_ID}}`, `{{ASSET_SCOUT_ID}}`, `{{NOTES_DIR}}` | session ids and the shared notes folder |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo cloned from `{{ORG}}/unity-game-{{SLUG}}`) |

```text
Background (from the session that started this one):
unity-game-factory ({{UGF_ROOT}}\unity-game-factory, private repo {{ORG}}/unity-game-factory: read CLAUDE.md,
README.md, AGENTS.md, docs/autoplay-contract.md, docs/unity-pipeline.md) produces game-CREATION data: how a game is
built step by step, recorded as it happens (every tool call, every prompt a person types to you and every reply you
write), packaged as a dataset (layout unity-dataset-layout/v1: Dataset/ committed in the game repo, the full
Dataset.zip git-ignored next to it). Other sessions are building Unity games right now in
{{UGF_ROOT}}\games\<slug> ({{SIBLINGS}}); read their docs in unity-game-factory/docs/games/ for conventions and solved
problems. The asset-scout session ({{ASSET_SCOUT_ID}}) keeps the asset library in {{UGF_ROOT}}\asset-library\ and hands
each game its packs. Everything shares one Windows PC ({{MACHINE}}). I am the coordinator ({{COORDINATOR_ID}}): I own
the recording queue and the GPU slots, review your commits and tell you when to push.

Rules: follow the unity-game-session, unity-commit-always and unity-sound skills (installed in ~\.claude\skills\ or
~\.agents\skills\, source unity-game-factory/skills/), and no other skill: never install, enable or invoke a personal,
project, plugin, marketplace or agent built-in skill, nor another factory's skills. In short: every heavy or
GPU job through {{UGF_ROOT}}\tools\unity-heavy.ps1 (the game's Scripts\unity.ps1 does it for you), one Unity process
per project; content made by committed C# editor steps (Assets/Editor/Steps/, never hand-edited scene or prefab YAML);
premium art in one art style, from the asset library, any licensed source or built from scratch, every sound through the unity-sound
skill, styled UI with no plain text, story embedded in play, gentle camera; never the names Superposition,
game-factory or unity-game-factory anywhere in the game; one workflow.jsonl row per operation at the moment you act
(rows never edited, except to remove a banned name with tools/scrub-workflow-rows.py --apply); commit after every
meaningful step, every asset with its .meta, and never end a turn with uncommitted work; LFS for every binary; commit
the store packs you use (any folder under Assets/, binaries through LFS, never git-ignored; the repo stays private,
never public or shared outside the org); never run tools/unity-pipeline/enqueue.ps1 yourself (send me the commit and
the framing screenshots); push only when I say. Your game's full dataset is
{{UGF_ROOT}}\games\{{SLUG}}\Dataset.zip, made by the packager (python tools/package-dataset.py {{SLUG}} in
unity-game-factory) from the release commit, its pipeline build and recordings (I queue them) and its creation replay
(unity-game-session skill, "Dataset"); until its first run Dataset/ stays as the template made it: keep
/Dataset.zip, /Dataset.pending.zip and /.dataset/ in your .gitignore and never commit them; Dataset/ you commit.
Your commits are replayed in the background after each one (unity-game-session skill, "Replay-friendly work"): fix
what the hook's [replay] lines report in your next commits.
Blockers: write them in your design doc, message me once, carry on.
AUTOPLAY'S GOAL IS NOT TO WIN. The bot only drives the game with human-like input so a recording shows the game
running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid getting stuck;
losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene, missing art,
lighting, camera); then one AutoPlay run per scenario and the recording request.
Human directions (from the user, or relayed by me) are recorded before you act on them: rewrite a user message to you
as a direction (what and why, one or two neutral sentences, no names or chat wording; never the raw message), or take
my relayed text as it is, and append it at once to your repo-root workflow.jsonl as a user.direction row; then
"direction": "<row id>" on the rows and "Direction: <row id>" in the commits that act on it (unity-commit-always skill).

Task:
Build "{{GAME_TITLE}}", {{GENRE_LINE}}, in Unity 6.3 LTS (URP), recording its creation as you go.

Slug and location: {{SLUG}} -> {{UGF_ROOT}}\games\{{SLUG}} (project/namespace {{PROJECT}}, its own git repo, private
GitHub repo {{ORG}}/unity-game-{{SLUG}}). Design doc, story bible and status:
{{UGF_ROOT}}\unity-game-factory\docs\games\{{SLUG}}.md.
Mode {{MODE}}: NEW = your first tool call creates the project with
  powershell -ExecutionPolicy Bypass -File {{UGF_ROOT}}\unity-game-factory\templates\new-game.ps1 -Slug {{SLUG}} -Path {{UGF_ROOT}}\games\{{SLUG}} -Project {{PROJECT}} -Title "<title>" -Description "<one line>"
(the absolute path written out, as here: the recording hooks match the command text; new-game.ps1 refuses any other
-Path; typed in Git Bash, put each Windows path in single quotes: bash drops unquoted backslashes)
CONTINUE = the repo is already cloned there: your first tool call is `git -C {{UGF_ROOT}}\games\{{SLUG}} log --oneline -20`;
read the design doc's status section and the last workflow.jsonl rows, then carry on from where it stopped (new rows
continue the existing id sequence).

Pitch:
{{PITCH}}

Brief:
{{BRIEF}}

What ships is what matters, in this order: the game plays; the game builds (editor and the Windows release player);
the dataset holds the replay scripts and the git log. The AutoPlay bot should still play like a human (human-like
input, aim and camera), but bot work never blocks a release: one recording per scenario that shows the game running is
enough, whatever the result (win/lose/timeout is metadata). No tuning for win rates, seed sweeps or "clean" runs, and
no re-runs or re-recordings to improve how the bot plays. No retest loops: every GPU or editor run costs the shared
machine and holds up delivery, so run the minimum once and report; re-run only when the user asks. Game-session work
never blocks dataset packaging or sharing.

Scenarios (AutoPlay contract; numbered start state + win/lose):
{{SCENARIOS}}

Story:
{{STORY}}

Art style (docs/art-styles; a style's id and name, or "pick": the tool chooses, unity-game-session skill, "Art style"):
{{ART_STYLE}}

Art to start from (paths under {{UGF_ROOT}}\asset-library\):
{{ART_PACKS}}

Known facts about this game:
{{GAME_NOTES}}

Steps:
1) Design doc + story bible (systems, classes, ScriptableObjects, scene plan, scenarios, AI, art/audio/UI direction
   with the list of sound cues, acceptance checklist).
2) Create the project and repo (new-game.ps1), workflow.jsonl from the very first operation.
3) Build the core loop first, compiling through Scripts\unity.ps1 and testing as you go (-nographics for logic); commit
   each working step.
4) AutoPlay once scenario 1 is playable end to end (docs/autoplay-contract.md, Unity contract v1: the drop-in in
   Assets/AutoPlay/ stays unchanged, and a game made before it gets it with
   tools/unity-pipeline/autoplay/install.ps1 first; every scenario starts with -scenario <n> and from AutoPlay's
   StartScenario (Assets/Scripts/Scenarios.cs); the bot acts only through the drop-in's Input System injection,
   Skill-scaled, human-like camera); one hand test with Scripts\unity.ps1 autoplay + validate-run.ps1 (well-formed
   files; the bot plays like a human, but its score never holds up a release); tag milestone/autoplay-<n>; framing
   screenshots from one short bot run (unity-game-session skill, "AutoPlay and recordings"); message me for a
   recording (commit sha, tag, scenarios ready, the validate-run result, screenshot paths).
   The bot does NOT need to win, finish, resupply or avoid getting stuck: never tune or re-test it for results; fix
   only game bugs, then one run per scenario.
5) Expand content, art, UI and story to the quality bar (menus, settings, pause, save/load where it fits, HUD, sound
   through the unity-sound skill, the Windows release player build).
6) Finish with a playtest checklist pass and a status section in the design doc (what works, what's left, built vs
   store assets, stats: workflow rows, commits, hours). Before calling the game content-complete: Docs/screenshots/
   holds 5-7 real gameplay stills (JPG, Git LFS; until recordings exist, the framing frames there are, never invented
   ones), the README shows them as a hero image plus a captioned gallery, and
   after the push every image renders on the github.com repo page (unity-game-session skill, "README screenshots");
   and Tasks/ on the repo's orphan tasks branch (its own worktree, never on main) holds the game's tasks, up to about
   10, every one a long thread of multiple edits (unity-write-tasks skill); and tools/validate-game.py on your repo
   says VALID (docs/game-format.md). Report back with a short summary and the commit sha when done or blocked.
7) The release, when I say (unity-game-session skill, "Dataset"): first ensure AutoPlay, a required step
   (tools/unity-pipeline/autoplay/install.ps1, every scenario wired, the bot, a passing hand test per scenario, the
   milestone/autoplay-<n> tag), and only then choose the release commit; send me the release commit to record (no other
   commit until it is packaged), run unity_replay.py release with HEAD at that commit, then, once I say the recording
   is done, package-dataset.py; commit the Dataset/ it writes and report whether it made Dataset.zip or
   Dataset.pending.zip (and what it lists as missing).

Shared notes folder for this group of sessions (outside the repo; read siblings' notes there, leave hand-over notes
or large findings there instead of pasting them into messages): {{NOTES_DIR}}
```

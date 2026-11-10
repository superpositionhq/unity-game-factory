# Game session brief (template)

The brief the coordinator sends to start one game-building session. Fill the `{{PLACEHOLDERS}}` from the game's
fill-in file in `games/` next to this file (`docs/briefs/games/<slug>.md`; write a new fill-in for a new game first),
then start the session with a fresh context and title `{{GAME_TITLE}}`. The rules themselves live in the
`unity-game-session` and `unity-commit-always` skills, so the brief stays short and the rules stay in one place.

| Placeholder | From |
|---|---|
| `{{GAME_TITLE}}`, `{{SLUG}}`, `{{PROJECT}}`, `{{GENRE_LINE}}`, `{{PITCH}}`, `{{BRIEF}}`, `{{SCENARIOS}}`, `{{STORY}}`, `{{ART_PACKS}}`, `{{GAME_NOTES}}` | `games/<slug>.md` |
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
built step by step, recorded as it happens, packaged as a dataset (layout unity-dataset-layout/v1: Dataset/ committed
in the game repo, the full Dataset.zip git-ignored next to it). Other sessions are building Unity games right now in
{{UGF_ROOT}}\games\<slug> ({{SIBLINGS}}); read their docs in unity-game-factory/docs/games/ for conventions and solved
problems. The asset-scout session ({{ASSET_SCOUT_ID}}) keeps the asset library in {{UGF_ROOT}}\asset-library\ and hands
each game its packs. Everything shares one Windows PC ({{MACHINE}}). I am the coordinator ({{COORDINATOR_ID}}): I own
the recording queue (not available yet) and the GPU slots, review your commits and tell you when to push.

Rules: follow the unity-game-session, unity-commit-always and unity-sound skills (installed in ~\.claude\skills\ or
~\.agents\skills\, source unity-game-factory/skills/), and no other skill: never install, enable or invoke a personal,
project, plugin, marketplace or agent built-in skill, nor the Unreal game-factory's skills. In short: every heavy or
GPU job through {{UGF_ROOT}}\tools\unity-heavy.ps1 (the game's Scripts\unity.ps1 does it for you), one Unity process
per project; content made by committed C# editor steps (Assets/Editor/Steps/, never hand-edited scene or prefab YAML);
premium art from the bought/downloaded Asset Store packs and animation packs, every sound through the unity-sound
skill, styled UI with no plain text, story embedded in play, gentle camera; never the names Superposition,
game-factory or unity-game-factory anywhere in the game; one workflow.jsonl row per operation at the moment you act
(rows never edited, except to remove a banned name with tools/scrub-workflow-rows.py --apply); commit after every
meaningful step, every asset with its .meta, and never end a turn with uncommitted work; LFS for every binary; commit
the store packs you use (any folder under Assets/, binaries through LFS, never git-ignored; the repo stays private,
never public or shared outside the org); never queue recordings yourself (the recording queue is not available yet:
report what is ready to me); push only when I say. Your game's full dataset is
{{UGF_ROOT}}\games\{{SLUG}}\Dataset.zip, made by the packager (not available yet: until it is, Dataset/ stays as the
template made it): keep /Dataset.zip, /Dataset.pending.zip and /.dataset/ in your .gitignore and never commit them;
Dataset/ you commit. Your commits will be replayed by the creation replay (not available yet: nothing replays them
today); work so they can be (unity-game-session skill, "Replay-friendly work"). Blockers: write them in your design
doc, message me once, carry on.
AUTOPLAY'S GOAL IS NOT TO WIN. The bot only drives the game with human-like input so a recording shows the game
running. Never tune, fix or re-test the bot to win, score, finish, reach targets, resupply or avoid getting stuck;
losing, timing out or wandering is fine (metadata). Fix only game bugs (crash, hang, broken scene, missing art,
lighting, camera); then one AutoPlay run per scenario and the recording request. The AutoPlay drop-in and the recorder
are not available yet: until they are, write no AutoPlay code and no bot, make every scenario start from the command
line with -scenario <n>, and report what is ready to me (unity-game-session skill).
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

Art to start from (paths under {{UGF_ROOT}}\asset-library\):
{{ART_PACKS}}

Known facts about this game:
{{GAME_NOTES}}

Steps:
1) Design doc + story bible (systems, classes, ScriptableObjects, scene plan, scenarios, AI, art/audio/UI direction
   with the list of sound cues, acceptance checklist).
2) Create the project and repo (new-game.ps1), workflow.jsonl from the very first operation.
3) Build the core loop first, compiling through Scripts\unity.ps1 and testing as you go (-nographics for logic tests);
   commit each working step.
4) Once scenario 1 is playable end to end, make the game ready for AutoPlay (the drop-in is not available yet: no
   AutoPlay code, no bot): every scenario starts with -scenario <n>, all input through the Input System, no pause or
   mute on focus loss, every action reachable by input; the design doc's status says AutoPlay is open. Framing check
   from one short rendered play per scenario (unity-game-session skill, "AutoPlay and recordings"); report to me what
   is ready (commit sha, the scenarios that start with -scenario <n>, the release build's result, screenshot paths).
   The bot does NOT need to win, finish, resupply or avoid getting stuck: never tune or re-test it for results; fix
   only game bugs, then one run per scenario.
5) Expand content, art, UI and story to the quality bar (menus, settings, pause, save/load where it fits, HUD, sound
   through the unity-sound skill, the Windows release player build).
6) Finish with a playtest checklist pass and a status section in the design doc (what works, what's left, built vs
   store assets, stats: workflow rows, commits, hours). Before calling the game content-complete: Docs/screenshots/
   holds 5-7 real gameplay stills (JPG, Git LFS), the README shows them as a hero image plus a captioned gallery, and
   after the push every image renders on the github.com repo page (unity-game-session skill, "README screenshots");
   and Tasks/ on the repo's orphan tasks branch (its own worktree, never on main) holds the game's tasks, up to about
   10, every one a long thread of multiple edits (unity-write-tasks skill); and tools/validate-game.py on your repo
   says VALID (docs/game-format.md). Report back with a short summary and the commit sha when done or blocked.

Shared notes folder for this group of sessions (outside the repo; read siblings' notes there, leave hand-over notes
or large findings there instead of pasting them into messages): {{NOTES_DIR}}
```

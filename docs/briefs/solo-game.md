# Solo game brief (plain Claude Code or Codex)

For one person building one game with one coding-agent session in a terminal, Claude Code (`claude`) or OpenAI Codex
CLI (`codex`): no desktop app, no coordinator, no other sessions. The rules are the same as for a coordinated game
session (the `unity-game-session` and `unity-commit-always` skills, installed by `machine/setup.ps1`); what the
coordinator would do (queue recordings, decide pushes, relay directions, hand out store packs) is done by you, the
person at the keyboard. You queue a recording from a terminal of your own, never through the session:
`powershell -ExecutionPolicy Bypass -File <root>\unity-game-factory\tools\unity-pipeline\enqueue.ps1 <slug> -RequestedBy coordinator`
([../unity-pipeline.md](../unity-pipeline.md), "Queue"; by default a run waits until the PC has had no input for 5
minutes). With the desktop app and several games at once, start each game session from
[game-session.md](game-session.md) instead.

Start: open a terminal in the machine root (`cd <root>`, e.g. `C:\Users\<name>\UnityWork`; not another
factory's root, whose `CLAUDE.md` and `AGENTS.md` load its own rules) and run one of

- `claude` (its `<root>\CLAUDE.md` loads the unity-game-factory rules), or
- `codex -s danger-full-access` (its `<root>\AGENTS.md` names the rules; the full-access sandbox is needed because
  Unity writes its caches and licence state under `%LOCALAPPDATA%` and `%APPDATA%`, the job limiter uses machine-wide
  mutexes, and git / gh need the network; `codex` asks once to trust the folder),

then paste the `text` block below with the placeholders filled. Stay in this one session for the whole game where you
can (resume it with `claude --continue` or `codex resume --last`): the recording (every tool call, every prompt you
type and every reply the model writes) follows the session, and a new session is filed under the game only from its
first tool call that names the game folder. For a game that has a fill-in in
`games/` next to this file, take the pitch, scenarios and story from it; for a new game, write them in a few lines
each.

| Placeholder | From |
|---|---|
| `{{GAME_TITLE}}`, `{{SLUG}}`, `{{PROJECT}}` | the title, a lowercase slug (`island-survival`) and a PascalCase project name (`IslandSurvival`) |
| `{{PITCH}}`, `{{SCENARIOS}}`, `{{STORY}}`, `{{ART_PACKS}}` | `games/<slug>.md`, or your own few lines |
| `{{UGF_ROOT}}` | the machine root (e.g. `C:\Users\<name>\UnityWork`; `machine/lib/ugf-root.ps1`) |
| `{{ORG}}` | the GitHub organisation (or user) owning the repos: `github_org` in the machine config |
| `{{MODE}}` | `NEW` (no repo yet) or `CONTINUE` (repo already cloned into `{{UGF_ROOT}}\games\{{SLUG}}`) |

```text
You are the only session on this machine: build "{{GAME_TITLE}}" in Unity 6.3 LTS (URP) and record how it is built.
There is no coordinator and there are no other sessions: never start, spawn or message other sessions. Whatever the
skills say to send to "the coordinator" (recording requests, push requests, Asset Store requests, blockers), tell me
here and wait for my answer.

Read first: {{UGF_ROOT}}\unity-game-factory\AGENTS.md, README.md, docs/autoplay-contract.md, docs/unity-pipeline.md,
and the unity-game-session, unity-commit-always and unity-sound skills
({{UGF_ROOT}}\unity-game-factory\skills\<name>\SKILL.md; installed for your agent too). They hold the rules; in short:
- use only the unity-game-factory skills (unity-commit-always, unity-game-session, unity-sound, unity-write-tasks):
  never install, enable or invoke any other skill (personal, project, plugin, marketplace, built into the agent, or
  another factory's), even when one is offered;
- every editor, build or GPU job through {{UGF_ROOT}}\tools\unity-heavy.ps1 (the game's Scripts\unity.ps1 does it for
  you); one Unity process per project; content made by committed C# editor steps, never hand-edited scene or prefab
  YAML;
- premium art from store packs (any folder under Assets/, committed with their .meta files, binaries through Git LFS,
  never git-ignored; the repo stays private), every sound through the unity-sound skill, styled UI with no plain text,
  story embedded in play, gentle camera; never the names of the toolkit or its owners inside the game;
- one workflow.jsonl row per operation at the moment you act (rows are never edited, except to remove a banned name
  with tools/scrub-workflow-rows.py --apply); commit after every meaningful step, every asset with its .meta, never
  end a turn with uncommitted work; LFS for every binary;
- my messages that change the game are directions: rewrite each as one or two neutral sentences and append it to
  workflow.jsonl as a user.direction row (via "direct") before acting on it (unity-commit-always skill);
- AutoPlay's goal is NOT to win: the bot only drives the game with human-like input; fix game bugs, never tune the
  bot; one AutoPlay run per scenario; the AutoPlay drop-in in Assets/AutoPlay/ stays unchanged;
- your commits are replayed in the background after each one: fix what the hook's [replay] lines report in your next
  commits (unity-game-session skill, "Replay-friendly work");
- push only when I say; never run tools/unity-pipeline/enqueue.ps1 (recordings are queued by me, if at all).

Game: {{GAME_TITLE}} ({{SLUG}} -> {{UGF_ROOT}}\games\{{SLUG}}, project {{PROJECT}}, private GitHub repo
{{ORG}}/unity-game-{{SLUG}}). Design doc, story bible and status:
{{UGF_ROOT}}\unity-game-factory\docs\games\{{SLUG}}.md (create it if missing).
Mode {{MODE}}: NEW = your first tool call creates the project with
  powershell -ExecutionPolicy Bypass -File {{UGF_ROOT}}\unity-game-factory\templates\new-game.ps1 -Slug {{SLUG}} -Path {{UGF_ROOT}}\games\{{SLUG}} -Project {{PROJECT}} -Title "<title>" -Description "<one line>"
(the absolute path written out: the recording hooks match the command text; typed in Git Bash, put each Windows path
in single quotes: bash drops unquoted backslashes).
CONTINUE = your first tool call is `git -C {{UGF_ROOT}}\games\{{SLUG}} log --oneline -20`; read the design doc's
status and the last workflow.jsonl rows and carry on.

Pitch:
{{PITCH}}

Scenarios (AutoPlay contract; numbered start state + win/lose):
{{SCENARIOS}}

Story:
{{STORY}}

Art to start from (store packs in {{UGF_ROOT}}\asset-library\, or ask me for Asset Store packs):
{{ART_PACKS}}

Steps:
1) Design doc + story bible; 2) create the project (new-game.ps1); 3) core loop first, compiling and testing through
Scripts\unity.ps1, committing each working step; 4) AutoPlay once scenario 1 plays end to end
(docs/autoplay-contract.md, sections 6-7; a game made before the drop-in gets it with
tools/unity-pipeline/autoplay/install.ps1 first): one hand test with Scripts\unity.ps1 autoplay +
tools/unity-pipeline/validate-run.ps1, tag milestone/autoplay-<n>, framing screenshots from one short bot run
(unity-game-session skill), then tell me; 5) content, art, UI, sound (unity-sound skill), the Windows release player
build; 6) playtest checklist, status section in the design doc, and
before calling it content-complete: 5-7 real gameplay stills in Docs/screenshots/ (JPG, LFS; until recordings exist,
the framing frames there are, never invented ones) shown in the README as a hero image plus a captioned gallery,
checked on github.com after I say push; Tasks/ with at least 5 and up to about 10 tasks on the game, every one a hard, long thread of
multiple edits, on the tasks branch, never on main (unity-write-tasks skill); tools/validate-game.py VALID; 7) the
release, when I say (unity-game-session skill, "Dataset"): first ensure AutoPlay, a required step
(tools/unity-pipeline/autoplay/install.ps1, every scenario wired, the bot, a passing hand test per scenario, the
milestone/autoplay-<n> tag), and only then choose the release commit; tell me the release commit so I queue its
recording (no other commit until it is packaged), run unity_replay.py release with HEAD at that commit, then, once I
say the recording is done, package-dataset.py; commit the Dataset/ it writes. Report each milestone here with the
commit sha.
```

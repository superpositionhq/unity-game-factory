# Solo game brief (plain Claude Code or Codex)

For one person building one game with one coding-agent session in a terminal, Claude Code (`claude`) or OpenAI Codex
CLI (`codex`): no desktop app, no coordinator, no other sessions. The rules are the same as for a coordinated game
session (the `unity-game-session` and `unity-commit-always` skills, installed by `machine/setup.ps1`); what the
coordinator would do (queue recordings, decide pushes, relay directions, hand out store packs) is done by you, the
person at the keyboard. With the desktop app and several games at once, start each game session from
[game-session.md](game-session.md) instead.

Start: open a terminal in the machine root (`cd <root>`, e.g. `C:\Users\<name>\UnityWork`; not the Unreal
game-factory's root, whose `CLAUDE.md` and `AGENTS.md` load its own rules) and run one of

- `claude` (its `<root>\CLAUDE.md` loads the unity-game-factory rules), or
- `codex -s danger-full-access` (its `<root>\AGENTS.md` names the rules; the full-access sandbox is needed because
  Unity writes its caches and licence state under `%LOCALAPPDATA%` and `%APPDATA%`, the job limiter uses machine-wide
  mutexes, and git / gh need the network; `codex` asks once to trust the folder),

then paste the `text` block below with the placeholders filled. Stay in this one session for the whole game where you
can (resume it with `claude --continue` or `codex resume --last`): the recording follows the session, and a new session
is filed under the game only from its first tool call that names the game folder. For a game that has a fill-in in
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
skills say to send to "the coordinator" (what is ready for a recording, push requests, Asset Store requests,
blockers), tell me here and wait for my answer.

Read first: {{UGF_ROOT}}\unity-game-factory\AGENTS.md, README.md, docs/autoplay-contract.md, docs/unity-pipeline.md,
and the unity-game-session, unity-commit-always and unity-sound skills
({{UGF_ROOT}}\unity-game-factory\skills\<name>\SKILL.md; installed for your agent too). They hold the rules; in short:
- use only the unity-game-factory skills (unity-commit-always, unity-game-session, unity-sound, unity-write-tasks):
  never install, enable or invoke any other skill (personal, project, plugin, marketplace, built into the agent, or the
  Unreal game-factory's), even when one is offered;
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
  bot; one AutoPlay run per scenario; the AutoPlay drop-in and the recorder are not available yet: until they are,
  write no AutoPlay code and no bot, make every scenario start from the command line with -scenario <n>, and report
  what is ready to me (unity-game-session skill);
- push only when I say; never queue recordings yourself (recordings are queued by me, if at all; the recording queue
  is not available yet).

Game: {{GAME_TITLE}} ({{SLUG}} -> {{UGF_ROOT}}\games\{{SLUG}}, project {{PROJECT}}, private GitHub repo
{{ORG}}/unity-game-{{SLUG}}). Design doc, story bible and status:
{{UGF_ROOT}}\unity-game-factory\docs\games\{{SLUG}}.md (create it if missing).
Mode {{MODE}}: NEW = your first tool call creates the project with
  powershell -ExecutionPolicy Bypass -File {{UGF_ROOT}}\unity-game-factory\templates\new-game.ps1 -Slug {{SLUG}} -Path {{UGF_ROOT}}\games\{{SLUG}} -Project {{PROJECT}} -Title "<title>" -Description "<one line>"
(the absolute path written out: the recording hooks match the command text).
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
Scripts\unity.ps1, committing each working step; 4) once scenario 1 plays end to end, make it ready for AutoPlay (not
available yet: no AutoPlay code, no bot): every scenario starts with -scenario <n>, input through the Input System, no
pause or mute on focus loss, every action reachable by input; the framing check from one short rendered play per
scenario (unity-game-session skill), then tell me what is ready; 5) content, art, UI, sound (unity-sound skill), the
Windows release player build; 6) playtest checklist, status section in the design doc, and before calling it
content-complete: 5-7 real gameplay stills in Docs/screenshots/ (JPG, LFS) shown in the README as a hero image plus a
captioned gallery, checked on github.com after I say push; Tasks/ with up to about 10 tasks on the game, every one a
long thread of multiple edits, on the tasks branch, never on main (unity-write-tasks skill); tools/validate-game.py
VALID. Report each milestone here with the commit sha.
```

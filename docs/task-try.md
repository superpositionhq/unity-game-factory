# Task try: run a task with a coding agent (internal)

**Contractors don't run this** (owner, 2026-11-05: it took up to 25 minutes a task). Judge a task's difficulty in the
game session instead (unity-write-tasks skill, section 6). We run the try on submitted tasks.

The task check ([task-check.md](task-check.md)) proves a task is fair: the start fails it and the reference passes.
The task try tells you whether it is hard enough. It gives the task to your own coding agent, Claude Code or Codex on
your own subscription, exactly as an agent gets it in the cloud, then grades what the agent left with the task's own
probes. Every task must be a long thread of multiple edits (unity-write-tasks skill, section 1); if your agent solves
it easily, the task isn't done yet.

```powershell
python tools\task-try.py C:\Users\<you>\UnityWork\games\<slug> --task <task-name> --agent claude
python tools\task-try.py C:\Users\<you>\UnityWork\games\<slug> --task <task-name> --agent codex --runs 3
python tools\task-try.py C:\Users\<you>\UnityWork\games\<slug> --task C:\Users\<you>\UnityWork\tasks\<slug>\Tasks\<task-name>.json --agent claude
```

Each task prints one line, for example:

```
0/3 solved  stealth-fix-guards-lose-the-player  (best 4/7 required checks)
2/3 solved  rally-racer-corr-chase-camera  (best 7/7 required checks)
```

Options: `--runs N` (default 1), `--model M` (the harness's model; default its own), `--agent-arg ARG` (an extra
argument for the harness, repeatable), `--keep` (keep the workspaces and the built games), `--out DIR`,
`--scratch DIR`, `--direct`, `--timeout S`, `--build-timeout S` (as the task check's).

## Before you run it

- The task check says VALID (`tools/task-check.py`). The try builds the start and the reference too, but tells you
  nothing useful about a task that isn't valid.
- `claude` or `codex` is on PATH and logged in (run it once by hand). The try runs it headless: Claude Code with
  `-p --permission-mode bypassPermissions` and its hooks off, Codex with `exec -s danger-full-access`; the agent can
  run anything on your computer, as a game session can.
- Requirements as the task check's: Windows, the project's Unity 6.3 LTS editor installed and an active Unity licence
  (a batchmode run without one exits 198), Python 3.12, git and Git LFS with both commits' objects fetched, and short
  paths (Unity fails past 260 characters: give `--scratch` a short folder when the default is refused). Disk: one full
  copy of the game per run (the agent edits it, so it can't be a hardlink) with its own `Library/`, plus the start and
  the reference built once.
- Time: the agent gets the task's `limits.max_minutes` (Claude Code also its `max_turns`), then one build and the
  plays per run. Each workspace imports every asset the first time the agent or the grade opens it. A long thread can
  take hours per run; start it before you leave the machine.

## What it does

1. Builds and measures the start and the reference once, as the task check does, for the probes' thresholds.
2. Per run, copies the game at `seed.commit` into a workspace `<drive>:\.task-try\<id>\run<N>\<game>`: every file of
   that commit without `Tasks/`, `History/`, `Dataset/` or `Dataset.zip`, in a fresh git repository with one commit.
   The workspace is outside the machine root and the game repo, so the harness reads neither's `AGENTS.md` or
   `CLAUDE.md`.
3. Starts the harness in the workspace with the brief as its prompt: the task's instruction, the scene and arguments
   QA plays (`play_scene`, `play_args`) and where the Unity 6.3 editor is installed. Nothing of the grader's half. The
   machine's recording hooks record nothing for it (`UGF_NO_RECORDING`, with the Unreal factory's `GF_NO_RECORDING`
   set too), so a try never enters a game's record.
4. When the agent stops (or its time runs out), stops whatever it left running in the workspace (an editor or a
   player: any process whose command line names the workspace), removes the build outputs (`Temp/`, `Obj/`, `Logs/`,
   `Build/`, `Builds/`) but keeps `Library/` (Unity's import cache, keyed by each asset's content and import settings,
   so what the agent left there can't change what a build makes), adds the probe package as `Packages/com.taskprobe/`,
   builds and plays the agent's game (on a desktop of its own, as the task check's plays) and runs every check but
   judges, trace probes and packaging, against the thresholds of step 1.

Results: `<repo>\.task-tries\<task>.json` (format `task-try/1`): per run `solved` (every required check passed),
`score` (the weighted share of checks passed, as the cloud scores it, judges left out), `required_passed` of
`required`, `milestones` reached, `seconds`, `timed_out`, `turns` and `usd` when the harness reports them, the
`checks` rows, and `peeked`; `status` is `DONE`, or `ERROR` with its `reasons` when the try couldn't run (the line then
reads `ERROR   <task>: ...`, for example a start or reference that doesn't build: run the task check first). Each run's
transcript is `<task>\run<N>\transcript.jsonl`, its plays beside it, and the brief the agent read `<task>\brief.md`;
the start's and the reference's plays are in `<task>\start\` and `<task>\reference\`, as the task check keeps them.

## Reading the result

- **Longest run under 25 minutes:** shorter than the guide (about 25 minutes or more). It's a guide, not a
  requirement: a task the agent doesn't solve is a good task at any length. The printed line notes it. A run that hit
  its own time limit or crashed says nothing about length.
- **Solved in any run, quickly:** too easy. Extend the thread back to an earlier attempt, merge it with its
  neighbouring issues, or drop it (unity-write-tasks section 6).
- **Never solved, but some required checks pass:** what a hard task looks like. Read the transcript: the agent should
  fail because the work is long and the cause is far away, not because the brief is missing something a player would
  know or the play scene is wrong.
- **Nothing passes, not even the build:** check the agent could build at all (the transcript); an agent that never
  found the editor, or ran into a licence error or a project lock (two Unity processes on its workspace), says nothing
  about the task.
- **`peeked` lists a folder** (the printed line: `transcript names ...: it may have read the answer`): the transcript
  names your game repo or tasks worktree, where the history and the answer are, or the machine root or your agent's
  own folders (`~\.claude`, `~\.codex`, `~\.agents`: its sessions, memory and skills). That run doesn't count: the
  cloud agent can't reach them. Run it again, or from an account that can't read those folders.

The try is advice for you. The cloud's own runs and grade decide approval, difficulty and pay. Codex runs with a home
of its own (your login, every skill off), but Claude Code also has your own harness settings, skills and memory, which
the cloud agent doesn't; keep them out of its way when you can.

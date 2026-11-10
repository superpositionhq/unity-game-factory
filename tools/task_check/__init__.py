"""The task checker: a contractor checks their own tasks before handing them in (docs/task-check.md).

For one task (a GameTask JSON on a game repo's `tasks` branch, docs/schemas/game-task.schema.json) it builds the game at
the task's start (seed.commit) and at its reference (seed.reference, when the task has one), plays both with the
TaskProbe package, measures every probe, and says whether the task is VALID: the start fails it, the reference passes
it, and what must still work already works at the start.

Modules:
- tasks: reading tasks from a repo and their checks, with the schema's defaults filled in;
- probes: the probe's queries, reducing a play's samples to one number, the editor pass's request and results;
- colour: URP's colour grading applied to a neutral grey (the grading probe's derived fields);
- verdict: thresholds (literal, calibrated, relative to the start) and the VALID/INVALID rules;
- seeds: a commit of the game materialized outside the repo, with its Git LFS objects and the probe package;
- unity: player builds, plays and the editor pass (through the machine's unity-heavy.ps1 when it has one);
- check: one task checked end to end; cli: `python tools/task-check.py`;
- trial: one task tried with the contractor's own coding agent and graded (`python tools/task-try.py`,
  docs/task-try.md).

Standard library only (Python 3.12)."""

FORMAT = "task-check/1"  # the result file's format

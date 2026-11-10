---
name: unity-commit-always
description: 'Commit discipline for every unity-game-factory session (game builders, helpers, coordinator). Use whenever you change files in a Unity game repo or in unity-game-factory, before ending any turn, and when deciding what may be committed or pushed. Covers commit cadence, messages, workflow.jsonl rows, .meta files, LFS, what never to commit, push policy and the WIP auto-commit hook.'
---

# Commit always (Unity)

The git history is the product: a game's `git.log` and `workflow.jsonl` are the creation record the dataset is built
from, and uncommitted work is invisible to the coordinator, the packager and the pipeline (the packager builds from
commits; the pipeline, not available yet, will too).
The user's standing rule: **every session commits its work continuously.**

## When

- After every meaningful step: a system compiles and runs, an editor step ran and changed content, a scene or asset
  set is imported, a bug is fixed and verified, a doc section is written, a tool change passes its test. At least
  every ~15 minutes of active work.
- Before anything risky (a Unity version upgrade, a render pipeline conversion, a mass rename or move of assets,
  `git lfs migrate`, a long build).
- **Never end a turn with uncommitted work of yours.** Last step of every turn: `git status`, commit what is yours,
  then report the sha.

## Which repo, which files

- **Game session:** your game repo (`%UGF_ROOT%\games\<slug>`): `git add -A` is fine there, it is yours alone.
  In unity-game-factory you own only `docs/games/<slug>.md`; commit it with
  `git commit -m "..." -- docs/games/<slug>.md`.
- **Helper / coordinator:** unity-game-factory is one checkout shared by several sessions. Stage explicit paths only
  (`git add <paths>`, `git commit -- <paths>`), never `git add -A` / `git commit -a`, never commit another session's
  changes. If someone else has uncommitted edits in a file you must change, commit only your change (write your
  version of the blob into the index with `git hash-object -w` + `git update-index --cacheinfo`, or ask them first).

## Message

- Subject: what changed, imperative, specific (`Add frost tower slow stacking and its tuning asset`), under ~72
  chars.
- Body: why, how it was verified (build/test/run result), anything left open.
- Game repos: end with the workflow rows the commit covers: `workflow: td-00412..td-00431`. A commit that acts on a
  human direction also names it: `Direction: td-00398 (<the direction in a few words>)`.
- Game repos: no AI attribution trailers or footers (`Co-Authored-By: <agent> ...`, `Generated with <tool>`) and never
  the names Superposition, game-factory or unity-game-factory: commit messages ship in the dataset's `git.log`. Agent,
  model and provider names (Claude, Anthropic, Opus, OpenAI, Codex CLI, GPT model ids) stay out too; deliverables
  block or scrub them. unity-game-factory commits follow the normal attribution rules.

## workflow.jsonl (game repos)

- Rows are written **when the operation happens**, not at commit time (schema `unity-workflow/v0`: `schema, id, seq,
  time` (ISO 8601 ms + offset), `actor:"agent", op, target, params, reason` (intent at that moment),
  `reason_source:"agent_note", status` (`observed`/`failed`/`reverted`), `source {script, sha256, commit}`).
- Commit `workflow.jsonl` together with the work it describes; the row ids go in the message. Many games also log an
  `op:"vcs.commit"` row (sha, subject, files) right after committing; it rides along in the next commit.
- Never edit, delete, reorder or backfill rows. Missed something: one `op:"log.gap"`, `status:"unrecorded"` row saying
  what and when. Failed attempts get rows too.
- **One exception (user rule): banned names.** A row that contains a banned name (studio/org name, the tool repos'
  names, agent/tool/provider names, the account name or machine paths with it, e-mail addresses) is edited in place to
  remove it, with a neutral word or placeholder and nothing else in the row changed; then one correction row is
  appended (`op:"log.correct"`, `params {rows: [ids], what: "removed banned names"}`), and the commit message names the
  edited rows. `python <UGF_ROOT>/unity-game-factory/tools/scrub-workflow-rows.py <repo>` does exactly this (dry run
  first, then `--apply`; it prints the commit message line). Write new rows without such names in the first place
  (relative paths, neutral words). The account name is enforced in every non-script file (workflow.jsonl, configs,
  docs, data); scripts and editor steps that already ran keep it (never edited; the packager scrubs them in every
  delivery), new ones use relative paths.
- Every editor step that ran stays in `Assets/Editor/Steps/` unchanged (a new step in a new file instead of
  overwriting), so `source.script` + `source.sha256` point at the real code.
- **Human directions (user rule: "not direct user messages, more like user directions"; "you should rewrite that and
  save to the workflow.jsonl").** Whoever receives a user message REWRITES it as a direction: what to change and why,
  one or two neutral sentences, without tone, profanity, names or chat wording (a game session for a message to it;
  the coordinator before relaying, sending the rewritten text ready to log). The rewritten direction is SAVED at once,
  before any action, by appending it to the game repo's own `workflow.jsonl` (the file at the repo root: the live
  source the packager copies, scrubbed, into `Dataset/workflow.jsonl`; never edit `Dataset/workflow.jsonl` by hand).
  A relayed direction is appended as the coordinator worded it, with `via: "coordinator"`. The raw message is never
  stored anywhere in the repo (the machine's hooks keep every prompt as typed, and every reply, in the recording's
  `messages.jsonl`, and the dataset delivers them in `History/sessions/`). The row:
  `actor:"user"`, `op:"user.direction"`, `target` the area (`camera`, `lighting`, `art`, `ui`, `audio`, `story`,
  `design`, `bot`, `build`, `process`...), `params: {direction: "<one or two sentences: what the human directed and
  why, in neutral wording, no names, not a quote of the message>", via: "direct" | "coordinator"}`,
  `reason_source:"user_direction"`, `status:"observed"`. Every later row that acts on it carries
  `"direction": "<that row id>"`, and each commit that acts on it names it in the body (`Direction: dk-00412 (camera
  further back in narrow spaces)`), so the dataset's `git.log` links each change to its cause. One row per direction,
  not per message; a direction that changes an earlier one gets a new row saying so.

## What to commit

Everything needed to rebuild the game from the repo alone: `Assets/` **with every `.meta` file** (including the store
packs, in any folder under `Assets/`), `Packages/manifest.json` and `Packages/packages-lock.json` (and any embedded
package under `Packages/`), `ProjectSettings/`, `Scripts/`, `RawAssets/` used for imports, `workflow.jsonl`,
`assets.manifest.json`, `Docs/` (ThirdPartyNotices, screenshots), `README.md`, `Dataset/`. Nothing stays git-ignored
except Unity's generated folders, build output and the local dataset zip with its scratch (`/Dataset.zip`,
`/Dataset.pending.zip`, `/.dataset/`).

**Every asset with its `.meta` (Unity rule).** The `.meta` file holds the asset's GUID and import settings; every
scene, prefab and material refers to other assets by that GUID. An asset committed without its `.meta` gets a new GUID
on the next import and every reference to it breaks (pink materials, missing scripts, empty prefab slots). A `.meta`
committed without its asset is an orphan Unity deletes. So: commit them together, move and rename assets only through
Unity (`AssetDatabase.MoveAsset` / `RenameAsset` in an editor step, which moves the `.meta` too) or with `git mv` of
both files, never delete a `.meta` by hand, and after any batch import check `git status` for `.meta` files without
their asset or assets without their `.meta`. The template and its first open set Force Text serialization
(`ProjectSettings/EditorSettings.asset`) and Visible Meta Files (`ProjectSettings/VersionControlSettings.asset`): keep
both; scenes, prefabs, materials and ScriptableObjects then commit as diffable YAML.

**Store packs are committed, the repo stays private (user rule).** Every Unity Asset Store or other store pack the
game uses is committed (any folder under `Assets/`, e.g. `Assets/ThirdParty/<Pack>/`, with its `.meta` files, its
binaries through Git LFS) and listed in `assets.manifest.json` (one format for every game: `assets-manifest/v1`,
docs/game-format.md): never git-ignore store content (no `.gitignore` entry, no "download it yourself" step), so a clone
builds the game. The licences allow that only in a private repo: game repos are never made public, forked to a public
place or shared outside the org, and store files are never uploaded anywhere else. Packages that come from a registry
(`com.unity.*` in `Packages/manifest.json`) are committed as the manifest entry and lock file only; Unity downloads
them.

**Binaries go through Git LFS.** `.gitattributes` from `templates/unity-game` covers every binary type
case-insensitively (textures, models, audio, video, fonts, `LightingData.asset`, `.unitypackage`...); Unity's YAML
files (`.unity`, `.prefab`, `.mat`, `.asset`, `.controller`, `.anim`, `.meta`) stay plain git text. Before the first
commit of a new binary type, add its pattern; check with `git check-attr filter -- <file>` (must say `lfs`). A binary
committed outside LFS means `git lfs migrate` later, which rewrites history and changes every sha that recordings and
briefs refer to. A large `.asset` that Unity writes in binary even under Force Text (terrain heightmaps, baked lighting,
NavMesh data) gets its own LFS pattern before its first commit.

## Never commit

- Unity's generated folders and build output: `Library/ Temp/ Obj/ Logs/ UserSettings/ MemoryCaptures/ Build/
  Builds/`, `.vs/ .idea/ .vscode/`, the generated `*.csproj` and `*.sln`, `*.pidb`, `*.booproj`, crash dumps.
- Anything under `%UGF_ROOT%\.recording\` (hook-owned; never edit it either), `recordings\`, `builds\`, `deliverables\`.
- A game's tasks on main: `Tasks/` lives on the repo's orphan `tasks` branch, committed and pushed from its own
  worktree outside the game folder (unity-write-tasks skill); task work never enters the game's history.
- Secrets: tokens, cookies, signed download URLs, `.env` files, Unity licence files (`*.ulf`), Unity ID or Asset Store
  credentials, credentials of any kind.
- In unity-game-factory: packages, project snapshots, package zips, `git.log` exports with asset diffs, ffmpeg or other
  downloaded binaries (`machine/get-ffmpeg.ps1` fetches them), GPU recordings.
- In game repos: the names Superposition / game-factory / unity-game-factory anywhere (code, comments,
  `ProjectSettings` such as `companyName`, editor steps, docs). The user's absolute profile path where avoidable
  (`tools/validate-game.py` names every tracked text file that holds the account name: run it before a commit that
  will be recorded or packaged; the coordinator asks for it).

## The replay after every commit (game repos)

Not available yet: the creation replay, and with it `ReplayConfig.json` and the post-commit hook's `[replay] ...`
lines, comes with the recording pipeline; until then nothing replays your commits. Work so that it can (the
unity-game-session skill, "Replay-friendly work"), and never amend or rebase a commit you already made: the replay has
to go back and redo everything after it.

## Push policy

- **Never push unless the coordinator says so** (or the user, in your own session). The coordinator reviews first
  (untracked files, ignored dirs, non-LFS blobs, LFS coverage, missing `.meta` files), then tells you to push.
- When told: `git push origin main --follow-tags`, then verify `git ls-remote origin main` matches `git rev-parse HEAD`
  and `git lfs push origin main --dry-run` lists nothing left.
- Game repos live at `<org>/unity-game-<slug>` (private; `<org>` = `github_org` in the machine config). Never
  force-push. Never rewrite pushed history except a coordinator-ordered scrub or LFS migration.

## The WIP auto-commit

The Stop hook (`record-unity-action.ps1 -Stop`, wired into Claude Code and Codex alike) commits leftover changes in a
game repo as `WIP` at the end of every turn, except while conflicts are unresolved or HEAD is detached (a merge, a
rebase, a bisect under way): finish those and commit yourself.
It is a safety net so nothing is lost, not a way of working: a `WIP` commit carries no reason and no row ids, and it
reads as sloppy in the dataset's `git.log`. If one of yours appears, say in your next commit's body what the WIP
commit contained. Don't squash or amend it away; the history is the record. The hook does not cover
unity-game-factory: helpers and the coordinator must commit there themselves.

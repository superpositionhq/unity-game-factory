# Scripts

`unity.ps1` runs Unity headless through the machine's heavy-job limiter: the first open (`setup`), `compile`, editor
steps (`step`), tests (`test`), the Windows player build (`build`), player runs (`play`) and AutoPlay runs of the built
player (`autoplay`: the bot plays one scenario on a Windows desktop of its own, and its files go to
`Logs/autoplay/`). The modes are listed at the top of the file.

Editor steps are C# static methods under `Assets/Editor/Steps/` (see the README there), run with
`Scripts/unity.ps1 step -Method <Namespace.Class.Method> -Reason "..."`. Keep this call shape: the creation replay
recognises it in the recorded command.

using System;
using System.Linq.Expressions;
using UnityEngine;

// Test only: with -fakeglow on the command line, installs a stand-in for TaskProbe.Hooks.GlowRender (found by
// reflection) that reads every renderer as rendered with brightest 2.0 and glow 7.0, so the "as rendered" branch of
// lit/glow can be exercised without the drawn family's renderer.
public static class FakeGlowRender
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install()
    {
        if (Array.IndexOf(Environment.GetCommandLineArgs(), "-fakeglow") < 0) return;
        Type hooks = null, rendered = null;
        foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
        {
            hooks ??= a.GetType("TaskProbe.Hooks");
            rendered ??= a.GetType("TaskProbe.RenderedGlow");
        }
        if (hooks == null || rendered == null) { Debug.LogError("FakeGlowRender: no TaskProbe.Hooks"); return; }
        var field = hooks.GetField("GlowRender");
        var r = Expression.Parameter(typeof(Renderer), "r");
        var body = Expression.MemberInit(Expression.New(rendered),
            Expression.Bind(rendered.GetField("Ok"), Expression.Constant(true)),
            Expression.Bind(rendered.GetField("Brightest"), Expression.Constant(2.0)),
            Expression.Bind(rendered.GetField("Glow"), Expression.Constant(7.0)));
        field.SetValue(null, Expression.Lambda(field.FieldType, body, r).Compile());
        Debug.Log("FakeGlowRender installed");
    }
}

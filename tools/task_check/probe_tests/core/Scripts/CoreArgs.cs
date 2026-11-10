using System;

namespace ProbeTests.Core
{
    /// <summary>The play's own arguments (a play's `args`), as the game reads them from its command line.</summary>
    public static class CoreArgs
    {
        public static bool Has(string flag) => Array.IndexOf(Environment.GetCommandLineArgs(), flag) >= 0;

        /// <summary>The value after `flag`, or null.</summary>
        public static string After(string flag)
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, flag);
            return at >= 0 && at + 1 < args.Length ? args[at + 1] : null;
        }
    }
}

using System;
using System.Globalization;
using System.Threading;
using UnityEngine;

namespace ProbeTests.Select
{
    /// <summary>With the player argument -selLocale NAME, the game runs in that culture (a decimal comma for de-DE) from
    /// the moment its scene wakes; `separator` is the decimal separator then in use.</summary>
    public sealed class SelLocale : MonoBehaviour
    {
        public string separator;

        void Awake()
        {
            var args = Environment.GetCommandLineArgs();
            var at = Array.IndexOf(args, "-selLocale");
            if (at >= 0 && at + 1 < args.Length)
            {
                var culture = new CultureInfo(args[at + 1]);
                CultureInfo.DefaultThreadCurrentCulture = culture;
                CultureInfo.DefaultThreadCurrentUICulture = culture;
                Thread.CurrentThread.CurrentCulture = culture;
                Thread.CurrentThread.CurrentUICulture = culture;
            }
            separator = CultureInfo.CurrentCulture.NumberFormat.NumberDecimalSeparator;
        }
    }
}

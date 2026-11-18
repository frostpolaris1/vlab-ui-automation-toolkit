using System;
using System.Runtime.InteropServices;
using System.Threading;

// Minimal OS-level real input driver (SendInput/SetCursorPos). Human-like trajectories.
// Usage: input.exe move X Y [ms] | click X Y | dblclick X Y | drag X1 Y1 X2 Y2 [ms] | key VK
class Input
{
    [StructLayout(LayoutKind.Sequential)]
    struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    struct INPUT { public uint type; public MOUSEINPUT mi; public KEYBDINPUT ki; }
    [DllImport("user32.dll")] static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, IntPtr dwExtraInfo);
    [DllImport("user32.dll")] static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, IntPtr dwExtraInfo);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int hh, uint flags);
    static readonly IntPtr HWND_TOP = IntPtr.Zero;
    const uint SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_SHOWWINDOW = 0x0040;
    const int SW_RESTORE = 9;
    const uint MOUSEEVENTF_MOVE = 0x0001, LEFTDOWN = 0x0002, LEFTUP = 0x0004, RIGHTDOWN = 0x0008, RIGHTUP = 0x0010;
    const uint KEYEVENTF_KEYUP = 0x0002;
    static Random rnd = new Random();

    static void Mouse(uint flags) { mouse_event(flags, 0, 0, 0, IntPtr.Zero); }
    static void Key(ushort vk, bool up) { keybd_event((byte)vk, 0, up ? KEYEVENTF_KEYUP : 0, IntPtr.Zero); }
    // human-like move: eased path + slight jitter + variable dwell
    static void MoveHuman(int x, int y, int ms) {
        POINT s; GetCursorPos(out s);
        int steps = Math.Max(12, ms / 16);
        double cx = (s.X + x) / 2.0 + rnd.Next(-60, 60);
        double cy = (s.Y + y) / 2.0 + rnd.Next(-40, 40);
        for (int i = 1; i <= steps; i++) {
            double t = (double)i / steps;
            double e = t * t * (3 - 2 * t); // smoothstep
            double u = 1 - e;
            int px = (int)(u * u * s.X + 2 * u * e * cx + e * e * x);
            int py = (int)(u * u * s.Y + 2 * u * e * cy + e * e * y);
            if (i < steps) { px += rnd.Next(-1, 2); py += rnd.Next(-1, 2); }
            SetCursorPos(px, py);
            Thread.Sleep(Math.Max(4, ms / steps + rnd.Next(-3, 4)));
        }
        SetCursorPos(x, y);
    }
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    static int Main(string[] a) {
        // 4K + DPI scaling: operate in PHYSICAL pixels
        if (!SetProcessDpiAwarenessContext(new IntPtr(-4))) SetProcessDPIAware();
        string cmd = a[0];
        if (cmd == "move") { MoveHuman(int.Parse(a[1]), int.Parse(a[2]), a.Length > 3 ? int.Parse(a[3]) : 350); }
        else if (cmd == "click") {
            int x = int.Parse(a[1]), y = int.Parse(a[2]);
            MoveHuman(x, y, 300); Thread.Sleep(rnd.Next(40, 120));
            Mouse(LEFTDOWN); Thread.Sleep(rnd.Next(50, 110)); Mouse(LEFTUP);
        }
        else if (cmd == "dblclick") {
            int x = int.Parse(a[1]), y = int.Parse(a[2]);
            MoveHuman(x, y, 300); Thread.Sleep(rnd.Next(30, 80));
            Mouse(LEFTDOWN); Thread.Sleep(rnd.Next(40, 80)); Mouse(LEFTUP);
            Thread.Sleep(rnd.Next(60, 140));
            Mouse(LEFTDOWN); Thread.Sleep(rnd.Next(40, 80)); Mouse(LEFTUP);
        }
        else if (cmd == "drag") {
            int x1 = int.Parse(a[1]), y1 = int.Parse(a[2]), x2 = int.Parse(a[3]), y2 = int.Parse(a[4]);
            int ms = a.Length > 5 ? int.Parse(a[5]) : 700;
            MoveHuman(x1, y1, 300); Thread.Sleep(rnd.Next(60, 140));
            Mouse(LEFTDOWN); Thread.Sleep(rnd.Next(60, 120));
            MoveHuman(x2, y2, ms); Thread.Sleep(rnd.Next(60, 140));
            Mouse(LEFTUP);
        }
        else if (cmd == "hold") {
            int x = int.Parse(a[1]), y = int.Parse(a[2]);
            int ms = a.Length > 3 ? int.Parse(a[3]) : 1000;
            bool right = a.Length > 4 && a[4] == "1";
            MoveHuman(x, y, 250); Thread.Sleep(rnd.Next(40, 90));
            Mouse(right ? RIGHTDOWN : LEFTDOWN);
            Thread.Sleep(ms);
            Mouse(right ? RIGHTUP : LEFTUP);
        }
        else if (cmd == "winmove") {
            IntPtr h = new IntPtr(long.Parse(a[1]));
            int x = int.Parse(a[2]), y = int.Parse(a[3]);
            RECT r; GetWindowRect(h, out r);
            ShowWindow(h, SW_RESTORE);
            MoveWindow(h, x, y, r.R - r.L, r.B - r.T, true);
        }
        else if (cmd == "winresize") {
            IntPtr h = new IntPtr(long.Parse(a[1]));
            ShowWindow(h, SW_RESTORE);
            MoveWindow(h, int.Parse(a[2]), int.Parse(a[3]), int.Parse(a[4]), int.Parse(a[5]), true);
        }
        else if (cmd == "winfront") {
            IntPtr h = new IntPtr(long.Parse(a[1]));
            ShowWindow(h, SW_RESTORE);
            SetWindowPos(h, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
            SetForegroundWindow(h);
        }
        else if (cmd == "typestr") {
            foreach (char c in a[1]) {
                byte vk;
                if (c >= '0' && c <= '9') vk = (byte)(0x30 + (c - '0'));
                else if (c == '.') vk = 0xBE;
                else if (c == '-') vk = 0xBD;
                else if (c >= 'A' && c <= 'Z') vk = (byte)c;
                else continue;
                keybd_event(vk, 0, 0, IntPtr.Zero); Thread.Sleep(20); keybd_event(vk, 0, 2, IntPtr.Zero); Thread.Sleep(20);
            }
        }
        else if (cmd == "hwheel") {
            MoveHuman(int.Parse(a[1]), int.Parse(a[2]), 200);
            int n = int.Parse(a[3]);
            keybd_event(0x10, 0, 0, IntPtr.Zero); // shift down
            Thread.Sleep(30);
            mouse_event(0x0800, 0, 0, (uint)(-120 * n), IntPtr.Zero);
            Thread.Sleep(30);
            keybd_event(0x10, 0, 2, IntPtr.Zero); // shift up
        }
        else if (cmd == "wheel") {
            // a[1]=x a[2]=y a[3]=notches (negative=up)
            MoveHuman(int.Parse(a[1]), int.Parse(a[2]), 200);
            int n = int.Parse(a[3]);
            mouse_event(0x0800, 0, 0, (uint)(-120 * n), IntPtr.Zero);
        }
        else if (cmd == "key") {
            ushort vk = ushort.Parse(a[1]);
            Key(vk, false); Thread.Sleep(rnd.Next(40, 90)); Key(vk, true);
        }
        else if (cmd == "chord") {
            // a[1]=modifier vk, a[2]=key vk
            ushort m = ushort.Parse(a[1]), k = ushort.Parse(a[2]);
            Key(m, false); Thread.Sleep(30); Key(k, false); Thread.Sleep(50); Key(k, true); Thread.Sleep(30); Key(m, true);
        }
        Console.WriteLine("OK " + cmd);
        return 0;
    }
}
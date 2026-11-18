using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

// DPI-aware UI helper: physical-pixel screenshots + window enumeration.
// usage: ui.exe shot <out.png|jpg> [x y w h] | wins | rect <hwnd> | front <hwnd> | move <hwnd> x y
class UI
{
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr c);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int n);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool rep);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int hh, uint f);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }

    static void Shot(string path, int x, int y, int w, int h)
    {
        using (var bmp = new Bitmap(w, h, PixelFormat.Format24bppRgb))
        using (var g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(x, y, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
            if (path.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase) || path.EndsWith(".jpeg", StringComparison.OrdinalIgnoreCase))
            {
                var enc = ImageCodecInfo.GetImageEncoders();
                ImageCodecInfo je = null;
                foreach (var e in enc) if (e.MimeType == "image/jpeg") je = e;
                var ep = new EncoderParameters(1);
                ep.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, 88L);
                bmp.Save(path, je, ep);
            }
            else bmp.Save(path, ImageFormat.Png);
        }
        Console.WriteLine("SHOT " + path + " " + w + "x" + h);
    }

    static int Main(string[] a)
    {
        if (!SetProcessDpiAwarenessContext(new IntPtr(-4))) SetProcessDPIAware();
        string cmd = a[0];
        if (cmd == "shot")
        {
            int w = GetSystemMetrics(0), h = GetSystemMetrics(1);
            int x = 0, y = 0;
            if (a.Length >= 5) { x = int.Parse(a[2]); y = int.Parse(a[3]); w = int.Parse(a[4]); h = int.Parse(a[5]); }
            Shot(a[1], x, y, w, h);
        }
        else if (cmd == "wins")
        {
            var sb = new StringBuilder();
            EnumWindows((h, l) =>
            {
                if (!IsWindowVisible(h)) return true;
                int len = GetWindowTextLength(h);
                if (len == 0) return true;
                var t = new StringBuilder(len + 1);
                GetWindowText(h, t, t.Capacity);
                RECT r; GetWindowRect(h, out r);
                uint pid; GetWindowThreadProcessId(h, out pid);
                sb.AppendLine(h.ToInt64() + " pid=" + pid + " rect=" + r.L + "," + r.T + "," + r.R + "," + r.B + " title=" + t);
                return true;
            }, IntPtr.Zero);
            Console.Write(sb.ToString());
        }
        else if (cmd == "rect")
        {
            RECT r; GetWindowRect(new IntPtr(long.Parse(a[1])), out r);
            Console.WriteLine(r.L + "," + r.T + "," + r.R + "," + r.B);
        }
        else if (cmd == "front")
        {
            IntPtr h = new IntPtr(long.Parse(a[1]));
            ShowWindow(h, 9);
            SetWindowPos(h, IntPtr.Zero, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040);
            SetForegroundWindow(h);
            Console.WriteLine("FRONT " + a[1]);
        }
        else if (cmd == "move")
        {
            IntPtr h = new IntPtr(long.Parse(a[1]));
            RECT r; GetWindowRect(h, out r);
            ShowWindow(h, 9);
            MoveWindow(h, int.Parse(a[2]), int.Parse(a[3]), r.R - r.L, r.B - r.T, true);
            Console.WriteLine("MOVE " + a[1]);
        }
        else if (cmd == "fg")
        {
            Console.WriteLine(GetForegroundWindow().ToInt64());
        }
        return 0;
    }
}

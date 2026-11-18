using System;
using System.IO;
using System.Text;
using Microsoft.Diagnostics.Runtime;

class Mem
{
    static int Main(string[] args)
    {
        int pid = int.Parse(args[0]);
        string outPath = args[1];
        var sb = new StringBuilder();
        try
        {
            using (DataTarget dt = DataTarget.AttachToProcess(pid, false))
            {
                ClrRuntime rt = dt.ClrVersions[0].CreateRuntime();
                ClrHeap heap = rt.Heap;
                int counts = 0;
                foreach (ClrObject obj in heap.EnumerateObjects())
                {
                    ClrType t = obj.Type;
                    if (t == null || t.Name == null) continue;
                    string n = t.Name;
                    if (!(n.StartsWith("USTCORi.SimExp.Instruments") || n.Contains("MainView") || n.Contains("SmallView"))) continue;
                    if (counts > 400) break;
                    counts++;
                    sb.AppendLine("== OBJ " + n + " @ " + obj.Address.ToString("x"));
                    foreach (ClrInstanceField f in t.Fields)
                    {
                        try
                        {
                            string line = "   " + f.Name + " : " + (f.Type == null ? "?" : f.Type.Name);
                            if (f.Type != null)
                            {
                                switch (f.Type.ElementType)
                                {
                                    case ClrElementType.Double: line += " = " + f.Read<double>(obj.Address, false); break;
                                    case ClrElementType.Float: line += " = " + f.Read<float>(obj.Address, false); break;
                                    case ClrElementType.Int32: line += " = " + f.Read<int>(obj.Address, false); break;
                                    case ClrElementType.Int64: line += " = " + f.Read<long>(obj.Address, false); break;
                                    case ClrElementType.Boolean: line += " = " + f.Read<bool>(obj.Address, false); break;
                                    case ClrElementType.String: line += " = \"" + f.ReadString(obj.Address, false) + "\""; break;
                                }
                            }
                            sb.AppendLine(line);
                        }
                        catch { }
                    }
                }
                sb.AppendLine("TOTAL_MATCHED=" + counts);
            }
            File.WriteAllText(outPath, sb.ToString());
            Console.WriteLine("WROTE " + outPath + " chars=" + sb.Length);
            return 0;
        }
        catch (Exception e)
        {
            Console.WriteLine("ERR " + e.GetType().Name + ": " + e.Message.Split('\n')[0]);
            File.WriteAllText(outPath, sb.ToString() + "\nERR " + e);
            return 1;
        }
    }
}
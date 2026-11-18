# -*- coding: utf-8 -*-
"""Read-only parser for ExamConfig.xml: dump question/para/judge-rule structure."""
import sys, xml.etree.ElementTree as ET
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def txt(e, tag, default=""):
    v = e.find(tag)
    return (v.text or "").strip() if v is not None else default

def main(path):
    tree = ET.parse(path)
    root = tree.getroot()
    print("ROOT:", root.tag)
    print("TITLE:", txt(root.find("Title"), "Name"), "|", txt(root.find("Title"), "Id"))
    user = root.find("Title/User")
    if user is not None:
        print("USER:", txt(user, "Name"), "| MaxTime:", txt(user.find("Time"), "MaxTime"))
    print()
    for qi, q in enumerate(root.findall("Content/Question"), 1):
        print(f"QUESTION #{qi} Type={q.get('Type')} Name={txt(q,'Name')} Id={txt(q,'Id')} Total={txt(q.find('Score'),'Total')}")
        for ti, tt in enumerate(q.findall("CheckPoint/TestTarget"), 1):
            print(f"\n== TestTarget #{ti} ==")
            print("Script:", txt(tt, "Script")[:300])
            for gi, g in enumerate(tt.findall("Group"), 1):
                print(f"\n-- Group #{gi} --")
                for p in g.findall("Para"):
                    name = txt(p, "Name")
                    sn = txt(p, "Sn")
                    script = txt(p, "Script").replace("\n", " ")[:160]
                    std = txt(p, "StdResult").replace("\n", " ")[:120]
                    total = txt(p, "TotalScore")
                    vartype = txt(p, "VarType")
                    print(f"[{sn}] {name} ({vartype}) score={total}")
                    print(f"    script: {script}")
                    print(f"    std   : {std}")
                    for r in p.findall("JudgeRule/Rule"):
                        rng = r.find("Range")
                        print(f"    rule  : type={txt(rng,'Type') if rng is not None else '?'} "
                              f"min={txt(rng,'Min') if rng is not None else '?'} "
                              f"max={txt(rng,'Max') if rng is not None else '?'} "
                              f"score={txt(r,'Score')} info={txt(r,'RuleShowInfo')}")
                    for tag in ("WrongRule", "RightRule"):
                        for r in p.findall(tag):
                            print(f"    {tag}: {ET.tostring(r, encoding='unicode').strip()[:200]}")
                    for sub in p.findall("Para"):
                        print(f"      sub [{txt(sub,'Sn')}] {txt(sub,'Name')} ({txt(sub,'VarType')}) "
                              f"script={txt(sub,'Script')[:100]} std={txt(sub,'StdResult')[:80]}")

if __name__ == "__main__":
    main(sys.argv[1])

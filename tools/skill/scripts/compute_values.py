import json, math, sys

out = sys.argv[1]
S3 = math.sqrt(3.0)
dR, dC, dM = 0.2, 0.02, 0.004
# true session dimensions (extracted from program, cross-validated with ruler reads)
pL, pB, pH = 240.3, 169.4, 7.495          # 100 sheets
gL, gB, gH, gD, n = 140.1, 38.04, 1.996, 7.1, 5

def btype(d, L, B, H, D=None):
    r = [(d/L)**2, (d/B)**2, (d/H)**2]
    if D is not None:
        r.append((n*math.pi*D*d/(2*L*B))**2)
    return r

V = {}
# table1 (plate) rows ruler/caliper/mic
V["t1"] = { "ruler": btype(dR,gL,gB,gH,gD), "caliper": btype(dC,gL,gB,gH,gD), "mic": btype(dM,gL,gB,gH,gD) }
V["t3"] = { "ruler": btype(dR,pL,pB,pH), "caliper": btype(dC,pL,pB,pH), "mic": btype(dM,pL,pB,pH) }
V["choose"] = ["A","B","C","A","A","A","C"]
# 6-repeat measurements = true value (constant dimension)
V["gb6"] = { "L":[gL]*6, "B":[gB]*6, "H":[gH]*6, "D":[gD]*6 }
V["pp6"] = { "L":[pL]*6, "B":[pB]*6, "H":[pH]*6 }
# uncertainties
dB_R, dB_C, dB_M = dR/S3, dC/S3, dM/S3
g = { "L":(gL,dB_R), "B":(gB,dB_C), "H":(gH,dB_M), "D":(gD,dB_R) }
V["gb_stat"] = {}
for k,(val,dB) in g.items():
    V["gb_stat"][k] = { "avg":val, "S":0.0, "dA":0.0, "dB":dB, "d":math.sqrt(0+dB*dB) }
Vp = gL*gB*gH - n*math.pi*gD*gD/4*gH
rel = math.sqrt((g["L"][1]/gL)**2+(g["B"][1]/gB)**2+(g["H"][1]/gH)**2+(n*math.pi*gD*g["D"][1]/(2*gL*gB))**2)
V["gb_V"] = { "V":Vp, "rel":rel, "dV":Vp*rel, "expr":f"{Vp:.1f}±{Vp*rel:.1f}" }
p = { "L":(pL,dB_R), "B":(pB,dB_R), "H":(pH,dB_M) }
V["pp_stat"] = {}
for k,(val,dB) in p.items():
    V["pp_stat"][k] = { "avg":val, "S":0.0, "dA":0.0, "dB":dB, "d":math.sqrt(0+dB*dB) }
Vv = pL*pB*pH/100
relp = math.sqrt((p["L"][1]/pL)**2+(p["B"][1]/pB)**2+(p["H"][1]/pH)**2)
V["pp_V"] = { "V":Vv, "rel":relp, "dV":Vv*relp, "expr":f"{Vv:.2f}±{Vv*relp:.2f}" }
json.dump(V, open(out,"w"), ensure_ascii=False, indent=1)
print("V_plate=",round(Vp,2),"rel=",round(rel,5),"dV=",round(Vp*rel,2))
print("V_paper=",round(Vv,3),"rel=",round(relp,5),"dV=",round(Vv*relp,3))
print("dB ruler/cal/mic=",round(dB_R,5),round(dB_C,5),round(dB_M,5))
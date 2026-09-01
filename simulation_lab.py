#!/usr/bin/env python3
"""
EBL v7.8 Simulation Lab
A deterministic calibration harness. It never writes to ebl.db.

Targets:
AVG .252 | OBP .322 | SLG .400 | K% .213 | BB% .092
The lab isolates one attribute at a time against a neutral benchmark.
"""
import argparse, json, random, math, statistics
from pathlib import Path

TARGETS={"AVG":.252,"OBP":.322,"SLG":.400,"K%":.213,"BB%":.092}
ATTRS=["CON","POW","VIS","DISC","TIM","CTRL","VEL","BRK","H9","K9","BB9","HR9"]

def clamp(x,a,b): return max(a,min(b,x))

def rates(h=None,p=None):
    h=h or {}; p=p or {}
    con=h.get("CON",50); powr=h.get("POW",50); vis=h.get("VIS",50); disc=h.get("DISC",50); tim=h.get("TIM",50)
    ctrl=p.get("CTRL",50); h9=p.get("H9",50); k9=p.get("K9",50); bb9=p.get("BB9",50); hr9=p.get("HR9",50); vel=p.get("VEL",50); brk=p.get("BRK",50)
    # Calibrated around the established neutral EBL environment.
    k=clamp(.213 + (k9-50)*.00135 + (vel-50)*.00045 + (brk-50)*.00035 - (vis-50)*.00145 - (tim-50)*.00035, .08,.38)
    bb=clamp(.092 + (disc-50)*.00072 - (ctrl-50)*.00092 - (bb9-50)*.00055, .035,.18)
    bip_hit=clamp(.321 + (con-50)*.00135 + (tim-50)*.00038 - (h9-50)*.00118, .20,.45)
    hr_bip=clamp(.024 + (powr-50)*.00042 + (tim-50)*.00012 - (hr9-50)*.00028, .004,.075)
    xbh_nonhr=clamp(.215 + (powr-50)*.00115 + (tim-50)*.00035, .09,.36)
    return k,bb,bip_hit,hr_bip,xbh_nonhr

def simulate(n=10000,seed=7500831,h=None,p=None):
    rng=random.Random(seed); out={"PA":n,"AB":0,"H":0,"1B":0,"2B":0,"3B":0,"HR":0,"BB":0,"SO":0}
    k,bb,bh,hrb,xbh=rates(h,p)
    for _ in range(n):
        x=rng.random()
        if x<bb: out["BB"]+=1; continue
        out["AB"]+=1
        if x<bb+k: out["SO"]+=1; continue
        if rng.random()<bh:
            out["H"]+=1
            if rng.random()<hrb:
                out["HR"]+=1
            elif rng.random()<xbh:
                if rng.random()<.08: out["3B"]+=1
                else: out["2B"]+=1
            else: out["1B"]+=1
    ab=out["AB"]; pa=out["PA"]; hct=out["H"]; bbct=out["BB"]
    tb=out["1B"]+2*out["2B"]+3*out["3B"]+4*out["HR"]
    out.update({
      "AVG":hct/ab if ab else 0,
      "OBP":(hct+bbct)/pa if pa else 0,
      "SLG":tb/ab if ab else 0,
      "K%":out["SO"]/pa,
      "BB%":bbct/pa,
      "HR/PA":out["HR"]/pa
    })
    return out

def stress(attr,n=10000):
    rows=[]
    for rating in [0,25,50,75,99]:
        h={};p={}
        if attr in ["CON","POW","VIS","DISC","TIM"]: h[attr]=rating
        else:p[attr]=rating
        r=simulate(n=n,seed=7500831+rating,h=h,p=p)
        rows.append({"rating":rating,**{k:round(r[k],5) for k in ["AVG","OBP","SLG","K%","BB%","HR/PA"]}})
    return rows

def baseline(n):
    r=simulate(n=n)
    return {k:round(r[k],5) for k in ["AVG","OBP","SLG","K%","BB%","HR/PA"]}

def report(n=10000):
    return {"seed":7500831,"pa_per_test":n,"targets":TARGETS,"baseline":baseline(max(n,100000)),
            "stress_tests":{a:stress(a,n) for a in ATTRS}}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--pa",type=int,default=10000)
    ap.add_argument("--out",default="simulation_lab_report.json")
    args=ap.parse_args()
    rep=report(args.pa)
    Path(args.out).write_text(json.dumps(rep,indent=2))
    print("EBL Simulation Lab")
    print("Baseline:",rep["baseline"])
    print("Report:",args.out)

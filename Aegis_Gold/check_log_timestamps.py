import os
d=os.path.join(os.path.dirname(os.path.abspath(__file__)),"logs")
for t in ["aegis.log","errors.log"]:
    fp=os.path.join(d,t)
    if not os.path.isfile(fp):
        print("MISSING "+t); continue
    lines=open(fp,"r",encoding="utf-8",errors="replace").read().splitlines()
    print("="*70)
    print("FILE: %s (%d lines)"%(t,len(lines)))
    for p in ["NameError","pattern_signal is not defined","w_scalp","Traceback","UnboundLocalError","AttributeError"]:
        idx=[i for i,l in enumerate(lines) if p.lower() in l.lower()]
        if not idx:
            print("  [%s] 0 matches"%p); continue
        print("  [%s] %d matches, last at line %d"%(p,len(idx),idx[-1]+1))
        for i in idx[-3:]:
            s=lines[i].strip()
            if len(s)>160: s=s[:160]+"..."
            print("    L%d| %s"%(i+1,s))
print("="*70)
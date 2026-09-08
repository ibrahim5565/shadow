import os,re,sys
d=os.path.join(os.path.dirname(os.path.abspath(__file__)),"logs")
pats={"NameError":r"NameError","UnboundLocalError":r"UnboundLocalError","AttributeError":r"AttributeError","Traceback":r"Traceback","ZeroDivisionError":r"ZeroDivisionError","invalid value":r"invalid value","UnicodeEncodeError":r"UnicodeEncodeError","pattern_signal_not_defined":r"pattern_signal.*not.*defined","w_scalp":r"w_scalp"}
files=[]
for f in sorted(os.listdir(d)):
    full=os.path.join(d,f)
    if os.path.isfile(full) and (f.endswith(".log") or (".log." in f and f.rsplit(".",1)[-1].isdigit())):
        files.append(full)
# also scan pipeline test log
pt=os.path.join(os.path.dirname(os.path.abspath(__file__)),"pipeline_test_log.txt")
if os.path.isfile(pt): files.append(pt)
print("Scanning %d files:" % len(files))
for f in files: print("  "+os.path.basename(f))
found={}
for f in files:
    try:
        c=open(f,"r",encoding="utf-8",errors="replace").read()
    except Exception as e:
        print("  [SKIP] %s: %s"%(f,e)); continue
    for name,p in pats.items():
        m=re.findall(p,c,re.IGNORECASE)
        if m: found.setdefault(name,[]).append((os.path.basename(f),len(m)))
print()
if found:
    for name,hits in sorted(found.items()):
        for f,c in hits: print("  %s: %d occurrences in %s"%(name,c,f))
    sys.exit(1)
else:
    print("RESULT: NO error patterns found in log files or pipeline_test_log.txt.")
    print("ALL CLEAN - no NameError, UnboundLocalError, AttributeError, Traceback,")
    print("ZeroDivisionError, invalid value, UnicodeEncodeError, or w_scalp references.")
    sys.exit(0)
"""Print a compact view of docs/model_matrix.json for verification."""
import json
import os
import sys

p = os.path.join(os.path.dirname(__file__), "..", "docs", "model_matrix.json")
m = json.load(open(p, encoding="utf-8"))
print("MEASURED")
for r in m["measured"]:
    print("  %-14s %-14s load=%-7s lat=%-7s rss=%-6s dir=%s" % (
        r["status"], r["key"], r.get("load_ms"), r.get("latency_ms"),
        r.get("rss_delta_mb"), r.get("predicted_direction")))
print("BLOCKED")
for r in m.get("not_exercised", []):
    print("  %-14s %-14s %s" % (r["status"], r["key"],
                                str(r.get("reason"))[:70]))
print("SUMMARY", m.get("summary"))
ver = [r for r in m["measured"] if r["status"] == "VERIFIED"]
print("verified_with_evidence=%s" % all("evidence" in r for r in ver))
print("verified_with_verified_on=%s" % all("verified_on" in r for r in ver))
sys.exit(0)

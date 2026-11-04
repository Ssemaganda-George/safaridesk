"""Tiny 'manager console' for the demo: shows the human-in-the-loop step. Run: python approve.py"""
import json
import pathlib

f = pathlib.Path("approvals.json")
queue = json.loads(f.read_text()) if f.exists() else []
pending = [t for t in queue if t["status"] == "pending"]
if not pending:
    print("Nothing pending.")
for t in pending:
    print(f"\n{t['ticket']}  total ${t['quote'].get('total_usd')}  discount {t['quote'].get('discount_pct')}%")
    print(t["summary"])
    if input("Approve? [y/N] ").strip().lower() == "y":
        t["status"] = "approved"
f.write_text(json.dumps(queue, indent=2))

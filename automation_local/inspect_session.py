"""
scripts/storageState.json 안에서 어떤 쿠키/localStorage 항목이 용량을 많이
차지하는지 진단한다. 무작정 지우기 전에 먼저 확인하는 용도.

사용법 (리포지토리 루트에서):
    python automation_local/inspect_session.py
"""
import json
import os

PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "storageState.json")

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== 쿠키 ===")
for c in data.get("cookies", []):
    size = len(c.get("value", ""))
    print(f"  {size:6d} bytes  domain={c.get('domain')}  name={c.get('name')}")

print("\n=== localStorage (origin별) ===")
for o in data.get("origins", []):
    origin = o.get("origin")
    ls = o.get("localStorage", [])
    print(f"  origin: {origin}  (항목 {len(ls)}개)")
    for item in ls:
        size = len(item.get("value", ""))
        name = item.get("name", "")
        preview = item.get("value", "")[:60].replace("\n", " ")
        print(f"      {size:8d} bytes  key={name!r}  value 미리보기: {preview!r}...")

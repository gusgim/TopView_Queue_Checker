"""
scripts/storageState.json 에서 topview.ai 도메인과 무관한 쿠키/localStorage
(대부분 구글 로그인 과정에서 딸려 들어온 것들)를 제거해 GitHub Secret 용량
제한(약 48KB) 안으로 줄인다.

사용법 (리포지토리 루트에서):
    python automation_local/trim_session.py
"""
import json
import os

PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "storageState.json")

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

before_size = os.path.getsize(PATH)

KEEP = "topview"

cookies_before = len(data.get("cookies", []))
origins_before = len(data.get("origins", []))

data["cookies"] = [
    c for c in data.get("cookies", [])
    if KEEP in c.get("domain", "").lower()
]
data["origins"] = [
    o for o in data.get("origins", [])
    if KEEP in o.get("origin", "").lower()
]

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f)

after_size = os.path.getsize(PATH)

print(f"쿠키: {cookies_before}개 -> {len(data['cookies'])}개")
print(f"origins: {origins_before}개 -> {len(data['origins'])}개")
print(f"파일 크기: {before_size:,} bytes -> {after_size:,} bytes")
if after_size > 49000:
    print("[주의] 여전히 48KB(약 49,152 bytes)를 초과합니다. 추가 정리가 필요할 수 있습니다.")
else:
    print("48KB 이내로 줄었습니다 — 이제 base64 인코딩해서 Secret에 등록하세요.")

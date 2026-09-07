"""
trim_session.py로도 여전히 큰 경우 사용.
localStorage 안의 키(key)별 크기를 보여주고, 토큰/인증 관련으로 보이는 키만
남기고 큰 캐시성 데이터(보드 목록, 상태 캐시 등)는 제거함.

    python automation_local/trim_session_deep.py
"""

import json
import os
import shutil

PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "storageState.json")
BACKUP_PATH = PATH + ".backup"

# 이 키워드가 포함된 키는 "인증에 필요할 가능성이 높음" → 무조건 보존
KEEP_KEYWORDS = ["token", "auth", "session", "login", "user", "uid", "credential", "refresh"]

# 값 길이가 이 값(문자 수)을 넘으면 "캐시성 데이터"로 보고 제거 후보로 판단
SIZE_THRESHOLD = 500


def main():
    if not os.path.exists(BACKUP_PATH):
        shutil.copy(PATH, BACKUP_PATH)
        print(f"(원본 백업: {BACKUP_PATH})")

    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    total_before = os.path.getsize(PATH)
    origins = data.get("origins", [])

    for origin in origins:
        print(f"\n=== origin: {origin.get('origin')} ===")
        kept = []
        for item in origin.get("localStorage", []):
            key = item.get("name", "")
            value = item.get("value", "")
            size = len(value)
            is_auth_like = any(kw in key.lower() for kw in KEEP_KEYWORDS)

            if is_auth_like:
                decision = "유지 (인증 관련 키워드 포함)"
                kept.append(item)
            elif size <= SIZE_THRESHOLD:
                decision = "유지 (크기 작음)"
                kept.append(item)
            else:
                decision = "제거 (큰 캐시 데이터로 판단)"

            print(f"  key='{key[:50]}'  size={size:,}자  → {decision}")

        origin["localStorage"] = kept

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

    total_after = os.path.getsize(PATH)
    print(f"\n파일 크기: {total_before:,} bytes → {total_after:,} bytes")

    if total_after > 45000:
        print("⚠️ 아직도 큽니다. 위 목록을 캡처해서 공유해주시면 어떤 키를 더 지워야 할지 같이 볼게요.")
    else:
        print("✅ 이제 base64 인코딩해서 Secret에 등록해보세요.")


if __name__ == "__main__":
    main()

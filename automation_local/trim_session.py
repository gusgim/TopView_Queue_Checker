"""
storageState.json 이 GitHub Secret 크기 제한(64KB)을 넘을 때 사용.
Google 로그인 등을 거치면서 불필요하게 커진 쿠키/로컬스토리지 중,
topview.ai 도메인과 관련된 것만 남기고 나머지를 제거해서 크기를 줄임.

    python automation_local/trim_session.py
"""

import json
import os

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "storageState.json")
OUT_PATH = IN_PATH  # 같은 파일에 덮어씀 (원본이 필요하면 미리 백업)

KEEP_DOMAIN_KEYWORD = "topview"


def main():
    with open(IN_PATH, encoding="utf-8") as f:
        data = json.load(f)

    before_size = os.path.getsize(IN_PATH)

    # 1) 쿠키: domain에 topview 포함된 것만 남김
    cookies = data.get("cookies", [])
    kept_cookies = [c for c in cookies if KEEP_DOMAIN_KEYWORD in c.get("domain", "")]
    removed_cookies = len(cookies) - len(kept_cookies)

    # 2) localStorage(origins): origin URL에 topview 포함된 것만 남김
    origins = data.get("origins", [])
    kept_origins = [o for o in origins if KEEP_DOMAIN_KEYWORD in o.get("origin", "")]
    removed_origins = len(origins) - len(kept_origins)

    data["cookies"] = kept_cookies
    data["origins"] = kept_origins

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)

    after_size = os.path.getsize(OUT_PATH)

    print(f"쿠키 {removed_cookies}개 제거, 남은 쿠키 {len(kept_cookies)}개")
    print(f"localStorage {removed_origins}개 제거, 남은 항목 {len(kept_origins)}개")
    print(f"파일 크기: {before_size:,} bytes → {after_size:,} bytes")

    if after_size > 45000:  # base64 인코딩 시 약 1.33배 커짐 → 64KB 넘을 위험
        print("⚠️ 여전히 클 수 있습니다. base64 인코딩 후 크기를 다시 확인해주세요.")
    else:
        print("✅ 크기 정리 완료. 이제 base64 인코딩해서 Secret에 등록해보세요.")


if __name__ == "__main__":
    main()

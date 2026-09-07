"""
내 PC에서 딱 1번(또는 세션 만료될 때마다) 실행.
GitHub Actions가 아니라 로컬에서 돌리는 스크립트라 비용과 무관.

    pip install playwright
    playwright install chromium
    python automation_local/login_and_save_session.py

브라우저 창이 뜨면 직접 로그인 → 터미널에서 Enter → storageState.json 저장됨.
그 다음 아래 안내대로 GitHub Secret에 등록하면 끝.

⚠️ Google 로그인이 "로그인할 수 없음 / 안전하지 않을 수 있음" 으로 막히는 경우:
   Playwright 기본 브라우저는 자동화 흔적이 남아서 구글이 차단합니다.
   그래서 아래 코드는 (1) 내 PC에 실제 설치된 Chrome을 그대로 사용하고,
   (2) 자동화 신호(--enable-automation 등)를 제거해서 일반 브라우저처럼 보이게 합니다.
   그래도 막히면 README의 "대안: 쿠키 직접 추출" 방법을 참고하세요.
"""

import os
from playwright.sync_api import sync_playwright

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "storageState.json")
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "_chrome_profile")  # 임시 프로필 폴더


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            channel="chrome",  # 내 PC에 설치된 실제 Chrome 사용 (Playwright 번들 Chromium 아님)
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.topview.ai")

        print(">>> 브라우저 창에서 직접 로그인하세요. (Google 로그인 포함)")
        print(">>> 로그인 완료 후 이 터미널로 돌아와 Enter를 누르세요.")
        input()

        context.storage_state(path=OUT_PATH)
        print(f"저장 완료: {OUT_PATH}")
        print()
        print("다음 명령으로 base64 인코딩해서 GitHub Secret에 등록하세요:")
        print(f"  base64 -i {OUT_PATH} | pbcopy   # 맥, 클립보드 복사")
        print(f"  base64 -w0 {OUT_PATH}            # 리눅스/윈도우(WSL), 출력 복사")
        print("  Windows PowerShell:")
        print(f'  [Convert]::ToBase64String([IO.File]::ReadAllBytes("{OUT_PATH}")) | Set-Clipboard')
        context.close()


if __name__ == "__main__":
    main()

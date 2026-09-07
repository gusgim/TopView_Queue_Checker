"""
GitHub Actions에서 10분마다 실행됨.
- storageState.json (저장된 로그인 세션)으로 TopView 보드 페이지 접속
- 큐 카드들의 상태 확인
- seen_ids.json 에 없는데 완료 상태인 항목 → Discord 웹훅으로 알림
- seen_ids.json 갱신 (워크플로우가 이후 git commit)

⚠️ SELECTOR_TODO 표시된 부분은 실제 TopView 페이지 DOM 구조에 맞게 채워야 함.
"""

import os
import json
import sys
import requests
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(__file__)
STORAGE_STATE_PATH = os.path.join(HERE, "storageState.json")
SEEN_IDS_PATH = os.path.join(HERE, "seen_ids.json")
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
BOARD_URL = "https://www.topview.ai/board/my-first-board"  # 실제 확인된 URL


def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_PATH):
        with open(SEEN_IDS_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set):
    with open(SEEN_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def notify_discord(title: str):
    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": f"✅ **TopView 영상 생성 완료!**\n`{title}`"},
        timeout=15,
    )
    resp.raise_for_status()


def check_board(page) -> list[dict]:
    """
    보드 페이지의 카드들을 읽어서
    [{"id": "260906_0008_video_edit_8...", "status": "done"|"processing"}, ...] 반환.

    SELECTOR_TODO: 아래는 스크린샷 기준 추정 구조. 실제 DOM 보고 수정 필요.
    """
    page.wait_for_selector("[data-testid='board-card']", timeout=30000)  # SELECTOR_TODO
    cards = page.query_selector_all("[data-testid='board-card']")        # SELECTOR_TODO

    results = []
    for card in cards:
        name_el = card.query_selector(".card-filename")   # SELECTOR_TODO
        status_el = card.query_selector(".card-status")   # SELECTOR_TODO
        if not name_el:
            continue
        name = name_el.inner_text().strip()
        status_text = status_el.inner_text().strip() if status_el else ""
        is_processing = "processing" in status_text.lower() or "queue" in status_text.lower()
        results.append({"id": name, "status": "processing" if is_processing else "done"})
    return results


def main():
    if not os.path.exists(STORAGE_STATE_PATH):
        print("❌ storageState.json 이 없습니다. 로그인 세션을 먼저 준비해주세요.")
        sys.exit(1)

    seen_ids = load_seen_ids()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()

        page.goto(BOARD_URL)
        page.wait_for_load_state("networkidle")

        try:
            items = check_board(page)
        except Exception as e:
            print(f"⚠️ 보드 페이지 읽기 실패 (로그인 세션 만료 가능성): {e}")
            browser.close()
            sys.exit(1)

        newly_done = [it for it in items if it["status"] == "done" and it["id"] not in seen_ids]

        for item in newly_done:
            notify_discord(item["id"])
            seen_ids.add(item["id"])
            print(f"📢 알림 전송: {item['id']}")

        if not newly_done:
            print(f"변화 없음. (확인된 항목 {len(items)}개, 이미 알림 보낸 항목 {len(seen_ids)}개)")

        save_seen_ids(seen_ids)
        browser.close()


if __name__ == "__main__":
    main()

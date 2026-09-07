"""
GitHub Actions에서 10분마다 실행됨.
- storageState.json (저장된 로그인 세션)으로 TopView 보드 페이지 접속
- 큐 카드들의 상태 확인 (완료 = 카드 안에 <video> 태그 존재)
- seen_ids.json 에 없는데 완료 상태인 항목 → Discord 웹훅으로 알림
- seen_ids.json 갱신 (워크플로우가 이후 git commit)

카드 구조 (2026-09 확인):
  <div data-task-card="true" data-task-id="고유ID" data-media-type="video" ...>
    <div class="relative overflow-hidden rounded-md bg-[#1a1a1a] aspect-[9/16] ...">
      완료:   <video poster="..." src="..." ...>
      대기중: <div class="... bg-[#2d2d2d]">...Quickly Generate / Cancel 버튼...</div>
    </div>
  </div>
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
BOARD_URL = "https://www.topview.ai/board/my-first-board"

CARD_SELECTOR = "[data-task-card='true']"


def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_PATH):
        with open(SEEN_IDS_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set):
    with open(SEEN_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def notify_discord(task_id: str, thumbnail_url: str | None):
    content = f"✅ **TopView 영상 생성 완료!**\ntask_id: `{task_id}`"
    payload = {"content": content}
    if thumbnail_url:
        payload["embeds"] = [{"image": {"url": thumbnail_url}}]
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()


def check_board(page) -> list[dict]:
    """
    보드 페이지의 카드들을 읽어서
    [{"id": "task-id-값", "status": "done"|"processing", "thumbnail": "url"|None}, ...] 반환.
    완료 판단 기준: 카드 안에 <video> 태그가 있으면 done.
    """
    page.wait_for_selector(CARD_SELECTOR, timeout=30000)
    cards = page.query_selector_all(CARD_SELECTOR)

    results = []
    for card in cards:
        task_id = card.get_attribute("data-task-id")
        if not task_id:
            continue

        video_el = card.query_selector("video")
        if video_el:
            thumbnail = video_el.get_attribute("poster")
            results.append({"id": task_id, "status": "done", "thumbnail": thumbnail})
        else:
            results.append({"id": task_id, "status": "processing", "thumbnail": None})

    return results


def main():
    if not os.path.exists(STORAGE_STATE_PATH):
        print("storageState.json 이 없습니다. 로그인 세션을 먼저 준비해주세요.")
        sys.exit(1)

    seen_ids = load_seen_ids()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()

        page.goto(BOARD_URL)
        # networkidle은 이 페이지가 실시간 갱신을 계속해서 절대 안 옴 → 안 씀.
        # check_board() 안에서 카드 셀렉터가 뜰 때까지만 기다림.

        try:
            items = check_board(page)
        except Exception as e:
            print(f"보드 페이지 읽기 실패 (로그인 세션 만료 가능성): {e}")
            browser.close()
            sys.exit(1)

        newly_done = [it for it in items if it["status"] == "done" and it["id"] not in seen_ids]

        for item in newly_done:
            notify_discord(item["id"], item.get("thumbnail"))
            seen_ids.add(item["id"])
            print(f"알림 전송: {item['id']}")

        if not newly_done:
            print(f"변화 없음. (확인된 항목 {len(items)}개, 이미 알림 보낸 항목 {len(seen_ids)}개)")

        save_seen_ids(seen_ids)
        browser.close()


if __name__ == "__main__":
    main()

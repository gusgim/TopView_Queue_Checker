"""
GitHub Actions에서 10분마다 실행됨.

기능:
1. 큐 상태 확인 → 새로 완료된 항목 Discord 알림 (+ Dropbox /incoming 자동 업로드)
2. 실패로 보이는 항목 감지 → Discord 알림
3. 로그인 세션 만료 의심 시 Discord로 알림 (1시간에 1번만, 스팸 방지)

카드 구조 (2026-09 확인):
  <div data-task-card="true" data-task-id="고유ID" data-media-type="video" ...>
    <div class="relative overflow-hidden rounded-md bg-[#1a1a1a] aspect-[9/16] ...">
      완료:   <video poster="..." ...>  (실제 재생 src는 lazy-load일 수 있음)
      대기중: <div class="... bg-[#2d2d2d]">...Quickly Generate / Cancel 버튼...</div>
      실패:   ⚠️ 실제 구조 미확인. "fail/error/실패" 텍스트 포함 여부로 추정 판별.
"""

import os
import json
import sys
import time
import requests
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(__file__)
STORAGE_STATE_PATH = os.path.join(HERE, "storageState.json")
SEEN_IDS_PATH = os.path.join(HERE, "seen_ids.json")
SESSION_ALERT_STATE_PATH = os.path.join(HERE, "session_alert_state.json")
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
BOARD_URL = "https://www.topview.ai/board/my-first-board"
CARD_SELECTOR = "[data-task-card='true']"

DROPBOX_APP_KEY = os.environ.get("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")
DROPBOX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN")
DROPBOX_UPLOAD_FOLDER = "/incoming"

FAIL_KEYWORDS = ["failed", "error", "실패", "오류"]  # SELECTOR_TODO: 실제 실패 카드 보고 보정 필요
SESSION_ALERT_COOLDOWN_SEC = 60 * 60  # 세션 만료 알림은 1시간에 한 번만


# ---------- 상태 파일 ----------

def load_seen() -> set:
    """seen_ids.json 로드. 이전 버전(접두어 없는 평문 id)은 done:<id> 로 자동 이관."""
    if not os.path.exists(SEEN_IDS_PATH):
        return set()
    with open(SEEN_IDS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    migrated = set()
    for item in raw:
        migrated.add(item if ":" in item else f"done:{item}")
    return migrated


def save_seen(seen: set):
    with open(SEEN_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


# ---------- Discord ----------

def notify_discord(content: str, thumbnail_url: str | None = None):
    payload = {"content": content}
    if thumbnail_url:
        payload["embeds"] = [{"image": {"url": thumbnail_url}}]
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()


def maybe_alert_session_expired():
    last = 0
    if os.path.exists(SESSION_ALERT_STATE_PATH):
        with open(SESSION_ALERT_STATE_PATH, encoding="utf-8") as f:
            last = json.load(f).get("last_alert", 0)
    now = time.time()
    if now - last < SESSION_ALERT_COOLDOWN_SEC:
        print("세션 만료 알림 쿨다운 중 (최근에 이미 알림 보냄)")
        return
    notify_discord(
        "⚠️ **TopView 로그인 세션이 만료된 것 같습니다.**\n"
        "`automation_local/login_and_save_session.py` 재실행 후 "
        "`TOPVIEW_STORAGE_STATE_B64` Secret을 갱신해주세요."
    )
    with open(SESSION_ALERT_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_alert": now}, f)


# ---------- Dropbox ----------

def get_dropbox_access_token() -> str | None:
    if not (DROPBOX_APP_KEY and DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN):
        return None
    resp = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": DROPBOX_REFRESH_TOKEN},
        auth=(DROPBOX_APP_KEY, DROPBOX_APP_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_to_dropbox(access_token: str, filename: str, content: bytes) -> str:
    path = f"{DROPBOX_UPLOAD_FOLDER}/{filename}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Dropbox-API-Arg": json.dumps({"path": path, "mode": "add", "autorename": True, "mute": False}),
        "Content-Type": "application/octet-stream",
    }
    resp = requests.post("https://content.dropboxapi.com/2/files/upload", headers=headers, data=content, timeout=120)
    resp.raise_for_status()
    return path


# ---------- 보드 읽기 ----------

def extract_video_src(card, page) -> str | None:
    """카드 안 video의 실제 재생 URL. 바로 안 나오면(lazy-load) 클릭해서 유도 후 재확인."""
    video_el = card.query_selector("video")
    if not video_el:
        return None

    src = video_el.get_attribute("src")
    if src:
        return src

    source_el = video_el.query_selector("source")
    if source_el and source_el.get_attribute("src"):
        return source_el.get_attribute("src")

    # lazy-load 대응: 카드를 클릭해서 재생을 유도한 뒤 다시 확인
    try:
        card.click()
        page.wait_for_timeout(1500)
        video_el2 = page.query_selector("video")
        if video_el2:
            src2 = video_el2.get_attribute("src")
            if src2:
                return src2
    except Exception as e:
        print(f"  (영상 URL 추출 위한 클릭 실패: {e})")
    finally:
        try:
            page.keyboard.press("Escape")  # 열렸을 수 있는 모달 닫기
        except Exception:
            pass
    return None


def check_board(page) -> list[dict]:
    page.wait_for_selector(CARD_SELECTOR, timeout=30000)
    cards = page.query_selector_all(CARD_SELECTOR)

    results = []
    for card in cards:
        task_id = card.get_attribute("data-task-id")
        if not task_id:
            continue

        video_el = card.query_selector("video")
        if video_el:
            results.append({
                "id": task_id, "status": "done",
                "thumbnail": video_el.get_attribute("poster"), "card": card,
            })
            continue

        card_text = (card.inner_text() or "").lower()
        is_failed = any(kw in card_text for kw in FAIL_KEYWORDS)
        results.append({
            "id": task_id, "status": "failed" if is_failed else "processing",
            "thumbnail": None, "card": card,
        })

    return results


def main():
    if not os.path.exists(STORAGE_STATE_PATH):
        print("storageState.json 이 없습니다. 로그인 세션을 먼저 준비해주세요.")
        sys.exit(1)

    seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()

        page.goto(BOARD_URL)

        if "login" in page.url.lower() or "signin" in page.url.lower():
            print("로그인 페이지로 리다이렉트됨 → 세션 만료로 판단")
            maybe_alert_session_expired()
            browser.close()
            sys.exit(1)

        try:
            items = check_board(page)
        except Exception as e:
            print(f"보드 페이지 읽기 실패 (세션 만료 가능성): {e}")
            maybe_alert_session_expired()
            browser.close()
            sys.exit(1)

        newly_done = [it for it in items if it["status"] == "done" and f"done:{it['id']}" not in seen]
        newly_failed = [it for it in items if it["status"] == "failed" and f"failed:{it['id']}" not in seen]

        dropbox_token = None
        if newly_done:
            try:
                dropbox_token = get_dropbox_access_token()
                if not dropbox_token:
                    print("Dropbox Secret이 설정 안 되어 있어 업로드는 건너뜀 (알림만 진행)")
            except Exception as e:
                print(f"Dropbox 토큰 발급 실패 (업로드 없이 알림만 진행): {e}")

        for item in newly_done:
            note = ""
            if dropbox_token:
                try:
                    video_src = extract_video_src(item["card"], page)
                    if video_src:
                        video_bytes = context.request.get(video_src).body()
                        dropbox_path = upload_to_dropbox(dropbox_token, f"topview_{item['id']}.mp4", video_bytes)
                        note = f"\nDropbox 업로드 완료: `{dropbox_path}`"
                    else:
                        note = "\n⚠️ 실제 영상 URL을 못 찾아 Dropbox 업로드는 건너뜀 (수동 다운로드 필요)"
                except Exception as e:
                    note = f"\n⚠️ Dropbox 업로드 실패: {e}"

            notify_discord(f"✅ **TopView 영상 생성 완료!**\ntask_id: `{item['id']}`{note}", item.get("thumbnail"))
            seen.add(f"done:{item['id']}")
            print(f"완료 알림 전송: {item['id']}")

        for item in newly_failed:
            notify_discord(f"❌ **TopView 영상 생성 실패로 보입니다.**\ntask_id: `{item['id']}`\n보드에서 직접 확인해주세요.")
            seen.add(f"failed:{item['id']}")
            print(f"실패 알림 전송: {item['id']}")

        if not newly_done and not newly_failed:
            print(f"변화 없음. (확인된 항목 {len(items)}개, 이미 처리한 항목 {len(seen)}개)")

        save_seen(seen)
        browser.close()


if __name__ == "__main__":
    main()

# TopView 큐 확인 → Discord 알림 (완전 무료, GitHub Actions)

큐에 넣어둔 TopView 영상 생성 요청이 완료되면, 10분 간격으로 자동 확인해서
Discord 채널에 알림을 보냅니다. 상시 서버/봇 없이 **GitHub Actions 무료 크레딧만** 사용합니다.

## 비용

- **Public 저장소** → GitHub Actions 무제한 무료.
- **Private 저장소** → 무료 티어 월 2,000분 제공 (10분마다 실행 시 1회 약 1~2분 소요 →
  하루 144회 실행이면 월 4,000~8,000분... 이 경우 **저장소를 public으로 만들거나**
  실행 주기를 20~30분으로 늘리는 걸 권장합니다). 로그인 세션이 담긴 secrets는
  public 저장소라도 노출되지 않으니 안전합니다.

## 1. 로컬에서 로그인 세션 저장 (내 PC, 무료)

```bash
pip install playwright
playwright install chromium
python automation_local/login_and_save_session.py
```

브라우저가 뜨면 TopView에 직접 로그인 → 터미널에서 Enter → `scripts/storageState.json` 생성됨.

## 2. GitHub Secrets 등록

저장소 Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|---|---|
| `TOPVIEW_STORAGE_STATE_B64` | `base64 -w0 scripts/storageState.json` 출력값 |
| `DISCORD_WEBHOOK_URL` | Discord 채널 설정 → 연동 → 웹후크 → 새 웹후크 → URL 복사 |

## 3. 워크플로우 활성화

`.github/workflows/check-queue.yml` 을 그대로 push 하면 10분마다 자동 실행됩니다.
Actions 탭에서 수동으로도 "Run workflow" 눌러서 즉시 테스트 가능합니다.

## ⚠️ 아직 채워야 하는 부분

`scripts/check_queue.py` 안의 `SELECTOR_TODO` 표시 — 실제 TopView 보드 페이지의
카드 DOM 구조(클래스명 등)를 보고 채워야 정상 동작합니다. 지금은 뼈대만 있는 상태.

가장 쉬운 확인 방법:
1. 크롬에서 TopView 보드 페이지 열고 F12 (개발자도구)
2. 카드 하나 우클릭 → "검사"
3. 카드 전체를 감싸는 요소, 파일명 텍스트 요소, 상태("Processing"/"In Queue") 텍스트
   요소의 class 이름 확인해서 코드에 반영

이 부분 스크린샷 찍어서 공유해주시면 셀렉터까지 채워서 드릴게요.

## ⚠️ 세션 만료 시

로그인 세션은 시간이 지나면 만료됩니다. 이 경우 워크플로우 로그에
"로그인 세션 만료 가능성" 에러가 뜹니다 → 1번 단계를 다시 실행해서
Secret을 갱신해주세요.

## ⚠️ 봇 탐지 가능성

GitHub Actions는 데이터센터 IP에서 접속하므로, TopView가 이를 비정상 접속으로
탐지해 차단할 가능성이 있습니다. 이 경우 대안:
- 실행 주기를 늘려서 (예: 30분) 트래픽 패턴을 자연스럽게
- 그래도 막히면 GitHub Actions "셀프 호스티드 러너"를 본인 PC에 등록해서
  같은 워크플로우 파일 그대로, 본인 집 IP에서 실행 (PC가 켜져있을 때만 동작,
  비용은 여전히 0원)

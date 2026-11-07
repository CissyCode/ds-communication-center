# news_bot — 네이버 기사 → 텔레그램 단체방 공유 봇

`news_bot/queries.json`에 적은 검색 조건으로 네이버 뉴스를 주기적으로 검색해, 새 기사만 텔레그램 단체방에 묶어서 보냅니다.
표준 라이브러리만 써서 추가로 설치할 패키지가 없습니다(Python 3.10+).

```
📰 삼성 반도체 · 3건

• 삼성전자, HBM4 12단 양산 돌입
  hankyung.com · 11/07 09:12
  삼성전자가 차세대 고대역폭메모리 HBM4 양산을…
```

## 1. 준비 (최초 1회)

### 1-1. 네이버 검색 API 키
1. https://developers.naver.com/apps 에서 **Application 등록**
2. 사용 API: **검색** 선택, 환경: WEB 설정(URL은 아무 값이나 가능)
3. 발급된 **Client ID / Client Secret** 저장 (하루 25,000회 무료)

### 1-2. 텔레그램 봇 + 단체방
1. 텔레그램에서 **@BotFather** → `/newbot` → 봇 이름 입력 → **토큰** 저장
2. 기사 공유용 **단체방 생성** → 만든 봇을 멤버로 초대
3. 단체방에 `/help` 메시지를 한 번 보냄
4. chat id 확인:
   ```bash
   TELEGRAM_BOT_TOKEN=발급받은토큰 python -m news_bot chat-id
   ```
   `-100…`으로 시작하는 group/supergroup id가 단체방 id입니다.

### 1-3. 설정 파일
```bash
cp .env.example .env   # 4개 값 채우기 (.env는 git에 올라가지 않음)
```

## 2. 검색 조건 설정 — `news_bot/queries.json`

| 항목 | 설명 | 기본값 |
|---|---|---|
| `name` | 단체방 메시지 제목으로 쓰이는 조건 이름 | (필수) |
| `query` | 네이버 뉴스 검색어 | (필수) |
| `include_any` | 제목·요약에 이 중 **하나라도** 있어야 함 | 없음 |
| `include_all` | 제목·요약에 **모두** 있어야 함 | 없음 |
| `exclude` | 하나라도 있으면 제외 (예: `주가`, `특징주`) | 없음 |
| `sort` | `date`(최신순) / `sim`(정확도순) | `date` |
| `display` | API에서 가져올 개수 (최대 100) | 30 |
| `max_per_run` | 한 번에 보낼 최대 개수 | 5 |
| `max_age_hours` | 이보다 오래된 기사 무시 (0이면 제한 없음) | 24 |
| `naver_only` | 네이버 뉴스(n.news.naver.com) 링크가 있는 기사만 | false |
| `enabled` | false면 일시 중지 | true |

파일 최상단의 `interval_minutes`(확인 주기, loop 모드)와 `quiet_hours`(예: `[22, 7]` → 22시~7시 KST 발송 안 함, 없애려면 `null`)도 조정할 수 있습니다.

> 검색어 자체는 네이버 API에 그대로 전달됩니다. 정밀한 조건(OR/AND/제외)은 `include_any`/`include_all`/`exclude`로 거는 편이 확실합니다.

조건을 바꾼 뒤에는 **발송 없이** 결과부터 확인하세요:
```bash
python -m news_bot preview                  # 전체 조건
python -m news_bot preview --name "HBM 시장"  # 특정 조건만
```

## 3. 실행 방법 (택1)

### A. 상주 실행 — 단체방 명령어까지 사용 (사내 서버/PC)
```bash
python -m news_bot loop
```
`interval_minutes`마다 자동 발송하고, 단체방에서 아래 명령어에 응답합니다.

| 명령어 | 동작 |
|---|---|
| `/news 검색어` | 지금 바로 네이버 뉴스 검색 결과 10건 (최근 72시간) |
| `/queries` | 등록된 자동 검색 조건 목록 |
| `/run` | 자동 검색 조건으로 즉시 수집 (방해 금지 시간 무시) |
| `/help` | 도움말 |

명령어는 `TELEGRAM_CHAT_ID`로 지정한 단체방에서 온 것만 처리합니다.

### B. GitHub Actions — 서버 없이 자동 발송만
리포지토리 **Settings → Secrets and variables → Actions**에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 등록하면 `.github/workflows/news-bot.yml`이 30분마다 `python -m news_bot run`을 실행합니다. (GitHub 스케줄은 수 분씩 지연될 수 있고, 단체방 명령어는 동작하지 않습니다.)

### C. cron
```
*/30 * * * * cd /path/to/ds-communication-center && python3 -m news_bot run >> storage/news_bot.log 2>&1
```

## 중복 발송 방지
보낸 기사는 `storage/news_bot.db`(SQLite, git 제외)에 기록되며 원문 링크 **또는** 정규화한 제목이 같으면 다시 보내지 않습니다(여러 조건에 동시에 걸린 기사도 한 번만). 기록은 30일 후 자동 삭제됩니다.

## 테스트
```bash
python -m unittest tests.test_news_bot
```

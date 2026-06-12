# NPS Tracker

국민연금(연기금 등)의 한국 주식시장 매매 데이터를 추적·분석하고, 추종 전략의 유효성을 과거 데이터로 검증하는 웹 애플리케이션.

> **데이터 출처 안내**: KRX는 "국민연금" 단독 데이터를 제공하지 않으며 **"연기금 등" 합산 카테고리**로만 공개합니다. 장 마감 후(T+1) 기준 데이터입니다.

🔗 **서비스 URL**: https://gukyeondda.up.railway.app

---

## 주요 기능

| 페이지 | URL | 설명 |
|--------|-----|------|
| 매매 동향 | `/` | KRX "연기금 등" 일별 순매수 상위 종목, 연속 매수일수·매수강도 시각화 |
| 종목 상세 | `/stocks/{ticker}` | 특정 종목의 NPS 매매 시계열 차트 |
| 백테스팅 | `/backtest` | "N일 연속 매수 종목을 따라 사면 수익이 났을까?" DQN 강화학습 기반 전략 검증 |
| 오늘의 추천종목 | `/recommend` | DQN(bandit) 및 포트폴리오 강화학습(MDP) 기반 오늘의 추천 |
| 기관별 종합추천 | `/investor-recommendations` | 기관·외국인·동시매수 점수를 종합한 TOP 50 추천 |

---

## 서비스 접속

| 서비스 | URL |
|--------|-----|
| 웹 애플리케이션 | https://gukyeondda.up.railway.app |

> API Swagger 문서(`/docs`)는 Railway 대시보드 → api 서비스 URL 에서 접근할 수 있습니다.

---

## 화면별 사용 방법

### 매매 동향 (`/`)

장 마감 후(T+1) 수집된 연기금 순매수 상위 종목을 표시합니다.

- **시장 필터**: KOSPI / KOSDAQ 전체 또는 개별 선택
- **정렬 기준**: 순매수금액 / 연속매수일수 / 매수강도 중 선택
- 종목명 클릭 시 해당 종목의 시계열 매매 차트로 이동

### 백테스팅 (`/backtest`)

전략 파라미터를 설정하고 과거 데이터로 수익률을 검증합니다.

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| 시작일 / 종료일 | - | 백테스팅 기간 |
| 최소 연속 매수일 | 3일 | 연기금이 N일 연속 순매수한 종목만 후보 |
| 최소 순매수금액 | 10억원 | 일별 순매수금액 하한 |
| 최소 매수강도 | 0.1% | 순매수금액 ÷ 시가총액 하한 |
| 보유 기간 | 20영업일 | 매수 후 보유 기간 |
| 진입 지연일 | 1일 | look-ahead bias 방지 (최소 1) |
| 최대 동시 보유 | 10종목 | 동시에 보유할 수 있는 최대 종목 수 |
| 초기 자본 | 1,000만원 | 백테스팅 시작 자본 |
| 거래 비용 | 0.25% | 수수료 + 세금 + 슬리피지 합산 |

> DQN 강화학습 에이전트가 매일 후보 종목 중 1개를 선택합니다. 결과는 총 수익률, CAGR, MDD, 샤프 비율, 승률 등으로 표시됩니다.

### 오늘의 추천종목 (`/recommend`)

**DQN 추천 (bandit)**: 매매동향 후보 중 DQN이 가장 유망하다고 판단한 종목 1개를 선택합니다.

**포트폴리오 강화학습(MDP) 추천**: 현금·보유종목·평가손익을 상태에 포함한 MDP DQN이 종목을 선택합니다. 모델이 "관망"을 선택하면 추천 없음이 반환될 수 있습니다.

### 기관별 종합추천 (`/investor-recommendations`)

연기금·외국인·기관 투자자의 동시 매수 패턴을 기반으로 점수를 산출하여 TOP 50 종목을 표시합니다.

- 기관 컨센서스 점수, 외국인 점수, 동시매수 기관 수 반영
- 매일 07:00 KST 자동 업데이트

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14 (App Router) · TypeScript · Tailwind CSS · TanStack Query · Recharts |
| 백엔드 | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| DB | PostgreSQL 16 + TimescaleDB (시계열 최적화) |
| 캐시 | Redis 7 (API 응답 TTL 1h, 백테스팅 job 상태) |
| 데이터 수집 | pykrx · OpenDartReader · APScheduler |
| 강화학습 | PyTorch (CPU) · DQN · MDP |
| 인프라 | Railway (web · api · collector · PostgreSQL · Redis) |

---

## 프로젝트 구조

```
nps-tracker/
├── data-collector/     # KRX/DART 데이터 수집 (APScheduler, 매일 07:00 KST)
│   ├── scrapers/       # 수집기 (OHLCV, NPS, 투자자별 수급, 백필)
│   └── db/             # 스키마 초기화, 세션 팩토리
├── api/                # FastAPI 백엔드
│   ├── routers/        # nps, backtest, stocks, investor_recommendation
│   └── services/       # 비즈니스 로직, Redis 캐시, 백테스팅 실행
├── backtest/           # 백테스팅 엔진 + DQN 에이전트
│   ├── engine.py       # 백테스팅 실행, 추천 로직
│   ├── dqn_agent.py    # DQN 에이전트 (bandit)
│   └── rl_state.py     # MDP 상태 정의
├── models/             # 학습된 DQN 모델 가중치 (.pth)
└── web/                # Next.js 프론트엔드
    ├── app/            # App Router 페이지
    └── components/     # 공통 컴포넌트
```

---

## 데이터 수집 구조

```
매일 07:00 KST (전 영업일 기준)
│
├── 1. 종목 마스터 갱신 (신규 상장/폐지 추적)
├── 2. OHLCV 수집 (KRX 일별 시가/고가/저가/종가/거래량/시가총액)
├── 3. NPS 매매 수집 (KRX "연기금 등" 순매수 데이터)
├── 4. 연속매수일수·매수강도 재계산
├── 5. 투자자별 수급 수집 (연기금/외국인/기관 등)
├── 6. 투자자별 시그널 재계산
└── 7. 기관 컨센서스 점수 계산 → daily_top_recommendations 갱신
```

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/nps/daily` | 일별 연기금 순매수 상위 종목 |
| GET | `/api/nps/stocks/{ticker}/trades` | 종목별 NPS 매매 시계열 |
| GET | `/api/nps/stocks/{ticker}/holdings` | 종목별 NPS 5% 이상 보유 공시 |
| GET | `/api/stocks` | 종목 목록 |
| GET | `/api/stocks/{ticker}` | 종목 상세 |
| POST | `/api/backtest` | 백테스팅 실행 요청 (비동기, job_id 반환) |
| GET | `/api/backtest/{job_id}` | 백테스팅 결과 조회 (폴링) |
| POST | `/api/backtest/recommend` | DQN(bandit) 오늘의 추천종목 |
| POST | `/api/backtest/recommend-mdp` | DQN(MDP) 포트폴리오 추천종목 |
| GET | `/api/investor-recommendations` | 기관 컨센서스 TOP 50 |
| GET | `/health` | 헬스체크 |

전체 API 명세(Swagger UI): Railway 대시보드 → api 서비스 URL → `/docs`

---

## 배포 구성 (Railway)

| 서비스 | 역할 |
|--------|------|
| web | Next.js 프론트엔드 |
| api | FastAPI 백엔드 |
| collector | 데이터 수집 스케줄러 (매일 07:00 KST 자동 실행) |
| PostgreSQL | TimescaleDB 확장 적용 시계열 DB |
| Redis | API 응답 캐시(TTL 1h) + 백테스팅 job 상태 저장 |

### 환경변수 (Railway Variables)

```
# api, collector 공통
DATABASE_URL=postgresql+psycopg2://...@postgres.railway.internal:5432/railway
REDIS_URL=redis://...@redis.railway.internal:6379

# collector 추가
DART_API_KEY=...          # DART 공시 수집
KRX_ID=...                # KRX 데이터포털 ID
KRX_PW=...                # KRX 데이터포털 PW

# web
NEXT_PUBLIC_API_URL=https://{api-service}.up.railway.app
```

---

## 데이터 백필 (초기 구축 또는 DB 재생성 시)

Railway collector 서비스 → **Shell** 탭에서 실행:

```bash
# 스키마 초기화 (최초 1회)
python -m db.init_schema

# 과거 데이터 백필 (기간이 길수록 백테스팅 정확도 향상)
python -m scrapers.backfill --from 2024-01-01 --to 2026-06-11

# 특정 날짜 즉시 수집 (누락 시)
python -m scrapers.daily_runner --now --date 2026-06-11
```

---

## 백테스팅 원칙

- **Look-ahead bias 방지**: T일 시그널로 T+1일에 진입 (`entry_lag_days >= 1` 강제)
- **생존편향 방지**: 상장폐지 종목 포함, 폐지일 도달 시 -100% 손실 처리
- **거래비용 반영**: 매수 체결가 × (1 + cost%), 매도 × (1 - cost%) 적용

---

## 법적 고지

본 서비스는 **정보 제공 목적**이며, 투자 자문이 아닙니다.

- 표시되는 데이터는 KRX의 "연기금 등" 카테고리 **합산 매매 정보**로, 국민연금공단 단독 매매가 아닙니다.
- 모든 매매 데이터는 **장 마감 후(T+1) 기준**이며, 실시간 정보가 아닙니다.
- 과거 매매 패턴이 미래 수익을 보장하지 않습니다.
- 투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다.

한국 자본시장법상 불특정 다수에게 종목을 "추천"하는 행위는 유사투자자문업 신고 대상이 될 수 있습니다. 본 서비스는 "추천 종목", "매수 추천" 등의 표현을 사용하지 않습니다.

**데이터 출처**: 한국거래소(KRX) · 금융감독원 전자공시시스템(DART)

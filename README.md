# NPS Tracker

국민연금(연기금 등)의 한국 주식시장 매매 데이터를 추적·분석하고, 추종 전략의 유효성을 과거 데이터로 검증하는 웹 애플리케이션.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [디렉토리 구조](#4-디렉토리-구조)
5. [데이터 모델](#5-데이터-모델)
6. [구현 상세](#6-구현-상세)
7. [API 명세](#7-api-명세)
8. [로컬 개발 환경](#8-로컬-개발-환경)
9. [배포](#9-배포)
10. [법적 고지](#10-법적-고지)

---

## 1. 프로젝트 개요

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 일별 매매 동향 | KRX "연기금 등" 일별 순매수 상위 종목 시각화 |
| 종목 상세 분석 | 특정 종목의 NPS 매매 시계열 차트 |
| 백테스팅 | "N일 연속 매수 종목을 따라 사면 수익이 났을까?" 전략 검증 |
| 자동 수집 | 매일 07:00 KST 전 영업일 데이터 자동 수집 |

### 데이터 출처의 한계

- KRX는 "국민연금" 단독 데이터를 제공하지 않으며 **"연기금 등" 합산 카테고리**로만 공개
- 장 마감 후 T+1 기준으로 데이터 확정 → 실시간 정보 아님
- 5% 이상 보유 정확치는 분기 단위 DART 공시로만 확인 가능

---

## 2. 기술 스택

### 백엔드

| 구성요소 | 기술 | 버전 | 선택 이유 |
|---------|------|------|---------|
| API 프레임워크 | FastAPI | ≥0.110 | 자동 OpenAPI 문서, 비동기 지원 |
| ORM | SQLAlchemy | 2.0 | Mapped[T] 타입 힌트, 2.0 스타일 |
| DB | PostgreSQL + TimescaleDB | PG 16 | 시계열 쿼리 최적화, 청크 압축 |
| 캐시 | Redis | 7 | API 응답 캐싱 (TTL 1시간) |
| 로깅 | loguru | ≥0.7 | 구조화 JSON 로그, rotation |
| 유효성 검증 | Pydantic v2 | ≥2.0 | BaseModel, ConfigDict |

### 프론트엔드

| 구성요소 | 기술 | 버전 | 선택 이유 |
|---------|------|------|---------|
| 프레임워크 | Next.js App Router | 16.2 | SSR/SEO, Server Components |
| 언어 | TypeScript | ≥5 | strict mode, 타입 안전성 |
| 스타일링 | Tailwind CSS | v4 | 유틸리티 기반, 빠른 개발 |
| 서버 상태 | TanStack Query | v5 | 캐싱, 재시도, 로딩 상태 |
| 차트 | Recharts | ≥3.8 | React 친화적, 이중축 지원 |

### 데이터 수집

| 구성요소 | 기술 | 역할 |
|---------|------|------|
| KRX 스크래퍼 | pykrx ≥1.2 | OHLCV, 연기금 순매수 수집 |
| DART 스크래퍼 | OpenDartReader ≥0.2 | 5% 보유 공시 수집 |
| 스케줄러 | APScheduler ≥3.10 | 매일 07:00 KST 자동 실행 |
| 재시도 | tenacity ≥8.2 | KRX 일시 장애 자동 재시도 |

### 백테스팅

| 구성요소 | 기술 | 역할 |
|---------|------|------|
| 연산 | Pandas + NumPy | 벡터 연산, 시계열 처리 |
| 비동기 실행 | ThreadPoolExecutor | API 블로킹 없이 백그라운드 실행 |
| 상태 관리 | Redis | job 상태 저장 (pending/running/done/failed) |

### 인프라

| 구성요소 | 기술 |
|---------|------|
| 로컬 개발 | Docker Compose |
| 컨테이너 이미지 | TimescaleDB PG16, Redis 7 Alpine |
| 배포 대상 | Railway (예정) |

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        사용자 브라우저                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────────┐
│                   Next.js (포트 3000)                         │
│  app/page.tsx          → 메인: 일별 순매수 상위               │
│  app/stocks/[ticker]   → 종목 상세 + 매매 차트                │
│  app/backtest          → 전략 파라미터 입력 + 결과 시각화       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP (NEXT_PUBLIC_API_URL)
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI (포트 8000)                         │
│                                                             │
│  routers/nps_trades.py  ← Redis 캐싱 (TTL 1h)              │
│  routers/stocks.py                                          │
│  routers/backtest.py    ← ThreadPoolExecutor 비동기          │
│                                                             │
│  services/nps_service.py    (비즈니스 로직)                   │
│  services/stock_service.py                                  │
│  services/backtest_service.py                               │
│  services/cache_service.py                                  │
└──────────┬──────────────────────────┬───────────────────────┘
           │ SQLAlchemy 2.0           │ redis-py
┌──────────▼──────────┐   ┌──────────▼──────────┐
│  TimescaleDB PG 16  │   │     Redis 7          │
│  (포트 5432)         │   │    (포트 6379)        │
│                     │   │                     │
│  stocks             │   │  nps:daily:*  TTL1h │
│  daily_ohlcv ★      │   │  backtest:{job_id}  │
│  nps_daily_trades ★ │   └─────────────────────┘
│  nps_holdings       │
│  collection_logs    │
│  ★ = hypertable     │
└──────────▲──────────┘
           │ SQLAlchemy
┌──────────┴──────────────────────────────────────────────────┐
│              data-collector (APScheduler)                    │
│                                                             │
│  매일 07:00 KST                                              │
│  scrapers/daily_runner.py                                   │
│    → sync_stock_master()   종목 마스터 갱신                   │
│    → save_daily_ohlcv()    전일 시세 저장                     │
│    → save_nps_daily_trades() 연기금 매매 저장                 │
│    → recalculate_signals() consecutive_buy_days 재계산       │
│                                                             │
│  scrapers/backfill.py   과거 데이터 일괄 수집                  │
│  scrapers/krx_scraper.py   pykrx 래퍼                        │
│  scrapers/dart_scraper.py  DART 5% 공시                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 디렉토리 구조

```
nps-tracker/
├── docker-compose.yml           # 로컬 개발용 (db + redis)
├── .env.production.example      # 프로덕션 환경변수 템플릿
│
├── data-collector/              # 데이터 수집 서비스
│   ├── config.py                # pydantic-settings 환경변수
│   ├── db/
│   │   ├── models.py            # SQLAlchemy 2.0 ORM 모델
│   │   ├── session.py           # 세션 팩토리 (contextmanager)
│   │   └── init_schema.py       # 스키마 + hypertable 초기화
│   ├── scrapers/
│   │   ├── krx_scraper.py       # pykrx 래퍼 (OHLCV, NPS 매매)
│   │   ├── dart_scraper.py      # DART 5% 보유 공시
│   │   ├── backfill.py          # 과거 데이터 일괄 수집
│   │   └── daily_runner.py      # APScheduler (07:00 KST)
│   └── Dockerfile
│
├── api/                         # FastAPI 백엔드
│   ├── main.py                  # 앱 진입점, CORS, 미들웨어
│   ├── config.py                # 환경변수 (DATABASE_URL, REDIS_URL 등)
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM (data-collector와 동일 스키마)
│   │   └── session.py           # get_session() 의존성 주입
│   ├── routers/
│   │   ├── nps_trades.py        # /api/nps/*
│   │   ├── stocks.py            # /api/stocks/*
│   │   └── backtest.py          # /api/backtest
│   ├── schemas/                 # Pydantic v2 응답 모델
│   ├── services/                # 비즈니스 로직 레이어
│   ├── tests/
│   │   ├── conftest.py          # pytest 픽스처 (test DB, seed_data)
│   │   └── test_nps_endpoints.py # 통합 테스트 19개
│   └── Dockerfile
│
├── backtest/                    # 백테스팅 엔진
│   ├── strategies.py            # FollowStrategy 파라미터 정의
│   ├── engine.py                # 백테스팅 핵심 로직
│   └── tests/
│       └── test_engine.py
│
└── web/                         # Next.js 프론트엔드
    ├── app/
    │   ├── page.tsx             # 메인: 일별 순매수 상위
    │   ├── stocks/[ticker]/     # 종목 상세
    │   └── backtest/            # 백테스팅 페이지
    ├── components/
    │   ├── nps-daily-dashboard.tsx  # 메인 테이블 + 요약 카드
    │   ├── stock-detail.tsx         # 종목 차트 + 매매 이력
    │   ├── backtest-form.tsx        # 전략 파라미터 입력 폼
    │   ├── nps-trades-chart.tsx     # 이중축 시계열 차트
    │   └── disclaimer.tsx           # 법적 면책 고지
    ├── lib/
    │   ├── api.ts               # API 호출 함수 모음
    │   ├── types.ts             # TypeScript 인터페이스
    │   └── utils.ts             # 금액/날짜 포매터
    ├── e2e/                     # Playwright E2E 테스트 21개
    └── Dockerfile
```

---

## 5. 데이터 모델

### stocks — 종목 마스터
```sql
ticker          VARCHAR(6) PRIMARY KEY   -- '005930'
name            VARCHAR(100) NOT NULL    -- '삼성전자'
market          VARCHAR(10) NOT NULL     -- 'KOSPI' | 'KOSDAQ'
sector          VARCHAR(100)
listing_date    DATE
delisting_date  DATE                     -- 생존편향 방지에 필수
is_active       BOOLEAN NOT NULL DEFAULT TRUE
```

### daily_ohlcv — 일별 시세 (TimescaleDB hypertable)
```sql
trade_date      DATE NOT NULL  -- PK
ticker          VARCHAR(6)     -- PK
open, high, low, close  INTEGER NOT NULL   -- 원 단위
volume          BIGINT NOT NULL
trading_value   BIGINT NOT NULL            -- 거래대금
market_cap      BIGINT                     -- 시가총액
shares_outstanding BIGINT
```

### nps_daily_trades — 연기금 일별 매매 (TimescaleDB hypertable)
```sql
trade_date          DATE NOT NULL   -- PK
ticker              VARCHAR(6)      -- PK
net_buy_volume      BIGINT NOT NULL -- 순매수 수량 (음수 = 순매도)
net_buy_amount      BIGINT NOT NULL -- 순매수 금액 (원)
consecutive_buy_days INTEGER        -- 사후 계산: 연속 매수일
buy_intensity_pct   DOUBLE PRECISION -- 시총 대비 매수 비중 (%)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

### TimescaleDB 설정
- `daily_ohlcv`, `nps_daily_trades` → hypertable 변환 (chunk_interval = 1 month)
- segmentby = `ticker` → 종목별 시계열 조회 가속
- 3개월 이상 청크 자동 압축 (디스크 ~70% 절감)

### 주요 인덱스
```sql
-- 메인 화면: 특정 일자 순매수 상위
CREATE INDEX idx_nps_date_amount ON nps_daily_trades (trade_date, net_buy_amount DESC);

-- 종목 상세: 특정 종목 시계열
CREATE INDEX idx_nps_ticker_date ON nps_daily_trades (ticker, trade_date);
CREATE INDEX idx_ohlcv_ticker_date ON daily_ohlcv (ticker, trade_date);
```

---

## 6. 구현 상세

### 6.1 데이터 수집 파이프라인

매일 07:00 KST 실행 순서:

```
1. sync_stock_master()
   └── KRX 전종목 마스터 조회 → stocks 테이블 upsert

2. save_daily_ohlcv(target_date)
   └── pykrx.get_market_ohlcv_by_ticker() → daily_ohlcv upsert

3. save_nps_daily_trades(target_date)
   └── pykrx.get_market_net_purchases_of_investor() → nps_daily_trades upsert

4. recalculate_signals(target_date)
   ├── consecutive_buy_days: 역순으로 순매수 연속일 카운트
   └── buy_intensity_pct: net_buy_amount / market_cap × 100
```

**멱등성 보장**: 모든 저장은 `INSERT ... ON CONFLICT DO UPDATE` — 동일 일자를 두 번 수집해도 결과 동일.

**수집 대상 날짜**: 당일 07:00 → 전 영업일 수집. 주말이면 금요일로 자동 스킵.

### 6.2 종가 표시 로직 (D-day close)

NPS 데이터는 T+1 공개이므로, 화면에서 조회 기준일의 종가를 표시:

```python
# nps_service.py
latest_ohlcv_date = MAX(daily_ohlcv.trade_date)  # 오늘 수집된 최신 종가 기준일
# NPS trade_date 기준이 아니라 최신 OHLCV 기준으로 JOIN
```

Redis 캐시 키에 `latest_ohlcv_date` 포함 → OHLCV 갱신 시 자동 무효화.

### 6.3 백테스팅 엔진

**FollowStrategy 파라미터**:

| 파라미터 | 기본값 | 설명 |
|---------|-------|------|
| `min_consecutive_days` | 3 | 최소 연속 매수일 |
| `min_net_buy_amount` | 10억원 | 최소 순매수 금액 |
| `min_buy_intensity_pct` | 0.1% | 최소 시총 대비 매수 강도 |
| `holding_period_days` | 20 | 보유 기간 (영업일) |
| `entry_lag_days` | 1 | 시그널 후 매수 지연일 (최소 1 강제) |
| `max_positions` | 10 | 동시 보유 최대 종목 수 |
| `initial_capital` | 1,000만원 | 초기 자본 |
| `transaction_cost_pct` | 0.25% | 거래비용 (수수료+세금+슬리피지) |

**핵심 원칙 (위반 시 AssertionError)**:

1. **No look-ahead bias**: `entry_lag_days >= 1` 강제. T일 시그널 → T+1일 이후 매수.
2. **Survivorship bias 방지**: 백테스트 기간 중 폐지된 종목도 포함, 폐지일에 -100% 손실 처리.
3. **거래비용 반영**: 매수가 = 시초가 × (1 + cost%), 매도가 = 시초가 × (1 - cost%).

**비동기 실행**: `POST /api/backtest` → ThreadPoolExecutor에서 백그라운드 실행 → Redis에 job 상태 저장 → `GET /api/backtest/{job_id}` 폴링.

### 6.4 캐싱 전략

```
nps:daily:{trade_date}:{limit}:{market}:{latest_ohlcv_date}
  TTL: 3600초 (1시간)
  무효화: latest_ohlcv_date 변경 시 자연 만료

backtest:{job_id}
  TTL: 86400초 (24시간)
  값: pending | running | done | failed + 결과 데이터
```

---

## 7. API 명세

베이스 URL: `http://localhost:8000`  
문서(Swagger UI): `http://localhost:8000/docs`

### NPS 매매

| 메서드 | 경로 | 설명 |
|-------|------|------|
| GET | `/api/nps/daily` | 일별 순매수 상위 종목 |
| GET | `/api/nps/stocks/{ticker}/trades` | 종목별 NPS 매매 시계열 |
| GET | `/api/nps/stocks/{ticker}/holdings` | 5% 보유 공시 이력 |

**GET `/api/nps/daily` 쿼리 파라미터**:

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `date` | YYYY-MM-DD | 최신일 자동 선택 | 조회 기준일 |
| `limit` | int | 50 | 최대 반환 종목 수 |
| `market` | KOSPI\|KOSDAQ | 전체 | 시장 필터 |

**응답 예시**:
```json
{
  "trade_date": "2026-05-20",
  "close_date": "2026-05-21",
  "total_net_buy_amount": 312000000000,
  "net_buy_count": 234,
  "net_sell_count": 89,
  "data_notice": "본 데이터는 KRX의 '연기금 등' 카테고리 합산치이며...",
  "items": [
    {
      "rank": 1,
      "ticker": "005930",
      "name": "삼성전자",
      "market": "KOSPI",
      "close": 61000,
      "change_pct": 1.23,
      "net_buy_amount": 30000000000,
      "net_buy_volume": 500000,
      "consecutive_buy_days": 5,
      "buy_intensity_pct": 0.082
    }
  ]
}
```

### 종목

| 메서드 | 경로 | 설명 |
|-------|------|------|
| GET | `/api/stocks` | 종목 목록 (페이지네이션) |
| GET | `/api/stocks/{ticker}` | 종목 상세 + 최근 OHLCV |

### 백테스팅

| 메서드 | 경로 | 설명 |
|-------|------|------|
| POST | `/api/backtest` | 백테스팅 작업 제출 → 202 + job_id |
| GET | `/api/backtest/{job_id}` | 작업 상태 및 결과 조회 |

**결과 지표**:
```json
{
  "job_id": "uuid",
  "status": "done",
  "total_return_pct": 23.4,
  "cagr_pct": 12.1,
  "max_drawdown_pct": -8.3,
  "sharpe_ratio": 1.42,
  "win_rate_pct": 58.3,
  "trades_count": 87,
  "equity_curve": [{"date": "2021-01-04", "equity": 10000000}, ...]
}
```

---

## 8. 로컬 개발 환경

### 사전 요구사항

- Docker Desktop
- Python 3.11+
- Node.js 20+
- pnpm 또는 npm

### 빠른 시작

```bash
# 1. 인프라 실행 (PostgreSQL + Redis)
docker compose up -d

# 2. 스키마 초기화
cd data-collector
python -m db.init_schema

# 3. 과거 데이터 백필 (최초 1회)
python -m scrapers.backfill --years 5

# 4. API 서버 실행
cd ../api
pip install -r requirements.txt
PYTHONPATH=. uvicorn main:app --reload

# 5. 웹 서버 실행
cd ../web
npm install
npm run dev
```

### 접속 주소

| 서비스 | URL |
|-------|-----|
| 웹 | http://localhost:3000 |
| API | http://localhost:8000 |
| API 문서 | http://localhost:8000/docs |

### 데이터 수집 수동 실행

```bash
cd data-collector

# 전 영업일 데이터 즉시 수집
python -m scrapers.daily_runner --now

# 특정 날짜 수집
python -m scrapers.daily_runner --now --date 2026-05-20

# 스케줄러 상시 가동 (매일 07:00 KST 자동 실행)
python -m scrapers.daily_runner
```

### 테스트

```bash
# API 통합 테스트 (nps_tracker_test DB 필요)
cd api
pytest tests/ -v

# E2E 테스트 (개발 서버 실행 중이어야 함)
cd web
npm run test:e2e

# E2E 테스트 UI 모드
npm run test:e2e:ui
```

### 환경변수

```bash
# data-collector/.env, api/.env
DATABASE_URL=postgresql+psycopg2://nps_user:localdevpassword@localhost:5432/nps_tracker
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
DART_API_KEY=your_key_here        # DART 공시 수집 시 필요

# api/.env 추가
ALLOWED_ORIGINS=http://localhost:3000

# web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 9. 배포

### Railway 배포 (예정)

각 서비스에 `railway.toml` 설정 완료. GitHub 저장소: [jisubhan/nps-tracker](https://github.com/jisubhan/nps-tracker)

**서비스 구성**:

| Railway 서비스 | 이미지/소스 | 포트 |
|--------------|-----------|------|
| db | `timescale/timescaledb:latest-pg16` | 5432 |
| redis | Railway 플러그인 | 6379 |
| api | `./api` Dockerfile | $PORT |
| web | `./web` Dockerfile | $PORT |
| collector | `./data-collector` Dockerfile | - |

**프로덕션 환경변수**: `.env.production.example` 참고

### Docker 이미지 특징

- **멀티스테이지 빌드**: web은 deps → builder → runner 3단계 (이미지 크기 최소화)
- **non-root 실행**: 모든 컨테이너 uid 1001 appuser/nextjs로 실행
- **Next.js standalone**: `output: 'standalone'` 모드로 node_modules 번들링 없이 배포

---

## 10. 법적 고지

본 서비스는 **정보 제공 목적**이며, 투자 자문이 아닙니다.

- 표시되는 데이터는 한국거래소(KRX)가 공개하는 "연기금 등" 카테고리의 **합산 매매 정보**로, 국민연금공단 단독 매매가 아닙니다.
- 모든 매매 데이터는 **장 마감 후(T+1) 기준**이며, 실시간 정보가 아닙니다.
- 과거 매매 패턴이 미래 수익을 보장하지 않습니다.
- 투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다.

한국 자본시장법상 불특정 다수에게 종목을 "추천"하는 행위는 유사투자자문업 신고 대상이 될 수 있습니다. 본 서비스는 "추천 종목", "매수 추천" 등의 표현을 사용하지 않습니다.

**데이터 출처**: 한국거래소(KRX), 금융감독원 전자공시시스템(DART)

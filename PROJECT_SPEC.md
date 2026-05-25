# NPS Tracker - 프로젝트 사양서

> 국민연금(연기금 등) 매매 데이터를 추적·분석하여 추종 전략의 유효성을 검증하는 웹 애플리케이션

## 1. 프로젝트 개요

### 1.1 목적

한국 주식시장에서 국민연금공단(NPS)의 매매 패턴을 분석하여, 개인 투자자가 의사결정 보조 도구로 활용할 수 있는 분석 플랫폼을 구축한다.

### 1.2 핵심 가치 제안

- **일별 매매 동향 가시화**: KRX의 "연기금 등" 일별 순매수 상위 종목을 직관적으로 표시
- **종목별 보유 추이 추적**: 특정 종목의 국민연금 보유량/순매수 흐름을 시계열로 시각화
- **백테스팅을 통한 전략 검증**: "국민연금이 N일 연속 매수한 종목을 따라 사면 수익이 났을까?" 같은 가설을 과거 데이터로 검증

### 1.3 ⚠️ 중요한 제약사항 (반드시 인지)

#### 1.3.1 데이터의 한계

- **KRX는 "국민연금" 단독 데이터를 제공하지 않는다.** "연기금 등"이라는 합산 카테고리로만 공개됨 (국민연금이 절대다수 비중)
- **장중 실시간 데이터는 매수/매도 분리되지 않음.** 장 종료 후(T+1) 마감 데이터로만 종목별 순매수 확인 가능
- **5% 이상 보유 정확치는 분기 단위 DART 공시**로만 확인 가능 (보고 의무 후 5영업일 내)

따라서 본 서비스의 모든 화면에 다음 고지를 명확히 표시한다:

> "본 데이터는 KRX의 '연기금 등' 카테고리 합산치이며, 국민연금 단독 매매가 아닙니다. 장 마감 후(T+1) 기준입니다."

#### 1.3.2 법적 제약

- 한국 자본시장법상 불특정 다수에게 종목을 "추천"하면 유사투자자문업 신고 대상이 될 수 있다
- 따라서 UI 문구에서 다음을 준수한다:
  - ❌ "추천 종목", "매수 추천", "AI 추천"
  - ✅ "국민연금 매매 정보", "순매수 상위", "정보 제공"
- 모든 페이지 하단에 면책 고지 필수

---

## 2. 기술 스택

### 2.1 결정된 스택

| 계층 | 기술 | 선택 이유 |
|------|------|-----------|
| 프론트엔드 | Next.js 14 (App Router) + TypeScript | SSR/SEO, React 친숙도, 풍부한 생태계 |
| UI 컴포넌트 | Tailwind CSS + shadcn/ui | 빠른 프로토타이핑, 일관된 디자인 시스템 |
| 차트 | Recharts | React 친화적, D3보다 단순, 충분한 표현력 |
| 백엔드 | Python 3.11 + FastAPI | Pandas 생태계 활용 (백테스팅에 결정적) |
| ORM | SQLAlchemy 2.0 + Alembic | 타입 힌트 지원, 마이그레이션 관리 |
| DB | PostgreSQL 16 + TimescaleDB | 시계열 쿼리 최적화 (수년치 일별 데이터) |
| 캐시/큐 | Redis 7 | API 응답 캐싱, Celery 브로커 |
| 스케줄러 | APScheduler (PoC) → Celery Beat (운영) | 매일 장 마감 후 데이터 수집 |
| 데이터 수집 | pykrx, OpenDartReader | KRX/DART 추상화 라이브러리 (직접 스크래핑 회피) |
| 컨테이너 | Docker Compose (개발) | 로컬 환경 일관성 |
| 백테스팅 | Pandas + NumPy (직접 구현) | vectorbt는 학습곡선 있음, 직접 구현이 명확 |

### 2.2 프로젝트 구조 (모노레포)

```
nps-tracker/
├── docker-compose.yml
├── README.md
├── CLAUDE.md                    # Claude Code 작업 규칙
├── PROJECT_SPEC.md              # 본 문서
│
├── data-collector/              # [Phase 1] Python - KRX/DART 데이터 수집
│   ├── requirements.txt
│   ├── config.py
│   ├── .env.example
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM
│   │   ├── session.py           # 세션 팩토리
│   │   └── init_schema.py       # 스키마 + hypertable 초기화
│   ├── scrapers/
│   │   ├── krx_scraper.py       # pykrx 래퍼
│   │   ├── dart_scraper.py      # DART 5%보유 공시
│   │   ├── backfill.py          # 과거 데이터 일괄 수집
│   │   └── daily_runner.py      # 일별 자동 수집 (스케줄러)
│   └── tests/
│
├── api/                         # [Phase 2] Python - FastAPI 백엔드
│   ├── requirements.txt
│   ├── main.py
│   ├── routers/
│   │   ├── stocks.py
│   │   ├── nps_trades.py
│   │   └── backtest.py
│   ├── schemas/                 # Pydantic 응답 모델
│   ├── services/                # 비즈니스 로직
│   └── tests/
│
├── web/                         # [Phase 3] Next.js 프론트엔드
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx             # 메인: 일별 순매수 상위
│   │   ├── stocks/[ticker]/page.tsx  # 종목별 상세
│   │   └── backtest/page.tsx    # 백테스팅
│   ├── components/
│   ├── lib/
│   └── tests/
│
└── backtest/                    # [Phase 4] Python - 백테스팅 엔진
    ├── strategies.py
    ├── engine.py
    └── tests/
```

---

## 3. 데이터 모델

### 3.1 핵심 테이블

#### `stocks` - 종목 마스터
```python
ticker: str (PK, 6자리, 예: '005930')
name: str  # 삼성전자
market: str  # KOSPI / KOSDAQ
sector: str | None
listing_date: date | None
delisting_date: date | None  # ⚠️ 생존편향 방지에 필수
is_active: bool
```

#### `daily_ohlcv` - 일별 시세 (TimescaleDB hypertable)
```python
trade_date: date (PK)
ticker: str (PK)
open, high, low, close: int  # 원 단위
volume: int
trading_value: int  # 거래대금
market_cap: int | None
shares_outstanding: int | None
```

#### `nps_daily_trades` - 국민연금 일별 매매 (핵심 테이블, hypertable)
```python
trade_date: date (PK)
ticker: str (PK)
net_buy_volume: int   # 순매수 수량 (음수 = 순매도)
net_buy_amount: int   # 순매수 금액 (원)
consecutive_buy_days: int     # 사후 계산: 연속 매수일
buy_intensity_pct: float | None  # 사후 계산: 시총 대비 매수 비중 (%)
created_at: datetime
```

#### `nps_holdings` - 5% 이상 보유 공시 (DART)
```python
id: int (PK, autoincrement)
ticker: str
report_date: date  # 보고 기준일
filing_date: date  # 공시일
shares: int
holding_ratio: float  # 보유 비율 %
purpose: str  # 단순투자/경영참여 등
rcept_no: str (UNIQUE)  # DART 접수번호
```

#### `collection_logs` - 수집 작업 로그
```python
id: int (PK)
job_type: str  # 'daily_trades' | 'ohlcv' | 'holdings'
target_date: date
status: str  # 'success' | 'failed' | 'partial'
rows_inserted: int
error_message: str | None
started_at, completed_at: datetime
```

### 3.2 인덱스 전략

자주 사용되는 쿼리 패턴별로:

```sql
-- "특정 일자의 순매수 상위 종목" (메인 화면)
CREATE INDEX idx_nps_date_amount ON nps_daily_trades (trade_date, net_buy_amount DESC);

-- "특정 종목의 시계열" (상세 화면)
CREATE INDEX idx_nps_ticker_date ON nps_daily_trades (ticker, trade_date);
CREATE INDEX idx_ohlcv_ticker_date ON daily_ohlcv (ticker, trade_date);
```

### 3.3 시계열 설계 핵심

- `daily_ohlcv`, `nps_daily_trades`는 TimescaleDB hypertable로 변환
- chunk_interval = 1 month (5년치 = 60청크, 적정 크기)
- 3개월 이상 청크는 자동 압축 (디스크 70% 절감)
- segmentby = 'ticker' (종목별 시계열 조회 가속)

---

## 4. 기능 사양 (Phase별)

### Phase 1: 데이터 수집 레이어 ⭐ 최우선

#### 1.1 KRX 스크래퍼 (`scrapers/krx_scraper.py`)

**책임:**
- pykrx를 사용해 일별 OHLCV 수집
- pykrx로 일별 투자자별 순매수 (연기금 등) 수집
- 종목 마스터 갱신 (신규 상장/폐지 추적)

**핵심 함수:**
```python
def fetch_daily_ohlcv(target_date: date, market: str = "ALL") -> pd.DataFrame:
    """특정 일자의 전종목 OHLCV"""

def fetch_nps_daily_trades(target_date: date) -> pd.DataFrame:
    """특정 일자의 '연기금 등' 종목별 순매수"""

def fetch_stock_master() -> pd.DataFrame:
    """현재 상장 종목 마스터 (KOSPI + KOSDAQ)"""
```

#### 1.2 DART 스크래퍼 (`scrapers/dart_scraper.py`)

**책임:**
- OpenDartReader로 국민연금공단의 5%이상 보유 공시 조회
- 신규 공시만 증분 수집 (rcept_no UNIQUE 제약으로 중복 방지)

#### 1.3 백필 스크립트 (`scrapers/backfill.py`)

```bash
python -m scrapers.backfill --years 5
```

- 과거 N년치 데이터를 영업일 단위로 순회 수집
- tenacity 기반 재시도 (KRX 일시 장애 대응)
- collection_logs에 진행 상황 기록 → 중단 후 재개 가능

#### 1.4 일별 자동 수집 (`scrapers/daily_runner.py`)

- APScheduler로 매일 18:00 KST 실행
- 당일 데이터 수집 → 시그널 지표 재계산 (consecutive_buy_days, buy_intensity_pct)

### Phase 2: FastAPI 백엔드

#### 2.1 핵심 엔드포인트

```
GET  /api/stocks                                  # 종목 마스터 (페이지네이션)
GET  /api/stocks/{ticker}                         # 종목 상세 + 최근 시세

GET  /api/nps/daily?date=2024-12-30&limit=50     # 일별 순매수 상위 (메인 화면용)
GET  /api/nps/stocks/{ticker}/trades             # 특정 종목의 NPS 매매 시계열
GET  /api/nps/stocks/{ticker}/holdings           # 5% 보유 공시 이력

POST /api/backtest                                # 백테스팅 실행 (비동기 작업)
GET  /api/backtest/{job_id}                       # 결과 조회
```

#### 2.2 응답 캐싱

- "오늘의 순매수 상위" → Redis TTL 1시간
- 종목별 시계열 → ETag 기반 304 응답

### Phase 3: Next.js 프론트엔드

#### 3.1 메인 페이지 (`app/page.tsx`)

- 일자 선택기 (최근 30영업일 드롭다운)
- 순매수 상위 50종목 테이블
  - 컬럼: 순위, 종목명, 종가, 등락률, NPS 순매수 금액, 연속 매수일, 매수 강도(%)
  - 정렬, 필터 (KOSPI/KOSDAQ)
  - 행 클릭 → 상세 페이지로 이동
- 상단 요약: "오늘 NPS 총 순매수액", "순매수 종목 수 vs 순매도 종목 수"

#### 3.2 종목 상세 (`app/stocks/[ticker]/page.tsx`)

- 종목 기본 정보 카드
- 차트 1: 종가 + NPS 일별 순매수 (이중축, 막대+선)
- 차트 2: NPS 누적 순매수 추이 (5% 보유 공시 시점 마커)
- 표: 최근 60영업일 NPS 매매 내역

#### 3.3 백테스팅 페이지 (`app/backtest/page.tsx`)

- 전략 파라미터 입력 폼
- "실행" 버튼 → 비동기 작업 시작
- 결과 시각화: 누적 수익률 곡선 (KOSPI 대비), 통계 카드 (CAGR, MDD, 샤프지수, 승률)

### Phase 4: 백테스팅 엔진

#### 4.1 추종 전략 정의

```python
@dataclass
class FollowStrategy:
    min_consecutive_days: int = 3       # 최소 연속 매수일
    min_net_buy_amount: int = 1_000_000_000  # 최소 순매수 10억원
    min_buy_intensity_pct: float = 0.1  # 최소 매수 강도 0.1%
    holding_period_days: int = 20       # 보유 기간 (영업일)
    entry_lag_days: int = 1             # 시그널 발생 후 N일 뒤 매수 (look-ahead 방지)
    max_positions: int = 10             # 동시 보유 최대 종목 수
    initial_capital: int = 10_000_000   # 초기 자본 1천만원
    transaction_cost_pct: float = 0.25  # 거래비용 0.25% (수수료+세금)
```

#### 4.2 백테스팅 엔진 핵심 원칙

**반드시 준수:**
1. **No look-ahead bias**: `entry_lag_days >= 1` 강제. T일 종가로 매수하려면 T-1일 이전 데이터만 사용
2. **Survivorship bias 방지**: 폐지된 종목도 전략 진입 후 폐지일까지 보유 (폐지 시 -100% 손실 처리)
3. **거래비용 반영**: 매수/매도마다 transaction_cost_pct 차감
4. **현실적 슬리피지**: 매수는 시초가 + 0.1%, 매도는 시초가 - 0.1%

#### 4.3 결과 지표

```python
{
    "total_return_pct": float,
    "cagr_pct": float,                    # 연복리 수익률
    "kospi_excess_return_pct": float,     # KOSPI 대비 알파
    "max_drawdown_pct": float,
    "sharpe_ratio": float,
    "win_rate_pct": float,
    "trades_count": int,
    "equity_curve": list[{date, equity}], # 일별 자산 변화
}
```

---

## 5. 비기능 요구사항

### 5.1 성능

- 메인 페이지(상위 50종목) 초기 로드: < 1초 (서버 응답 200ms 이내)
- 종목 상세 차트(1년치): < 1.5초
- 백테스팅(5년, 10종목): < 30초

### 5.2 데이터 무결성

- 모든 수집 작업은 멱등성 보장 (`INSERT ... ON CONFLICT DO UPDATE`)
- collection_logs로 부분 실패 추적 가능
- 매일 자동 수집 후 행 수가 임계치 미달이면 알림

### 5.3 관측성

- 모든 수집 작업: loguru로 구조화 로그 (JSON)
- 수집 실패 시 에러 메시지를 collection_logs.error_message에 저장
- API 요청 로깅 (FastAPI middleware)

---

## 6. 개발 로드맵 (6주)

| 주차 | 목표 | 산출물 |
|------|------|--------|
| 1 | 인프라 + DB 스키마 | docker-compose 동작, 스키마 생성, 5년치 백필 완료 |
| 2 | 데이터 수집 안정화 | daily_runner 가동, DART 스크래퍼, 시그널 지표 계산 |
| 3 | FastAPI 핵심 API | 메인 화면용 4개 엔드포인트 + 캐싱 |
| 4 | Next.js 메인 + 상세 | 일별 순매수 상위 + 종목별 차트 동작 |
| 5 | 백테스팅 엔진 | 전략 백테스트 결과 페이지 |
| 6 | 통합 테스트 + 배포 | E2E 테스트, Docker 이미지, 면책 고지 |

---

## 7. 면책 및 법적 고지 (UI 필수 노출)

```
본 서비스는 정보 제공 목적이며, 투자 자문이 아닙니다.

• 표시되는 데이터는 한국거래소(KRX)가 공개하는 "연기금 등"
  카테고리의 합산 매매 정보로, 국민연금공단 단독 매매가
  아닙니다.
• 모든 매매 데이터는 장 마감 후(T+1) 기준이며,
  실시간 정보가 아닙니다.
• 과거 매매 패턴이 미래 수익을 보장하지 않습니다.
• 투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다.

데이터 출처: 한국거래소(KRX), 금융감독원 전자공시시스템(DART)
```

---

## 8. 참고 자료

- KRX 정보데이터시스템: https://data.krx.co.kr
- DART 전자공시: https://dart.fss.or.kr
- pykrx GitHub: https://github.com/sharebook-kr/pykrx
- OpenDartReader: https://github.com/FinanceData/OpenDartReader
- TimescaleDB 문서: https://docs.timescale.com

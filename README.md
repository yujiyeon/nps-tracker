# NPS Tracker

국민연금(연기금 등)의 한국 주식시장 매매 데이터를 추적·분석하고, 추종 전략의 유효성을 과거 데이터로 검증하는 웹 애플리케이션.

> **데이터 출처 안내**: KRX는 "국민연금" 단독 데이터를 제공하지 않으며 **"연기금 등" 합산 카테고리**로만 공개합니다. 장 마감 후(T+1) 기준 데이터입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 일별 매매 동향 | KRX "연기금 등" 일별 순매수 상위 종목 시각화 |
| 종목 상세 분석 | 특정 종목의 NPS 매매 시계열 차트 |
| 백테스팅 | "N일 연속 매수 종목을 따라 사면 수익이 났을까?" 전략 검증 |
| 자동 수집 | 매일 07:00 KST 전 영업일 데이터 자동 수집 |

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14 (App Router) · TypeScript · Tailwind CSS · TanStack Query · Recharts |
| 백엔드 | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| DB | PostgreSQL 16 + TimescaleDB (시계열 최적화) |
| 캐시 | Redis 7 (API 응답 TTL 1h, 백테스팅 job 상태) |
| 데이터 수집 | pykrx · OpenDartReader · APScheduler |
| 백테스팅 | Pandas · NumPy |
| 인프라 | Docker Compose (로컬) · Railway (배포) |

---

## 프로젝트 구조

```
nps-tracker/
├── data-collector/     # KRX/DART 데이터 수집 (APScheduler)
├── api/                # FastAPI 백엔드
├── backtest/           # 백테스팅 엔진
├── web/                # Next.js 프론트엔드
└── docker-compose.yml  # 로컬 개발용 (PostgreSQL + Redis)
```

---

## 로컬 개발 환경

### 사전 요구사항

- Docker Desktop
- Python 3.11+
- Node.js 20+

### 빠른 시작

```bash
# 1. 인프라 실행 (PostgreSQL + Redis)
docker compose up -d

# 2. 스키마 초기화
cd data-collector
python -m db.init_schema

# 3. 과거 데이터 백필 (최초 1회, 수십 분 소요)
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
| API 문서 (Swagger) | http://localhost:8000/docs |

### 환경변수

각 서비스의 `.env.example`을 복사해 `.env`를 생성합니다.

```bash
# data-collector/.env, api/.env
DATABASE_URL=postgresql+psycopg2://nps_user:localdevpassword@localhost:5432/nps_tracker
REDIS_URL=redis://localhost:6379/0
DART_API_KEY=your_dart_api_key   # DART 공시 수집 시 필요

# api/.env 추가
ALLOWED_ORIGINS=http://localhost:3000

# web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 데이터 수집 수동 실행

```bash
cd data-collector

# 전 영업일 데이터 즉시 수집
python -m scrapers.daily_runner --now

# 특정 날짜 수집
python -m scrapers.daily_runner --now --date 2026-05-20

# 스케줄러 상시 가동 (매일 07:00 KST 자동 실행)
python -m scrapers.daily_runner
```

---

## 테스트

```bash
# API 통합 테스트
cd api && pytest tests/ -v

# E2E 테스트 (개발 서버 실행 중이어야 함)
cd web && npm run test:e2e
```

---

## 배포

각 서비스에 `railway.toml` 설정이 포함되어 있습니다. Railway에서 아래 5개 서비스를 연결합니다.

| Railway 서비스 | 소스 | 비고 |
|--------------|------|------|
| db | `timescale/timescaledb:latest-pg16` | 포트 5432 |
| redis | Railway 플러그인 | 포트 6379 |
| api | `./api` Dockerfile | |
| web | `./web` Dockerfile | |
| collector | `./data-collector` Dockerfile | 스케줄러 상시 가동 |

프로덕션 환경변수는 `.env.production.example` 참고.

---

## 상세 문서

기술 사양, 데이터 모델, API 명세, 백테스팅 원칙 등 상세 내용은 [PROJECT_SPEC.md](./PROJECT_SPEC.md)를 참고하세요.

---

## 법적 고지

본 서비스는 **정보 제공 목적**이며, 투자 자문이 아닙니다.

- 표시되는 데이터는 KRX의 "연기금 등" 카테고리 **합산 매매 정보**로, 국민연금공단 단독 매매가 아닙니다.
- 모든 매매 데이터는 **장 마감 후(T+1) 기준**이며, 실시간 정보가 아닙니다.
- 과거 매매 패턴이 미래 수익을 보장하지 않습니다.
- 투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다.

한국 자본시장법상 불특정 다수에게 종목을 "추천"하는 행위는 유사투자자문업 신고 대상이 될 수 있습니다. 본 서비스는 "추천 종목", "매수 추천" 등의 표현을 사용하지 않습니다.

**데이터 출처**: 한국거래소(KRX) · 금융감독원 전자공시시스템(DART)

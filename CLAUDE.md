# CLAUDE.md - Claude Code 작업 규칙

> 이 문서는 Claude Code가 본 저장소에서 작업할 때 자동으로 참조하는 규칙입니다.
> 전체 프로젝트 사양은 `PROJECT_SPEC.md`를 먼저 읽어주세요.

## 0. 작업 시작 전 필수 확인

새로운 작업을 시작할 때마다:
1. `PROJECT_SPEC.md`를 먼저 읽어 현재 Phase와 맥락을 파악할 것
2. 관련 디렉토리(`data-collector/`, `api/`, `web/`, `backtest/`)의 기존 코드 탐색
3. 이미 만들어진 모듈을 재사용하거나 확장하는 방식을 우선 고려

## 1. 코딩 컨벤션

### 1.1 Python (data-collector, api, backtest)

- **Python 3.11+** 문법 사용 (`X | None`, `list[T]` 등)
- **타입 힌트 필수**: 모든 함수 시그니처에 타입 힌트 (mypy strict 통과 가능 수준)
- **포매터**: `ruff format` (line-length 100)
- **린터**: `ruff check` (E, F, I, B, UP 룰셋)
- **import 순서**: stdlib → 외부 라이브러리 → 로컬 (`config`, `db`, `scrapers` 등)
- **Pydantic v2 사용**: BaseModel, ConfigDict 활용. v1 문법(`class Config:`) 금지
- **SQLAlchemy 2.0 스타일**: `Mapped[T]`, `mapped_column()` 사용. 레거시 `Column()` 금지
- **로깅**: `loguru` 사용. 표준 `logging` 모듈 직접 사용 금지
- **예외 처리**: 광범위한 `except Exception` 금지. 구체적인 예외 타입 명시

### 1.2 TypeScript / Next.js (web)

- **Next.js 14 App Router** 사용 (`pages/` 디렉토리 금지)
- **Server Components 우선**: 클라이언트 인터랙션 필요할 때만 `'use client'`
- **TypeScript strict mode**: any 금지, 타입 단언(`as`)은 최소화
- **함수형 컴포넌트만**: 클래스 컴포넌트 금지
- **상태관리**: 서버 상태는 TanStack Query, 클라이언트 상태는 Zustand (작은 앱이라면 useState로 충분)
- **스타일링**: Tailwind CSS only. CSS Modules / styled-components 금지
- **컴포넌트 분리**: 한 파일 200줄 초과 시 분리 검토

### 1.3 공통

- **주석은 "왜"를 설명**: "무엇을" 하는지는 코드로 표현. 비즈니스 로직의 의도, 비명백한 결정의 이유만 주석
- **한국어/영어 혼용 정책**:
  - 코드(변수명, 함수명, 클래스명): 영어
  - 주석, docstring: 한국어 (이 프로젝트는 한국 시장 도메인)
  - 사용자 노출 문구(UI, 에러 메시지): 한국어
  - 로그 메시지: 한국어 (운영자가 한국어 사용자)

## 2. 데이터 처리 규칙

### 2.1 데이터 무결성 (절대 위반 금지)

- **모든 수집 작업은 멱등성 보장**: 같은 일자 데이터를 두 번 수집해도 결과가 동일해야 함
  - PostgreSQL: `INSERT ... ON CONFLICT (PK) DO UPDATE` 사용
  - 또는 SQLAlchemy의 `dialect_postgresql.insert(...).on_conflict_do_update(...)`
- **수집 작업은 collection_logs에 기록**: 시작/종료/실패 모두 기록
- **부분 실패 허용**: 1000개 종목 중 5개 실패해도 나머지는 저장. 실패 종목은 로그에 기록

### 2.2 백테스팅 핵심 원칙 (절대 위반 금지)

이 항목은 백테스팅의 신뢰성과 직결되므로 한 줄도 어기지 말 것:

1. **No look-ahead bias**:
   - T일에 매수 결정 시 T-1일까지의 데이터만 사용
   - `entry_lag_days >= 1` 강제 (코드에 assert)
   - 종가 데이터로 매수 시 반드시 다음 영업일 시초가/종가 사용

2. **Survivorship bias 방지**:
   - 백테스팅 시 `stocks.delisting_date`가 있는 종목도 포함
   - 폐지일 도달 시 보유 포지션은 -100% 손실 처리 (혹은 정리매매가 평균 -50%)

3. **거래비용 반영**:
   - 매수: 체결가 × (1 + transaction_cost_pct/100)
   - 매도: 체결가 × (1 - transaction_cost_pct/100)
   - 기본값 0.25% (수수료 0.015% × 2 + 증권거래세 0.18% + 슬리피지)

### 2.3 시계열 쿼리

- 시계열 테이블(`daily_ohlcv`, `nps_daily_trades`) 조회 시 **반드시 `trade_date` 범위 조건 포함**
  - TimescaleDB 청크 프루닝 활용 위해 필수
  - `WHERE trade_date >= '2024-01-01'` 같은 조건 없이 `ticker`로만 조회 금지
- 1년 이상 조회 시 **다운샘플링 검토** (주봉/월봉)

## 3. 파일 구조 규칙

### 3.1 새 파일 생성 시

- 기존 디렉토리 구조를 우선 확인하고 적절한 위치에 배치
- 새 디렉토리 생성 시 `__init__.py` 추가 (Python)
- 1파일 1책임 원칙: 하나의 파일이 여러 도메인을 다루지 않게

### 3.2 모듈 의존성 방향

```
[금지되는 의존성]
db ← scrapers ← daily_runner    ✓ OK
api ← services ← db             ✓ OK
db → scrapers                   ✗ 금지 (db가 scrapers를 import)
web → api 코드                   ✗ 금지 (HTTP로만 통신)
```

## 4. 보안 및 비밀 관리

- **하드코딩 금지**: API 키, 비밀번호, 토큰은 `.env`에서만 로드
- **`.env` 파일 커밋 금지**: `.gitignore`에 등재
- **`.env.example`만 커밋**: 실제 값 대신 placeholder
- **DART_API_KEY 등 외부 API 키는 `config.py`의 Settings를 통해서만 접근**

## 5. 테스트 전략

### 5.1 우선순위

1. **데이터 수집의 멱등성**: 같은 작업 두 번 실행 후 DB 상태 동일성 검증
2. **백테스팅 엔진의 정확성**: 알려진 시나리오(예: 단순 매수 후 보유)로 결과 검증
3. **API 응답 스키마**: Pydantic 모델 직렬화 검증

### 5.2 테스트 도구

- Python: `pytest`, `pytest-asyncio`
- DB 테스트: 별도 테스트 DB 사용 (`nps_tracker_test`), 각 테스트 후 트랜잭션 롤백
- 외부 API(KRX, DART) 호출: `pytest` fixture로 mock
- 프론트엔드: Playwright (E2E), Vitest (단위)

### 5.3 작성하지 않아도 되는 테스트

- 단순 getter/setter
- 외부 라이브러리 자체 동작 (pykrx 함수 호출 결과 등)
- 명백한 글루 코드

## 6. UI/UX 규칙 (Phase 3, web/)

### 6.1 절대 사용 금지 문구

법적 리스크 방지를 위해 다음 표현은 절대 UI에 노출하지 않는다:

| ❌ 금지 | ✅ 권장 |
|---------|---------|
| "추천 종목" | "순매수 상위 종목" |
| "매수 추천" | "매매 정보" |
| "AI가 추천" | "데이터 기반 분석" |
| "수익 보장" | (사용 금지) |
| "확실한 투자처" | (사용 금지) |

### 6.2 면책 고지

- 모든 페이지 푸터에 면책 고지 노출 (PROJECT_SPEC.md §7 전문)
- 백테스팅 결과 페이지 상단에 강조 박스로 추가 고지

### 6.3 데이터 표시 규칙

- 금액: 한국식 단위 ("13.5억원", "1,250만원")
- 등락률: 색상으로 표현 (상승 빨강, 하락 파랑 - 한국 관습)
- 날짜: `YYYY-MM-DD (요일)` 형식
- 항상 데이터 기준 시점 표시: "2024-12-30 장 마감 기준"

## 7. 작업 진행 방식

### 7.1 작업 시작 시

새로운 기능을 구현할 때:
1. PROJECT_SPEC.md에서 해당 Phase 섹션 확인
2. 관련 기존 코드 파악 (`grep -r` 또는 디렉토리 탐색)
3. 영향받는 모듈 식별
4. 작업 계획을 사용자에게 간단히 공유한 후 진행

### 7.2 코드 작성 시

- 한 번에 하나의 모듈/기능에 집중
- 기존 패턴이 있으면 따를 것 (예: 다른 스크래퍼가 어떻게 짜여있는지 먼저 확인)
- 의존성 추가 시 `requirements.txt` / `package.json` 갱신
- 새로운 환경 변수 추가 시 `.env.example` 갱신

### 7.3 커밋 메시지 컨벤션

Conventional Commits 따름:
```
feat(scraper): KRX 일별 OHLCV 수집 함수 추가
fix(backtest): look-ahead bias 방지 로직 수정
chore(deps): pykrx 1.0.51로 업그레이드
docs: PROJECT_SPEC에 백테스팅 지표 정의 추가
```

## 8. 자주 하는 실수 (방지)

- ❌ `print()` 사용 → ✅ `logger.info()` (loguru)
- ❌ 빈 except → ✅ 구체적 예외 + 로그
- ❌ SQL 직접 작성 → ✅ SQLAlchemy ORM (raw SQL은 마이그레이션이나 hypertable 명령에만)
- ❌ 시계열 쿼리에 날짜 범위 누락 → ✅ 반드시 `WHERE trade_date BETWEEN ...`
- ❌ "투자 추천" 표현 → ✅ "정보 제공" 표현
- ❌ datetime.now() → ✅ `datetime.now(ZoneInfo("Asia/Seoul"))` (시간대 명시)
- ❌ float로 금액 처리 → ✅ int (원 단위) 또는 Decimal

## 9. 도움 요청 시

명확하지 않은 요구사항이 있으면 추측하지 말고 질문할 것:
- 비즈니스 로직 결정이 필요한 경우
- PROJECT_SPEC.md에 명시되지 않은 동작
- 보안/법적 영향이 있을 수 있는 결정

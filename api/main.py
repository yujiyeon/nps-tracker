"""FastAPI 애플리케이션 진입점"""
import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from config import settings
from routers import backtest, nps_trades, stocks, investor_recommendation

# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
)

# ──────────────────────────────────────────────
# FastAPI 앱
# ──────────────────────────────────────────────
app = FastAPI(
    title="NPS Tracker API",
    description=(
        "한국 주식시장 '연기금 등' 매매 데이터 분석 플랫폼. "
        "본 API는 정보 제공 목적이며 투자 자문이 아닙니다."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ──────────────────────────────────────────────
# 미들웨어
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """API 요청 로깅 미들웨어"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms:.1f}ms)"
    )
    return response


# ──────────────────────────────────────────────
# 라우터 등록
# ──────────────────────────────────────────────
app.include_router(stocks.router)
app.include_router(nps_trades.router)
app.include_router(backtest.router)
app.include_router(investor_recommendation.router)

# ──────────────────────────────────────────────
# 헬스체크 / 면책 고지
# ──────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "service": "NPS Tracker API",
        "version": "0.1.0",
        "disclaimer": (
            "본 서비스는 정보 제공 목적이며, 투자 자문이 아닙니다. "
            "표시되는 데이터는 KRX의 '연기금 등' 카테고리 합산 매매 정보로, "
            "국민연금공단 단독 매매가 아닙니다. "
            "모든 매매 데이터는 장 마감 후(T+1) 기준이며, 실시간 정보가 아닙니다. "
            "과거 매매 패턴이 미래 수익을 보장하지 않습니다. "
            "투자 결정과 그에 따른 모든 책임은 사용자 본인에게 있습니다."
        ),
        "docs": "/docs",
    }

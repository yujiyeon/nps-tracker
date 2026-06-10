"""
백테스팅 API.

POST /api/backtest          → job_id 반환 (즉시, 비동기 실행)
GET  /api/backtest/{job_id} → 결과 폴링
POST /api/backtest/recommend → 오늘의 추천종목 (날짜 불필요)
"""
import uuid

from fastapi import APIRouter, HTTPException
from loguru import logger

from schemas.backtest import (
    BacktestRequest,
    BacktestResultResponse,
    RecommendRequest,
)
from services import backtest_service, cache_service

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_JOB_TTL = 86400
_JOB_PREFIX = "backtest:job:"


@router.post("", response_model=BacktestResultResponse, status_code=202)
def submit_backtest(req: BacktestRequest) -> BacktestResultResponse:
    """
    백테스팅 실행 요청. 즉시 job_id 반환 후 스레드 풀에서 비동기 실행.

    - entry_lag_days >= 1 강제 (look-ahead bias 방지, PROJECT_SPEC §4.2)
    - 결과는 GET /api/backtest/{job_id}로 폴링
    """
    job_id = str(uuid.uuid4())

    job_data = BacktestResultResponse(
        job_id=job_id,
        status="pending",
        request=req,
    )
    cache_service.set_cached(f"{_JOB_PREFIX}{job_id}", job_data.model_dump(), ttl=_JOB_TTL)

    logger.info(f"백테스팅 job 생성: {job_id} ({req.from_date} ~ {req.to_date})")

    # 백테스팅 엔진을 ThreadPoolExecutor에서 비동기 실행
    backtest_service.submit_backtest(job_id, req.model_dump())

    return job_data


@router.get("/{job_id}", response_model=BacktestResultResponse)
def get_backtest_result(job_id: str) -> BacktestResultResponse:
    """백테스팅 결과 조회. status가 'done'이 될 때까지 폴링."""
    cached = cache_service.get_cached(f"{_JOB_PREFIX}{job_id}")
    if not cached:
        raise HTTPException(status_code=404, detail=f"백테스팅 job을 찾을 수 없습니다: {job_id}")

    return BacktestResultResponse(**cached)


@router.post("/recommend")
def recommend(req: RecommendRequest):
    """[기존 / bandit] 오늘의 추천종목. 기간 파라미터 없이 오늘 기준 1개 종목 선택."""
    return backtest_service.get_today_recommendation(req.model_dump())


@router.post("/recommend-mdp")
def recommend_mdp(req: RecommendRequest):
    """[방향 A / MDP] 포트폴리오 DQN 기반 오늘의 추천. 관망 시 추천 없음 반환 가능."""
    return backtest_service.get_portfolio_recommendation(req.model_dump())
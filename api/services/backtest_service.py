"""
백테스팅 서비스 - engine.py를 API와 연결.

ThreadPoolExecutor로 비동기 실행 후 Redis job 상태 업데이트.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session
from datetime import date
from typing import Any

# backtest 패키지는 프로젝트 루트에 있으므로 sys.path 추가
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backtest.engine import run_backtest, predict_one_day, predict_one_day_mdp  # noqa: E402
from backtest.strategies import FollowStrategy  # noqa: E402

from backtest.dqn_agent import DQNAgent
from backtest import rl_state

# DQN 후보 수 (rl_env / engine 과 동일해야 함)
TOP_K = 50

# 모델 경로 (기존 bandit 모델 / 방향A MDP 모델 — 서로 다른 차원이라 파일 분리)
_MODEL_BANDIT = "../models/dqn_nps_stock_model.pth"
_MODEL_MDP = "../models/dqn_nps_portfolio_model.pth"

# db.session은 스레드 실행 시점에 lazy import (모듈 레벨에서 DB 커넥션 생성 방지)
from services import cache_service

_JOB_TTL = 86400
_JOB_PREFIX = "backtest:job:"

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="backtest")


def _run_in_background(job_id: str, req_data: dict[str, Any]) -> None:
    """
    별도 스레드에서 백테스팅 실행 후 Redis 상태 업데이트.
    예외는 모두 잡아서 'failed' 상태로 기록.
    """
    key = f"{_JOB_PREFIX}{job_id}"

    # 상태를 running으로 변경
    job = cache_service.get_cached(key) or {}
    job["status"] = "running"
    cache_service.set_cached(key, job, ttl=_JOB_TTL)

    from db.session import SessionFactory  # lazy import — DB 연결은 스레드 실행 시점에

    session = SessionFactory()
    try:
        strategy = FollowStrategy(
            min_consecutive_days=req_data["min_consecutive_days"],
            min_net_buy_amount=req_data["min_net_buy_amount"],
            min_buy_intensity_pct=req_data["min_buy_intensity_pct"],
            holding_period_days=req_data["holding_period_days"],
            entry_lag_days=req_data["entry_lag_days"],
            max_positions=req_data["max_positions"],
            initial_capital=req_data["initial_capital"],
            transaction_cost_pct=req_data["transaction_cost_pct"],
            slippage_pct=0.1,  # BacktestRequest에 없으므로 기본값 사용
        )

        from_date = date.fromisoformat(str(req_data["from_date"]))
        to_date = date.fromisoformat(str(req_data["to_date"]))

        agent = DQNAgent(
            state_size=50 * 5,
            action_size=50,
        )

        agent.load(_MODEL_BANDIT)
        agent.epsilon = 0.0

        result = run_backtest(
            strategy=strategy,
            session=session,
            from_date=from_date,
            to_date=to_date,
            agent=agent,
            use_dqn=True,
        )

        #result = run_backtest(strategy, session, from_date, to_date)

        job.update(
            {
                "status": "done",
                "total_return_pct": result.total_return_pct,
                "cagr_pct": result.cagr_pct,
                "max_drawdown_pct": result.max_drawdown_pct,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate_pct": result.win_rate_pct,
                "trades_count": result.trades_count,
                "kospi_excess_return_pct": result.kospi_excess_return_pct,
                "equity_curve": result.equity_curve,
                "error_message": None,
            }
        )
        logger.info(f"백테스팅 완료: {job_id} (수익률 {result.total_return_pct:.2f}%)")

    except (ValueError, AssertionError) as exc:
        logger.warning(f"백테스팅 실패: {job_id} — {exc}")
        job.update({"status": "failed", "error_message": str(exc)})
    except Exception as exc:
        logger.exception(f"백테스팅 예기치 않은 오류: {job_id}")
        job.update({"status": "failed", "error_message": f"서버 오류: {exc}"})
    finally:
        session.close()

    cache_service.set_cached(key, job, ttl=_JOB_TTL)


def submit_backtest(job_id: str, req_data: dict[str, Any]) -> None:
    """백테스팅을 ThreadPoolExecutor에 제출 (논블로킹)."""
    _executor.submit(_run_in_background, job_id, req_data)
    logger.debug(f"백테스팅 job 제출: {job_id}")


def get_today_recommendation(req_data: dict[str, Any]):
    """
    오늘의 추천종목.

    RecommendRequest 는 추천에 필요한 필드만 보낸다(날짜·포지션수·초기자본·
    거래비용·진입지연 없음). FollowStrategy 생성에 필요한 나머지 값은 단일 추천에
    영향이 없으므로 안전한 기본값으로 채운다.
    """
    from db.session import SessionFactory
    from backtest.dqn_agent import DQNAgent
    from backtest.engine import predict_one_day

    session = SessionFactory()

    try:
        strategy = FollowStrategy(
            # 추천에 실제 영향을 주는 후보 필터
            min_consecutive_days=req_data["min_consecutive_days"],
            min_net_buy_amount=req_data["min_net_buy_amount"],
            min_buy_intensity_pct=req_data["min_buy_intensity_pct"],
            holding_period_days=req_data["holding_period_days"],
            # 단일 추천에는 의미 없는 값들 → 기본값 (요청에 없어도 동작)
            entry_lag_days=req_data.get("entry_lag_days", 1),
            max_positions=req_data.get("max_positions", 10),
            initial_capital=req_data.get("initial_capital", 10_000_000),
            transaction_cost_pct=req_data.get("transaction_cost_pct", 0.25),
            slippage_pct=0.1,
        )

        agent = DQNAgent(
            state_size=50 * 5,
            action_size=50,
        )

        agent.load(_MODEL_BANDIT)
        agent.epsilon = 0.0

        return predict_one_day(
            strategy=strategy,
            session=session,
            target_date=date.today(),
            agent=agent,
            market=req_data.get("market"),   # 매매동향 페이지와 동일한 시장 필터
        )

    finally:
        session.close()


def get_portfolio_recommendation(req_data: dict[str, Any]):
    """
    [방향 A / MDP] 포트폴리오 DQN 기반 오늘의 추천.
    기존 get_today_recommendation 과 입력은 같지만, 403차원 MDP 모델을 쓰고
    관망(skip)을 선택하면 '추천 없음'을 반환할 수 있다.
    """
    from db.session import SessionFactory

    session = SessionFactory()

    try:
        strategy = FollowStrategy(
            min_consecutive_days=req_data["min_consecutive_days"],
            min_net_buy_amount=req_data["min_net_buy_amount"],
            min_buy_intensity_pct=req_data["min_buy_intensity_pct"],
            holding_period_days=req_data["holding_period_days"],
            entry_lag_days=req_data.get("entry_lag_days", 1),
            max_positions=req_data.get("max_positions", 10),
            initial_capital=req_data.get("initial_capital", 10_000_000),
            transaction_cost_pct=req_data.get("transaction_cost_pct", 0.25),
            slippage_pct=0.1,
        )

        agent = DQNAgent(
            state_size=rl_state.state_size(TOP_K),   # 403
            action_size=rl_state.action_size(TOP_K), # 51 (관망 포함)
        )

        agent.load(_MODEL_MDP)
        agent.epsilon = 0.0

        return predict_one_day_mdp(
            strategy=strategy,
            session=session,
            target_date=date.today(),
            agent=agent,
            market=req_data.get("market"),
        )

    finally:
        session.close()
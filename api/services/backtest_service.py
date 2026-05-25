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

# backtest 패키지는 프로젝트 루트에 있으므로 sys.path 추가
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backtest.engine import run_backtest  # noqa: E402
from backtest.strategies import FollowStrategy  # noqa: E402

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

        result = run_backtest(strategy, session, from_date, to_date)

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

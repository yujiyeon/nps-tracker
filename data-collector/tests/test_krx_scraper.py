"""
KRX 스크래퍼 단위 테스트.

외부 API 호출은 mock으로 대체.
실제 pykrx 호출 여부가 아닌 데이터 변환 로직을 검증.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scrapers.krx_scraper import (
    NPS_INVESTOR,
    fetch_daily_ohlcv,
    fetch_nps_daily_trades,
)


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """pykrx get_market_ohlcv_by_ticker 응답 샘플"""
    return pd.DataFrame(
        {
            "시가": [70000, 45000],
            "고가": [71000, 46000],
            "저가": [69000, 44000],
            "종가": [70500, 45500],
            "거래량": [10000000, 5000000],
            "거래대금": [700000000000, 225000000000],
        },
        index=pd.Index(["005930", "000660"], name="ticker"),
    )


@pytest.fixture
def sample_cap_df() -> pd.DataFrame:
    """pykrx get_market_cap_by_ticker 응답 샘플"""
    return pd.DataFrame(
        {
            "시가총액": [420000000000000, 30000000000000],
            "상장주식수": [5969782550, 728002365],
        },
        index=pd.Index(["005930", "000660"], name="ticker"),
    )


@pytest.fixture
def sample_nps_df() -> pd.DataFrame:
    """pykrx get_market_net_purchases_of_equities_by_ticker 응답 샘플"""
    return pd.DataFrame(
        {
            "순매수거래량": [500000, -200000],
            "순매수거래대금": [35000000000, -9000000000],
        },
        index=pd.Index(["005930", "000660"], name="ticker"),
    )


class TestFetchDailyOhlcv:
    @patch("scrapers.krx_scraper.stock")
    def test_정상_수집(self, mock_stock, sample_ohlcv_df, sample_cap_df):
        mock_stock.get_market_ohlcv_by_ticker.return_value = sample_ohlcv_df
        mock_stock.get_market_cap_by_ticker.return_value = sample_cap_df

        result = fetch_daily_ohlcv(date(2024, 12, 30))

        assert not result.empty
        # KOSPI + KOSDAQ 각 2종목 = 4개 행 (중복 없음)
        assert len(result) == 4
        assert "open" in result.columns
        assert "market_cap" in result.columns
        # int 타입 확인
        assert result["close"].dtype == int

    @patch("scrapers.krx_scraper.stock")
    def test_휴장일_빈_DataFrame(self, mock_stock):
        mock_stock.get_market_ohlcv_by_ticker.return_value = pd.DataFrame()

        result = fetch_daily_ohlcv(date(2024, 12, 25))

        assert result.empty

    @patch("scrapers.krx_scraper.stock")
    def test_종가_0_종목_제외(self, mock_stock, sample_ohlcv_df, sample_cap_df):
        # 종가 0인 종목 추가 (거래 없음)
        df_with_zero = sample_ohlcv_df.copy()
        df_with_zero.loc["999999"] = [0, 0, 0, 0, 0, 0]
        mock_stock.get_market_ohlcv_by_ticker.return_value = df_with_zero
        mock_stock.get_market_cap_by_ticker.return_value = sample_cap_df

        result = fetch_daily_ohlcv(date(2024, 12, 30))

        # 종가 0인 종목은 포함되지 않아야 함
        assert all(result["close"] > 0)


class TestFetchNpsDailyTrades:
    @patch("scrapers.krx_scraper.stock")
    def test_정상_수집(self, mock_stock, sample_nps_df):
        mock_stock.get_market_net_purchases_of_equities_by_ticker.return_value = sample_nps_df

        result = fetch_nps_daily_trades(date(2024, 12, 30))

        assert not result.empty
        assert "net_buy_volume" in result.columns
        assert "net_buy_amount" in result.columns
        # NPS_INVESTOR로 호출 확인
        mock_stock.get_market_net_purchases_of_equities_by_ticker.assert_called_with(
            "20241230", "20241230", "KOSPI", NPS_INVESTOR
        )

    @patch("scrapers.krx_scraper.stock")
    def test_순매수_0_종목_제외(self, mock_stock):
        df_all_zero = pd.DataFrame(
            {"순매수거래량": [0, 0], "순매수거래대금": [0, 0]},
            index=pd.Index(["005930", "000660"], name="ticker"),
        )
        mock_stock.get_market_net_purchases_of_equities_by_ticker.return_value = df_all_zero

        result = fetch_nps_daily_trades(date(2024, 12, 30))

        assert result.empty

    @patch("scrapers.krx_scraper.stock")
    def test_음수_순매도_포함(self, mock_stock, sample_nps_df):
        """순매도(음수)도 DB에 저장되어야 함"""
        mock_stock.get_market_net_purchases_of_equities_by_ticker.return_value = sample_nps_df

        result = fetch_nps_daily_trades(date(2024, 12, 30))

        # 음수 값도 포함 확인
        assert (result["net_buy_volume"] < 0).any()

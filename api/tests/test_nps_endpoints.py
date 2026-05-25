"""
NPS 매매 API 통합 테스트.

실제 nps_tracker_test DB에 픽스처 데이터를 넣고
API 응답 스키마·비즈니스 로직을 검증합니다.
"""
from datetime import date


class TestNpsDailyEndpoint:
    def test_최신일_자동_선택(self, client, seed_data):
        """`trade_date` 미지정 시 가장 최근 수집일 반환."""
        res = client.get("/api/nps/daily?limit=10")
        assert res.status_code == 200
        body = res.json()
        assert body["trade_date"] == str(seed_data["today"])

    def test_응답_스키마_필드_존재(self, client, seed_data):
        """응답에 필수 필드가 모두 포함돼야 한다."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&limit=10")
        assert res.status_code == 200
        body = res.json()

        assert "trade_date" in body
        assert "close_date" in body
        assert "total_net_buy_amount" in body
        assert "net_buy_count" in body
        assert "net_sell_count" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_순매수_종목_수_집계(self, client, seed_data):
        """net_buy_amount > 0 인 종목만 net_buy_count에 포함."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&limit=10")
        body = res.json()
        # 픽스처: 삼성전자·SK하이닉스 순매수(2개), 현대차 순매도(1개)
        assert body["net_buy_count"] == 2
        assert body["net_sell_count"] == 1

    def test_items_순매수금액_내림차순(self, client, seed_data):
        """items는 net_buy_amount 내림차순으로 정렬돼야 한다."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&limit=10")
        amounts = [item["net_buy_amount"] for item in res.json()["items"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_item_필드_검증(self, client, seed_data):
        """각 item에 필수 필드가 있어야 한다."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&limit=10")
        item = res.json()["items"][0]
        for field in ["rank", "ticker", "name", "market", "net_buy_amount",
                      "net_buy_volume", "consecutive_buy_days"]:
            assert field in item, f"필드 누락: {field}"

    def test_종가_close_date_기준(self, client, seed_data):
        """close는 trade_date가 아닌 close_date(최신 OHLCV) 기준이어야 한다."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&limit=10")
        body = res.json()
        # 픽스처에서 삼성전자 today close = 61000
        samsung = next(i for i in body["items"] if i["ticker"] == "005930")
        assert samsung["close"] == 61000

    def test_데이터_없는_날짜_404(self, client):
        """데이터가 없는 날짜 조회 시 404 반환. seed_data 불필요 — 빈 DB에서 검증."""
        res = client.get("/api/nps/daily?date=2000-01-01&limit=10")
        assert res.status_code == 404

    def test_시장_필터_KOSPI(self, client, seed_data):
        """market=KOSPI 필터 시 KOSPI 종목만 반환."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}&market=KOSPI&limit=10")
        assert res.status_code == 200
        for item in res.json()["items"]:
            assert item["market"] == "KOSPI"

    def test_data_notice_포함(self, client, seed_data):
        """법적 고지(data_notice) 필드가 응답에 포함돼야 한다."""
        res = client.get(f"/api/nps/daily?date={seed_data['today']}")
        body = res.json()
        assert "data_notice" in body
        assert "연기금 등" in body["data_notice"]
        assert "T+1" in body["data_notice"]


class TestNpsTradeTimeseriesEndpoint:
    def test_정상_조회(self, client, seed_data):
        res = client.get(
            f"/api/nps/stocks/005930/trades"
            f"?from_date={seed_data['prev']}&to_date={seed_data['today']}"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ticker"] == "005930"
        assert body["name"] == "삼성전자"
        assert len(body["items"]) >= 1

    def test_없는_종목_404(self, client, seed_data):
        res = client.get("/api/nps/stocks/XXXXXX/trades")
        assert res.status_code == 404

    def test_timeseries_item_필드(self, client, seed_data):
        res = client.get(
            f"/api/nps/stocks/005930/trades"
            f"?from_date={seed_data['today']}&to_date={seed_data['today']}"
        )
        item = res.json()["items"][0]
        for field in ["trade_date", "net_buy_amount", "net_buy_volume",
                      "consecutive_buy_days"]:
            assert field in item


class TestStocksEndpoint:
    def test_종목_목록_조회(self, client, seed_data):
        res = client.get("/api/stocks?page=1&page_size=10")
        assert res.status_code == 200
        body = res.json()
        assert "total" in body
        assert "items" in body
        assert body["total"] >= 3

    def test_종목_상세_조회(self, client, seed_data):
        res = client.get("/api/stocks/005930")
        assert res.status_code == 200
        body = res.json()
        assert body["stock"]["ticker"] == "005930"
        assert body["stock"]["name"] == "삼성전자"
        assert "ohlcv" in body

    def test_없는_종목_404(self, client, seed_data):
        res = client.get("/api/stocks/XXXXXX")
        assert res.status_code == 404


class TestBacktestEndpoint:
    def test_job_생성_202(self, client, seed_data):
        """POST /api/backtest는 202를 반환하고 job_id를 포함해야 한다."""
        res = client.post("/api/backtest", json={
            "from_date": "2026-01-01",
            "to_date": "2026-05-06",
            "min_consecutive_days": 3,
            "min_net_buy_amount": 1000000000,
            "min_buy_intensity_pct": 0.1,
            "holding_period_days": 20,
            "entry_lag_days": 1,
            "max_positions": 10,
            "initial_capital": 10000000,
            "transaction_cost_pct": 0.25,
        })
        assert res.status_code == 202
        body = res.json()
        assert "job_id" in body
        assert body["status"] == "pending"

    def test_look_ahead_bias_거부(self, client, seed_data):
        """entry_lag_days=0 은 422 유효성 오류여야 한다 (Pydantic ge=1)."""
        res = client.post("/api/backtest", json={
            "from_date": "2026-01-01",
            "to_date": "2026-05-06",
            "min_consecutive_days": 3,
            "min_net_buy_amount": 1000000000,
            "min_buy_intensity_pct": 0.1,
            "holding_period_days": 20,
            "entry_lag_days": 0,
            "max_positions": 10,
            "initial_capital": 10000000,
            "transaction_cost_pct": 0.25,
        })
        assert res.status_code == 422

    def test_job_결과_폴링(self, client, seed_data):
        """GET /api/backtest/{job_id} 가 job 상태를 반환해야 한다."""
        post_res = client.post("/api/backtest", json={
            "from_date": "2026-01-01",
            "to_date": "2026-05-06",
            "min_consecutive_days": 3,
            "min_net_buy_amount": 1000000000,
            "min_buy_intensity_pct": 0.1,
            "holding_period_days": 20,
            "entry_lag_days": 1,
            "max_positions": 10,
            "initial_capital": 10000000,
            "transaction_cost_pct": 0.25,
        })
        job_id = post_res.json()["job_id"]
        get_res = client.get(f"/api/backtest/{job_id}")
        assert get_res.status_code == 200
        assert get_res.json()["job_id"] == job_id

    def test_없는_job_404(self, client):
        res = client.get("/api/backtest/nonexistent-job-id")
        assert res.status_code == 404

from datetime import date

from pydantic import BaseModel, ConfigDict


class StockItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    market: str
    sector: str | None
    listing_date: date | None
    delisting_date: date | None
    is_active: bool


class OhlcvItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_date: date
    open: int
    high: int
    low: int
    close: int
    volume: int
    trading_value: int
    market_cap: int | None
    shares_outstanding: int | None


class StockDetailResponse(BaseModel):
    stock: StockItem
    # 최근 60 영업일 OHLCV
    ohlcv: list[OhlcvItem]


class StockListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[StockItem]

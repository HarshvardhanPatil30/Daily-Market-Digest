from datetime import date, datetime

import pytest

from services import market_data


class FakeFrame:
    def __init__(self, days):
        self.index = [datetime.combine(day, datetime.min.time()) for day in days]
        self.iloc = self

    def __len__(self):
        return len(self.index)

    def __getitem__(self, index):
        return {"Close": 100.0}


class FakeTicker:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def history(self, **kwargs):
        self.calls.append(kwargs)
        return self.frame


class FakeYFinance:
    def __init__(self, frame):
        self.ticker = FakeTicker(frame)

    def Ticker(self, symbol):
        return self.ticker


def test_index_fetch_fails_if_provider_row_is_not_requested_date(monkeypatch):
    target = date(2026, 10, 27)
    fake = FakeYFinance(FakeFrame([date(2026, 10, 28)]))
    monkeypatch.setattr(market_data, "require_yfinance", lambda: fake)

    with pytest.raises(RuntimeError, match="No uniquely verified Nifty 50 session"):
        market_data.fetch_indexes(target)

    assert fake.ticker.calls[0]["end"] == "2026-10-28"

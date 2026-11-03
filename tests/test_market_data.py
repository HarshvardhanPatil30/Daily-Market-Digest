from datetime import date

import pandas as pd
import pytest

from services import market_data


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

    fake_frame = pd.DataFrame(
        {"Close": [100.0]},
        index=pd.to_datetime(["2026-10-28"]),
    )

    fake = FakeYFinance(fake_frame)
    monkeypatch.setattr(market_data, "require_yfinance", lambda: fake)

    with pytest.raises(RuntimeError, match="No uniquely verified Nifty 50 session"):
        market_data.fetch_indexes(target)

    assert fake.ticker.calls[0]["end"] == "2026-10-28"
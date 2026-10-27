from datetime import date, datetime, timedelta, timezone
import math
from models.schemas import IndexSnapshot, StockMove

def calculate_change(close, previous):
    try:
        close, previous = float(close), float(previous)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("finite non-negative close and positive previous close are required") from exc
    if not math.isfinite(close) or not math.isfinite(previous) or close < 0 or previous <= 0:
        raise ValueError("finite non-negative close and positive previous close are required")
    change = close - previous
    percent = change / previous * 100
    if not math.isfinite(change) or not math.isfinite(percent):
        raise ValueError("price change must be finite")
    return round(change, 2), round(percent, 2)

def validate_indexes(indexes, trading_date: date):
    expected = {"Nifty 50", "BSE Sensex"}
    if len(indexes) != 2 or {i.name for i in indexes} != expected: return False, "Exactly one Nifty 50 and one BSE Sensex record are required"
    if any(i.market_date != trading_date or not math.isfinite(i.close) or i.close <= 0 or not math.isfinite(i.previous_close) or i.previous_close <= 0 for i in indexes): return False, "Index records are inconsistent or invalid"
    return True, ""

def validate_moves(moves, trading_date: date, universe):
    invalid = [m.symbol for m in moves if m.market_date != trading_date or m.symbol not in universe or not math.isfinite(m.close) or m.close <= 0 or not math.isfinite(m.percent_change)]
    return not invalid, "Invalid constituent or market-date mismatch: " + ", ".join(invalid)

def is_stale(retrieved_at: datetime, hours=36):
    if retrieved_at.tzinfo is None: retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - retrieved_at.astimezone(timezone.utc) > timedelta(hours=hours)

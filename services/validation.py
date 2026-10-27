from datetime import date, datetime, timedelta, timezone
from models.schemas import IndexSnapshot, StockMove

def calculate_change(close, previous):
    if close is None or previous is None or close < 0 or previous <= 0: raise ValueError("non-negative close and positive previous close are required")
    change = float(close) - float(previous)
    return round(change, 2), round(change / float(previous) * 100, 2)

def validate_indexes(indexes, trading_date: date):
    if len(indexes) < 2: return False, "Both Nifty 50 and BSE Sensex are required"
    if any(i.market_date != trading_date or i.close <= 0 for i in indexes): return False, "Index records are inconsistent or invalid"
    return True, ""

def validate_moves(moves, trading_date: date, universe):
    invalid = [m.symbol for m in moves if m.market_date != trading_date or m.symbol not in universe or m.close <= 0]
    return not invalid, "Invalid constituent or market-date mismatch: " + ", ".join(invalid)

def is_stale(retrieved_at: datetime, hours=36):
    if retrieved_at.tzinfo is None: retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - retrieved_at.astimezone(timezone.utc) > timedelta(hours=hours)

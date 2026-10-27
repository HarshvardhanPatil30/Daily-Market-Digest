from services.market_data import fetch_movers, nifty_universe
from services.validation import validate_moves
class NSEMoversAgent:
    def run(self,target_date):
        moves=fetch_movers(target_date); ok,msg=validate_moves(moves,target_date,nifty_universe())
        if not ok: raise ValueError(msg)
        return sorted([m for m in moves if m.percent_change > 0],key=lambda m:m.percent_change,reverse=True)[:5], sorted([m for m in moves if m.percent_change < 0],key=lambda m:m.percent_change)[:5]

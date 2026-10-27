from services.market_data import fetch_indexes
class MarketDataAgent:
    def run(self, target_date): return fetch_indexes(target_date)

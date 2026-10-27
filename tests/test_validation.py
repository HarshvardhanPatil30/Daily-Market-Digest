from datetime import date,datetime,timezone,timedelta
from services.demo_data import demo_payload,DEMO_UNIVERSE
from services.validation import validate_indexes,validate_moves,is_stale
def test_demo_records_validate():
    indexes,moves,_=demo_payload(); assert validate_indexes(indexes,indexes[0].market_date)[0]; assert validate_moves(moves,indexes[0].market_date,DEMO_UNIVERSE)[0]
def test_stale(): assert is_stale(datetime.now(timezone.utc)-timedelta(days=2))

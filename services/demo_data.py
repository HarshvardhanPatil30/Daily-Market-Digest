from datetime import date, datetime, timezone
from models.schemas import IndexSnapshot, StockMove, NewsArticle
from services.validation import calculate_change

DEMO_UNIVERSE = {"ALPHACEM.NS", "BRAVOBANK.NS", "CRESCENT.NS", "DELTAIT.NS", "EVEREST.NS", "FALCON.NS", "GANGES.NS", "HORIZON.NS", "INDIGO.NS", "JASMINE.NS"}
def demo_payload(day=None):
    day=day or date(2026,10,20); now=datetime.now(timezone.utc)
    def idx(n,s,c,p):
        ch,pc=calculate_change(c,p); return IndexSnapshot(n,s,c,p,ch,pc,day,"Synthetic demo fixture",now)
    values=[("Alpha Cement","ALPHACEM.NS",402.5,12.5,3.21),("Bravo Bank","BRAVOBANK.NS",611.2,15.8,2.65),("Crescent","CRESCENT.NS",921.0,17.4,1.93),("Delta IT","DELTAIT.NS",1455,19,1.32),("Everest","EVEREST.NS",254,2.8,1.11),("Falcon","FALCON.NS",881,-20.5,-2.27),("Ganges","GANGES.NS",1120,-21.5,-1.88),("Horizon","HORIZON.NS",405,-6.8,-1.65),("Indigo","INDIGO.NS",730,-9.3,-1.26),("Jasmine","JASMINE.NS",315,-3,-0.94)]
    moves=[StockMove(n,s,c,ch,pct,day,"Synthetic demo fixture") for n,s,c,ch,pct in values]
    articles=[NewsArticle("DEMO: Domestic equities close with mixed sector performance","https://example.com/demo/markets","Demo Financial Wire",now,"Indian equities",now,"Synthetic demonstration headline; not real news."),NewsArticle("DEMO: Investors review upcoming macroeconomic data","https://example.com/demo/macro","Demo Business Journal",now,"macroeconomics",now,"Synthetic demonstration headline; not real news."),NewsArticle("DEMO: Alpha Cement publishes a fictional operational update","https://example.com/demo/company","Demo Corporate News",now,"company",now,"Synthetic demonstration headline; not real news.")]
    return [idx("Nifty 50","^NSEI",24831.40,24680.10),idx("BSE Sensex","^BSESN",81044.11,80571.21)],moves,articles

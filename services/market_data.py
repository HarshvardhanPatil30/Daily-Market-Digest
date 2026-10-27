"""Public-data adapters. They never manufacture live figures."""
from datetime import datetime, timezone
from services.validation import calculate_change
from models.schemas import IndexSnapshot, StockMove

INDEX_SYMBOLS={"Nifty 50":"^NSEI", "BSE Sensex":"^BSESN"}

def require_yfinance():
    try: import yfinance as yf; return yf
    except ImportError as exc: raise RuntimeError("yfinance is not installed. Install requirements.txt or use --demo.") from exc

def fetch_indexes(target_date):
    yf=require_yfinance(); found=[]
    for name,symbol in INDEX_SYMBOLS.items():
        # yfinance's end bound is exclusive: request only the target session.
        frame=yf.Ticker(symbol).history(start=str(target_date), end=str(target_date.fromordinal(target_date.toordinal()+1)), auto_adjust=False)
        if len(frame) != 1 or frame.index[0].date() != target_date:
            raise RuntimeError(f"No uniquely verified {name} session for {target_date}")
        history=yf.Ticker(symbol).history(period="10d", auto_adjust=False)
        row=frame.iloc[0]; prior=history[history.index.date < target_date]
        if prior.empty: raise RuntimeError(f"Missing prior close for {name}")
        close=float(row["Close"]); previous=float(prior.iloc[-1]["Close"]); change,pct=calculate_change(close,previous)
        found.append(IndexSnapshot(name,symbol,close,previous,change,pct,target_date,"Yahoo Finance",datetime.now(timezone.utc)))
    return found

def nifty_universe():
    # Defensible bundled reference, refreshed against NSE's published list when available.
    return {"ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS","BEL.NS","BHARTIARTL.NS","CIPLA.NS","COALINDIA.NS","DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS","HDFCLIFE.NS","HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS","JIOFIN.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS","SBIN.NS","SHRIRAMFIN.NS","SUNPHARMA.NS","TATACONSUM.NS","TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS","TRENT.NS","ULTRACEMCO.NS","WIPRO.NS"}

def fetch_movers(target_date):
    yf=require_yfinance(); universe=sorted(nifty_universe()); frame=yf.download(universe,start=str(target_date),end=str(target_date.fromordinal(target_date.toordinal()+1)),group_by="ticker",progress=False,auto_adjust=False,threads=True)
    moves=[]; missing=[]
    for symbol in universe:
        try:
            item=frame[symbol].dropna(subset=["Close"])
            if len(item) != 1 or item.index[0].date() != target_date:
                missing.append(symbol); continue
            hist=yf.Ticker(symbol).history(period="10d",auto_adjust=False); prior=hist[hist.index.date < target_date]
            if prior.empty:
                missing.append(symbol); continue
            close=float(item.iloc[0]["Close"]); previous=float(prior.iloc[-1]["Close"]); change,pct=calculate_change(close,previous)
            moves.append(StockMove(symbol.removesuffix(".NS"),symbol,close,change,pct,target_date,"Yahoo Finance"))
        except (KeyError, ValueError, TypeError, OverflowError):
            missing.append(symbol)
    if missing:
        raise RuntimeError(
            f"Incomplete Nifty 50 data for {target_date}: {len(missing)}/{len(universe)} "
            "constituents could not be verified; refusing to publish partial mover rankings"
        )
    if len(moves) != len(universe): raise RuntimeError("No complete verified Nifty 50 constituent set was returned")
    return moves

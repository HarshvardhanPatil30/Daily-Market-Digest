
"""Public-data adapters. They never manufacture live figures."""

from datetime import datetime, timezone, timedelta

from services.validation import calculate_change
from models.schemas import IndexSnapshot, StockMove


INDEX_SYMBOLS = {
    "Nifty 50": "^NSEI",
    "BSE Sensex": "^BSESN",
}


def require_yfinance():
    try:
        import yfinance as yf
        return yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is not installed. Install requirements.txt or use --demo."
        ) from exc


def latest_verified_session(target_date):
    """
    Find the latest date on or before target_date for which both
    Nifty 50 and Sensex have verified closing-price data.

    This prevents early-morning runs from requesting a trading
    session that has not happened yet.
    """
    yf = require_yfinance()

    start_date = target_date - timedelta(days=30)
    end_date = target_date + timedelta(days=1)

    available_dates = []

    for name, symbol in INDEX_SYMBOLS.items():
        history = yf.Ticker(symbol).history(
            start=str(start_date),
            end=str(end_date),
            auto_adjust=False,
        )

        if history.empty:
            raise RuntimeError(
                f"No recent market history returned for {name} ({symbol})"
            )

        history = history.dropna(subset=["Close"])

        dates = {
            timestamp.date()
            for timestamp in history.index
            if timestamp.date() <= target_date
        }

        if not dates:
            raise RuntimeError(
                f"No verified trading session found for {name} "
                f"on or before {target_date}"
            )

        available_dates.append(dates)

    common_dates = set.intersection(*available_dates)

    if not common_dates:
        raise RuntimeError(
            f"No common verified Nifty 50 and Sensex session "
            f"found on or before {target_date}"
        )

    session_date = max(common_dates)

    return session_date


def fetch_indexes(target_date):
    """
    Fetch Nifty 50 and Sensex closing prices for the exact
    verified target_date, together with their previous closes.
    """
    yf = require_yfinance()
    found = []

    start_date = target_date - timedelta(days=15)
    end_date = target_date + timedelta(days=1)

    for name, symbol in INDEX_SYMBOLS.items():
        history = yf.Ticker(symbol).history(
            start=str(start_date),
            end=str(end_date),
            auto_adjust=False,
        )

        if history.empty:
            raise RuntimeError(
                f"No market history returned for {name}"
            )

        history = history.dropna(subset=["Close"])

        target_rows = history[
            history.index.date == target_date
        ]

        if len(target_rows) != 1:
            raise RuntimeError(
                f"No uniquely verified {name} session for {target_date}"
            )

        prior = history[
            history.index.date < target_date
        ]

        if prior.empty:
            raise RuntimeError(
                f"Missing prior close for {name}"
            )

        row = target_rows.iloc[0]
        previous_row = prior.iloc[-1]

        close = float(row["Close"])
        previous = float(previous_row["Close"])

        change, pct = calculate_change(close, previous)

        found.append(
            IndexSnapshot(
                name,
                symbol,
                close,
                previous,
                change,
                pct,
                target_date,
                "Yahoo Finance",
                datetime.now(timezone.utc),
            )
        )

    return found


def nifty_universe():
    # Defensible bundled reference, refreshed against NSE's published list when available.
    return {
        "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS",
        "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS",
        "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS",
        "BHARTIARTL.NS", "CIPLA.NS", "COALINDIA.NS",
        "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS",
        "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
        "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS",
        "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS",
        "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS",
        "KOTAKBANK.NS", "LT.NS", "M&M.NS",
        "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
        "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS",
        "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS",
        "SUNPHARMA.NS", "TATACONSUM.NS", "TMPV.NS",
        "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
        "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS",
        "WIPRO.NS",
    }


def fetch_movers(target_date):
    """
    Fetch all Nifty 50 constituent data for the exact same
    verified session used by fetch_indexes().
    """
    yf = require_yfinance()

    universe = sorted(nifty_universe())

    frame = yf.download(
        universe,
        start=str(target_date),
        end=str(target_date + timedelta(days=1)),
        group_by="ticker",
        progress=False,
        auto_adjust=False,
        threads=True,
    )

    if frame.empty:
        raise RuntimeError(
            f"No Nifty 50 constituent data returned for {target_date}"
        )

    moves = []
    missing = []

    for symbol in universe:
        try:
            item = frame[symbol].dropna(subset=["Close"])

            if (
                len(item) != 1
                or item.index[0].date() != target_date
            ):
                missing.append(symbol)
                continue

            hist = yf.Ticker(symbol).history(
                period="10d",
                auto_adjust=False,
            )

            prior = hist[
                hist.index.date < target_date
            ]

            if prior.empty:
                missing.append(symbol)
                continue

            close = float(item.iloc[0]["Close"])
            previous = float(prior.iloc[-1]["Close"])

            change, pct = calculate_change(close, previous)

            moves.append(
                StockMove(
                    symbol.removesuffix(".NS"),
                    symbol,
                    close,
                    change,
                    pct,
                    target_date,
                    "Yahoo Finance",
                )
            )

        except (KeyError, ValueError, TypeError, OverflowError):
            missing.append(symbol)

    if missing:
        raise RuntimeError(
            f"Incomplete Nifty 50 data for {target_date}: "
            f"{len(missing)}/{len(universe)} constituents "
            "could not be verified; refusing to publish "
            "partial mover rankings"
        )

    if len(moves) != len(universe):
        raise RuntimeError(
            "No complete verified Nifty 50 constituent set was returned"
        )

    return moves

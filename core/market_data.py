"""
Market data retrieval.
Resolves ISINs to Yahoo Finance tickers and fetches latest prices + FX rates.
"""

import time
import requests
import yfinance as yf
import pandas as pd
from functools import lru_cache
from typing import Optional


# ---------------------------------------------------------------------------
# ISIN → Ticker resolution
# ---------------------------------------------------------------------------

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"


def isin_to_ticker_openfigi(isin: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Query OpenFIGI (free tier, no key required up to rate limits) to resolve
    ISIN → ticker.  Returns the first equity/ETF result found.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    payload = [{"idType": "ID_ISIN", "idValue": isin}]
    try:
        resp = requests.post(OPENFIGI_URL, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or "data" not in data[0]:
            return None
        for item in data[0]["data"]:
            ticker = item.get("ticker")
            exch = item.get("exchCode", "")
            if ticker and exch in ("US", "UW", "UN", "UA", "UT", "UF", ""):
                return ticker
        # Fall back to first ticker regardless of exchange
        return data[0]["data"][0].get("ticker")
    except Exception:
        return None


@lru_cache(maxsize=256)
def resolve_ticker(isin: str, openfigi_key: Optional[str] = None) -> Optional[str]:
    """
    Try multiple strategies to get a Yahoo Finance ticker from an ISIN.
    Results are cached for the session lifetime.
    """
    # Strategy 1: OpenFIGI
    ticker = isin_to_ticker_openfigi(isin, openfigi_key)
    if ticker:
        # Validate against yfinance
        info = yf.Ticker(ticker).fast_info
        try:
            if info.last_price and info.last_price > 0:
                return ticker
        except Exception:
            pass

    # Strategy 2: yfinance direct ISIN lookup (works for some ISINs)
    try:
        tk = yf.Ticker(isin)
        price = tk.fast_info.last_price
        if price and price > 0:
            return isin
    except Exception:
        pass

    return ticker  # return best guess even if unvalidated


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------

def fetch_latest_price(ticker: str) -> Optional[float]:
    """Fetch the most recent closing price for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        price = tk.fast_info.last_price
        if price and price > 0:
            return float(price)
        # Fallback: last row of 5-day history
        hist = tk.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def fetch_fx_rate(from_ccy: str, to_ccy: str) -> Optional[float]:
    """
    Fetch FX rate from_ccy → to_ccy using Yahoo Finance pairs (e.g. USDCHF=X).
    Returns 1.0 if currencies are equal.
    """
    if from_ccy == to_ccy:
        return 1.0
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        tk = yf.Ticker(pair)
        rate = tk.fast_info.last_price
        if rate and rate > 0:
            return float(rate)
        hist = tk.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Portfolio enrichment
# ---------------------------------------------------------------------------

def enrich_positions(
    positions: pd.DataFrame,
    target_currency: str = "USD",
    openfigi_key: Optional[str] = None,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Given a positions DataFrame (from parser.compute_positions), resolve tickers,
    fetch latest prices, convert to target_currency, and compute P&L.

    Returns enriched DataFrame with additional columns:
        ticker, latest_price, price_currency, fx_rate, latest_price_converted,
        market_value, cost_basis_total, pnl, pnl_pct
    """
    results = []
    n = len(positions)

    fx_cache: dict[str, Optional[float]] = {}

    for i, row in positions.iterrows():
        isin = row["isin"]
        if progress_callback:
            progress_callback(i / n, f"Resolving {isin}…")

        ticker = resolve_ticker(isin, openfigi_key)
        latest_price = None
        price_ccy = str(row.get("currency", "CHF"))

        if ticker:
            latest_price = fetch_latest_price(ticker)
            # Try to infer price currency from yfinance info
            try:
                info = yf.Ticker(ticker).fast_info
                price_ccy = getattr(info, "currency", price_ccy) or price_ccy
            except Exception:
                pass

        # FX: price_ccy → target_currency
        fx_key = f"{price_ccy}_{target_currency}"
        if fx_key not in fx_cache:
            fx_cache[fx_key] = fetch_fx_rate(price_ccy.upper(), target_currency.upper())
        fx_rate = fx_cache[fx_key] or 1.0

        latest_converted = (latest_price * fx_rate) if latest_price is not None else None
        qty = row["quantity"]
        avg_cost = row.get("avg_cost_price")

        market_value = qty * latest_converted if latest_converted is not None else None

        # Cost basis also needs FX if original currency differs
        cost_fx_key = f"{row.get('currency', 'USD')}_{target_currency}"
        if cost_fx_key not in fx_cache:
            fx_cache[cost_fx_key] = fetch_fx_rate(
                str(row.get("currency", "CHF")).upper(), target_currency.upper()
            )
        cost_fx = fx_cache[cost_fx_key] or 1.0

        cost_total = (qty * avg_cost * cost_fx) if avg_cost is not None else None
        pnl = (market_value - cost_total) if (market_value is not None and cost_total is not None) else None
        pnl_pct = (pnl / abs(cost_total) * 100) if (pnl is not None and cost_total and cost_total != 0) else None

        time.sleep(0.05)  # gentle rate limiting

        results.append({
            **row.to_dict(),
            "ticker": ticker,
            "latest_price": latest_price,
            "price_currency": price_ccy,
            "fx_rate": fx_rate,
            "latest_price_converted": latest_converted,
            "market_value": market_value,
            "cost_basis_total": cost_total,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

    enriched = pd.DataFrame(results)
    return enriched

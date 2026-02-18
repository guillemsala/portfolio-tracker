# Portfolio Tracker

A Streamlit app that ingests a brokerage trade CSV and returns a **live portfolio valuation** using [yfinance](https://github.com/ranaroussi/yfinance) for market prices and [OpenFIGI](https://www.openfigi.com/api) for ISIN→ticker resolution. Format is the default provided by UBS.

## Project structure

```
portfolio_tracker/
├── app.py                  # Streamlit entry point
├── requirements.txt
├── core/
│   ├── parser.py           # CSV ingestion, trade normalisation, position netting
│   └── market_data.py      # ISIN resolution (OpenFIGI), yfinance price/FX fetching
├── ui/
│   └── charts.py           # Plotly chart builders
└── utils/
    └── helpers.py          # Formatting helpers, sample CSV generator
```

## Setup

```bash
cd portfolio_tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Expected CSV schema

| Column | Description |
|---|---|
| Trade date | Trade execution date (DD.MM.YYYY or YYYY-MM-DD) |
| Trade time | Trade execution time |
| Booking | BUY / SELL / etc. |
| Value date | Settlement date |
| ISIN | 12-character ISIN |
| Ccy. | Instrument currency |
| Number/amt. | Quantity (negative = sell for some brokers) |
| Trans. price | Price per unit in instrument currency |
| Exchange rate | FX rate at trade time |
| Valuation currency | Base currency of the account |
| Trans. value | Signed transaction value (negative = cash out) |
| Asset class | Equity / ETF / Bond / etc. |

Both comma-separated and semicolon-separated files are supported.  
European number formatting (`.` as thousands sep, `,` as decimal) is handled automatically.

## Features

- **Position netting** — aggregates all buys and sells per ISIN into a net quantity with a VWAP cost basis.
- **ISIN resolution** — OpenFIGI API (no key required for low volume; optional key in sidebar for higher limits) with yfinance fallback.
- **Live pricing** — `yf.Ticker.fast_info.last_price` with 5-day history fallback.
- **FX conversion** — All positions converted to a user-selected target currency using Yahoo Finance FX pairs (`USDCHF=X`, etc.).
- **Analytics** — Allocation pie chart, per-position P&L bar chart, asset class exposure bar chart.
- **Export** — Download the enriched positions table as CSV.

## Notes on ISIN resolution

Yahoo Finance does not have a native ISIN→ticker API.  The app uses a two-stage approach:

1. **OpenFIGI** (`/v3/mapping`) — returns FIGI records keyed by ISIN, from which US-listed tickers are preferred.
2. **yfinance direct** — some ISINs are accepted directly by yfinance as a ticker string (rare).

For illiquid or OTC instruments (structured products, private equity, etc.) resolution will fail and those positions are flagged separately.

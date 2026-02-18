"""
Portfolio Tracker — Streamlit App
===================================
Upload your brokerage trade CSV and get a live valuation using yfinance.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd

from core.parser import load_trades, compute_positions
from core.market_data import enrich_positions
from ui.charts import pie_chart, bar_pnl, asset_class_bar
from utils.helpers import fmt_currency, fmt_pct, generate_sample_csv, COMMON_CURRENCIES

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Settings")

    target_currency = st.selectbox(
        "Valuation currency",
        COMMON_CURRENCIES,
        index=0,
        help="All positions will be converted to this currency for aggregation.",
    )

    openfigi_key = st.text_input(
        "OpenFIGI API key (optional)",
        type="password",
        help="Free key from https://www.openfigi.com/api — increases rate limits for ISIN resolution.",
    )

    st.markdown("---")
    st.markdown("### Sample CSV")
    st.download_button(
        "Download sample CSV",
        data=generate_sample_csv(),
        file_name="sample_trades.csv",
        mime="text/csv",
    )

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("📈 Portfolio Tracker")
st.markdown(
    "Upload your brokerage trade export and get a **live portfolio valuation** "
    "with prices fetched via [yfinance](https://github.com/ranaroussi/yfinance)."
)

uploaded = st.file_uploader(
    "Upload trade CSV",
    type=["csv", "txt"],
    help="Expected columns: Trade date, Trade time, Booking, Value date, ISIN, Ccy., "
         "Number/amt., Trans. price, Exchange rate, Valuation currency, Trans. value, Asset class",
)

if uploaded is None:
    st.info("👆 Upload a CSV to get started, or download the sample above.")
    st.stop()

# ---------------------------------------------------------------------------
# Parse trades
# ---------------------------------------------------------------------------
with st.spinner("Parsing trades…"):
    try:
        trades = load_trades(uploaded)
    except Exception as e:
        st.error(f"Failed to parse CSV: {e}")
        st.stop()

with st.expander("📋 Raw trades", expanded=False):
    st.dataframe(trades, use_container_width=True)

positions = compute_positions(trades)

if positions.empty:
    st.warning("No open positions found after netting trades.")
    st.stop()

st.markdown(f"**{len(positions)} open positions** found. Fetching live prices…")

# ---------------------------------------------------------------------------
# Enrich with live market data
# ---------------------------------------------------------------------------
progress_bar = st.progress(0.0, text="Resolving tickers…")

def progress_cb(frac: float, msg: str):
    progress_bar.progress(min(frac, 1.0), text=msg)

with st.spinner("Fetching market data from Yahoo Finance…"):
    enriched = enrich_positions(
        positions,
        target_currency=target_currency,
        openfigi_key=openfigi_key or None,
        progress_callback=progress_cb,
    )

progress_bar.empty()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
total_mv = enriched["market_value"].sum(skipna=True)
total_cost = enriched["cost_basis_total"].sum(skipna=True)
total_pnl = enriched["pnl"].sum(skipna=True)
total_pnl_pct = (total_pnl / abs(total_cost) * 100) if total_cost else 0.0

unresolved = enriched["ticker"].isna().sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Market Value", fmt_currency(total_mv, target_currency))
col2.metric("Total Cost Basis", fmt_currency(total_cost, target_currency))
col3.metric("Unrealised P&L", fmt_currency(total_pnl, target_currency), fmt_pct(total_pnl_pct))
col4.metric("Unresolved ISINs", str(unresolved), help="Positions where a ticker could not be found")

st.markdown("---")

# ---------------------------------------------------------------------------
# Positions table
# ---------------------------------------------------------------------------
st.subheader("Positions")

display_cols = [
    "isin", "ticker", "asset_class", "currency", "quantity",
    "avg_cost_price", "latest_price", "price_currency",
    "fx_rate", "latest_price_converted",
    "market_value", "cost_basis_total", "pnl", "pnl_pct",
]
display_cols = [c for c in display_cols if c in enriched.columns]
tbl = enriched[display_cols].copy()

# Format for display
def colour_pnl(val):
    if pd.isna(val):
        return ""
    return "color: #22c55e" if val >= 0 else "color: #ef4444"

styled = (
    tbl.style
    .format({
        "quantity": "{:,.4f}",
        "avg_cost_price": "{:,.4f}",
        "latest_price": "{:,.4f}",
        "fx_rate": "{:,.6f}",
        "latest_price_converted": "{:,.4f}",
        "market_value": "{:,.2f}",
        "cost_basis_total": "{:,.2f}",
        "pnl": "{:+,.2f}",
        "pnl_pct": "{:+.2f}%",
    }, na_rep="N/A")
    .applymap(colour_pnl, subset=["pnl", "pnl_pct"])
)

st.dataframe(styled, use_container_width=True)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
if enriched["market_value"].notna().any():
    st.subheader("Analytics")

    tab1, tab2, tab3 = st.tabs(["Allocation", "P&L", "Asset Class Exposure"])

    with tab1:
        st.plotly_chart(pie_chart(enriched, target_currency), use_container_width=True)

    with tab2:
        if enriched["pnl"].notna().any():
            st.plotly_chart(bar_pnl(enriched, target_currency), use_container_width=True)
        else:
            st.info("P&L not available (cost basis missing).")

    with tab3:
        if "asset_class" in enriched.columns and enriched["asset_class"].notna().any():
            st.plotly_chart(asset_class_bar(enriched, target_currency), use_container_width=True)
        else:
            st.info("Asset class data not available.")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.subheader("Export")
csv_out = enriched.to_csv(index=False).encode()
st.download_button(
    "⬇️ Download enriched positions CSV",
    data=csv_out,
    file_name="portfolio_valuation.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# Unresolved ISINs detail
# ---------------------------------------------------------------------------
if unresolved > 0:
    with st.expander(f"⚠️ {unresolved} unresolved ISINs", expanded=True):
        st.markdown(
            "The following ISINs could not be matched to a Yahoo Finance ticker. "
            "Their market values are excluded from totals. "
            "You may provide an **OpenFIGI API key** in the sidebar to improve resolution."
        )
        st.dataframe(
            enriched[enriched["ticker"].isna()][["isin", "asset_class", "currency", "quantity"]],
            use_container_width=True,
        )

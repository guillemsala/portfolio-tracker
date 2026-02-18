"""
CSV parser for brokerage trade exports.
Expected columns: Trade date, Trade time, Booking, Value date, ISIN,
                  Ccy., Number/amt., Trans. price, Exchange rate,
                  Valuation currency, Trans. value, Asset class
"""

import pandas as pd
import numpy as np
from pathlib import Path


COLUMN_MAP = {
    "Trade date": "trade_date",
    "Trade time": "trade_time",
    "Booking": "booking",
    "Value date": "value_date",
    "ISIN": "isin",
    "Ccy.": "currency",
    "Number/Amt.": "quantity",
    "Trans. price": "trans_price",
    "Exchange rate": "exchange_rate",
    "Valuation currency": "valuation_currency",
    "Trans. value": "trans_value",
    "Asset class": "asset_class",
}


def _parse_numeric(series: pd.Series) -> pd.Series:
    """Handle European-style number formatting (1.234,56 → 1234.56)."""
    if series.dtype == object:
        cleaned = (
            series.astype(str)
            .str.replace(r"\s", "", regex=True)
            .str.replace("'", "")          # Swiss thousands separator
            .str.replace(",", ".", regex=False)
        )
        # If both . and , were present originally, the above is wrong for EU format
        # Detect EU format: dots as thousands sep, comma as decimal
        original = series.astype(str).str.strip()
        eu_mask = original.str.match(r"^-?[\d.]+,\d+$")
        if eu_mask.any():
            cleaned = (
                original
                .str.replace(r"\s", "", regex=True)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def load_trades(file) -> pd.DataFrame:
    """
    Load and normalise trade CSV into a clean DataFrame.
    `file` can be a path string, Path, or file-like object (Streamlit UploadedFile).
    """
    # Try common separators
    df = pd.read_csv(file, sep=";").iloc[:-1]

    # Rename columns
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Parse dates
    for col in ["trade_date", "value_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Parse numerics
    for col in ["quantity", "trans_price", "exchange_rate", "trans_value"]:
        if col in df.columns:
            df[col] = _parse_numeric(df[col])

    # Drop rows without ISIN
    df = df.dropna(subset=["isin"])
    df["isin"] = df["isin"].str.strip()

    return df


def compute_positions(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate trades into current positions (net quantity per ISIN).
    Sells are identified by negative quantity or negative trans_value.
    Returns DataFrame with columns: isin, currency, asset_class, quantity, avg_cost_price
    """
    df = trades.copy()

    # Ensure quantity sign reflects buys (+) and sells (-)
    # Some brokers encode sells with negative trans_value but positive quantity
    if "trans_value" in df.columns:
        # If trans_value is negative and quantity is positive → it's a sell
        sell_mask = (df["trans_value"] < 0) & (df["quantity"] > 0)
        df.loc[sell_mask, "quantity"] = -df.loc[sell_mask, "quantity"]

    # Weighted average cost basis (only buys)
    buys = df[df["quantity"] > 0].copy()

    def wavg_price(g):
        total_qty = g["quantity"].sum()
        if total_qty == 0:
            return np.nan
        return (g["quantity"] * g["trans_price"]).sum() / total_qty

    cost_basis = (
        buys.groupby("isin")
        .apply(wavg_price, include_groups=False)
        .rename("avg_cost_price")
        .reset_index()
    )

    positions = (
        df.groupby(["isin", "currency", "asset_class"], dropna=False)
        .agg(quantity=("quantity", "sum"))
        .reset_index()
    )

    positions = positions[positions["quantity"].abs() > 1e-8]  # drop closed positions
    positions = positions.merge(cost_basis, on="isin", how="left")
    return positions

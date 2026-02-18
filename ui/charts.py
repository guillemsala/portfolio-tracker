"""
Plotly chart helpers for the Streamlit UI.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def pie_chart(df: pd.DataFrame, target_currency: str) -> go.Figure:
    """Portfolio allocation by market value."""
    valid = df.dropna(subset=["market_value"])
    labels = valid["ticker"].fillna(valid["isin"])
    fig = px.pie(
        valid,
        values="market_value",
        names=labels,
        title=f"Portfolio Allocation (market value in {target_currency})",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def bar_pnl(df: pd.DataFrame, target_currency: str) -> go.Figure:
    """P&L per position."""
    valid = df.dropna(subset=["pnl"]).copy()
    valid["label"] = valid["ticker"].fillna(valid["isin"])
    valid = valid.sort_values("pnl")
    colors = ["#ef4444" if v < 0 else "#22c55e" for v in valid["pnl"]]
    fig = go.Figure(
        go.Bar(
            x=valid["label"],
            y=valid["pnl"],
            marker_color=colors,
            text=valid["pnl"].map(lambda x: f"{x:+,.2f}"),
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"Unrealised P&L per Position ({target_currency})",
        xaxis_title="Position",
        yaxis_title=f"P&L ({target_currency})",
        yaxis_zeroline=True,
    )
    return fig


def asset_class_bar(df: pd.DataFrame, target_currency: str) -> go.Figure:
    """Market value by asset class."""
    valid = df.dropna(subset=["market_value", "asset_class"])
    grouped = valid.groupby("asset_class")["market_value"].sum().reset_index()
    fig = px.bar(
        grouped,
        x="asset_class",
        y="market_value",
        title=f"Exposure by Asset Class ({target_currency})",
        labels={"market_value": f"Market Value ({target_currency})", "asset_class": "Asset Class"},
        color="asset_class",
    )
    return fig

"""
Misc utilities: formatting, sample CSV generation.
"""

import pandas as pd
import io


COMMON_CURRENCIES = [
    "CHF", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK",
    "HKD", "SGD", "NZD", "CNY",
]


def fmt_currency(value: float, currency: str = "USD", decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{currency} {value:,.{decimals}f}"


def fmt_pct(value: float) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def generate_sample_csv() -> bytes:
    """Return a minimal sample CSV matching the expected schema."""
    data = {
        "Trade date": ["15.01.2024", "20.01.2024", "05.02.2024", "10.02.2024"],
        "Trade time": ["09:30:00", "14:15:00", "10:00:00", "11:45:00"],
        "Booking": ["BUY", "BUY", "BUY", "SELL"],
        "Value date": ["17.01.2024", "22.01.2024", "07.02.2024", "12.02.2024"],
        "ISIN": ["US0378331005", "US5949181045", "IE00B4L5Y983", "US0378331005"],
        "Ccy.": ["USD", "USD", "USD", "USD"],
        "Number/Amt.": [10, 5, 20, 3],
        "Trans. price": [185.5, 374.0, 85.2, 195.0],
        "Exchange rate": [1.0, 1.0, 1.0, 1.0],
        "Valuation currency": ["CHF", "CHF", "CHF", "CHF"],
        "Trans. value": [1855.0, 1870.0, 1704.0, 585.0],
        "Asset class": ["Equity", "Equity", "ETF", "Equity"],
    }
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_csv(buf, sep=";", index=False)
    return buf.getvalue()

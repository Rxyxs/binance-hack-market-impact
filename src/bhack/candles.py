"""Writes docs/candles.js: Binance spot candles for the page's interactive chart.

Fifteen-minute bars around the hack and daily bars for 2026. `python -m bhack.candles`
"""
from __future__ import annotations

import json

import pandas as pd

from . import datasets
from .config import ROOT

COINS = ["BTC", "BNB", "ETH", "XRP", "SOL"]


def _bars(df: pd.DataFrame) -> list[list]:
    """[unix time, open, high, low, close, USD volume]"""
    return [[int(t.timestamp()), *(float(f"{v:.6g}") for v in row)]
            for t, row in zip(df.index, df[["open", "high", "low", "close", "quote_volume"]].values)]


def build() -> dict:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "quote_volume": "sum"}
    minute, daily = datasets.minute_spot(), datasets.daily_prices()
    out = {"15m": {}, "1d": {}}
    for c in COINS:
        m = minute[minute.coin == c].set_index("time").sort_index()
        out["15m"][c] = _bars(m.resample("15min").agg(agg).dropna())
        d = daily[(daily.coin == c) & (daily.time >= "2026-01-01")].set_index("time").sort_index()
        out["1d"][c] = _bars(d)
    text = "window.CANDLES=" + json.dumps(out, separators=(",", ":")) + ";\n"
    (ROOT / "docs" / "candles.js").write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    o = build()
    print({k: len(v["BTC"]) for k, v in o.items()})

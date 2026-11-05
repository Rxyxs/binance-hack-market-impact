"""Binance charts: docs/candles.js for the page's interactive chart and a static figure.

Fifteen-minute spot and perpetual-futures bars and open interest around the hack, daily
bars for 2026 up to the last closed day, and the published forecast bands.
`python -m bhack.candles`
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import sources
from .config import IMG, REPORTS, ROOT, T_CZ_POST, T_FIRST_OUTFLOW, T_HALT, WIN_END, WIN_START
from .datasets import _klines

COINS = ["BTC", "BNB", "ETH", "XRP", "SOL"]
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "quote_volume": "sum"}


def _bars(df: pd.DataFrame) -> list[list]:
    """[unix time, open, high, low, close, USD volume]"""
    return [[int(t.timestamp()), *(float(f"{v:.6g}") for v in row)]
            for t, row in zip(df.index, df[["open", "high", "low", "close", "quote_volume"]].values)]


def _15m(coin: str, market: str) -> pd.DataFrame:
    k = _klines(coin, "1m", WIN_START.date(), WIN_END.date(), market=market)
    return k.resample("15min").agg(AGG).dropna()


def _open_interest(coin: str) -> list[list]:
    days = pd.date_range(WIN_START.date(), WIN_END.date(), inclusive="left").date
    frames = [sources.binance_daily("metrics", f"{coin}USDT", d, market="um") for d in days]
    m = pd.concat([f for f in frames if f is not None]).set_index("time").sort_index()
    oi = m["sum_open_interest_value"].astype(float).resample("15min").last().dropna()
    return [[int(t.timestamp()), round(v / 1e6, 2)] for t, v in oi.items()]


def impact_figure(spot: dict[str, pd.DataFrame], fut: pd.DataFrame, oi: list[list]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    bg, grid, muted, up, down = "#181a20", "#2b3139", "#848e9c", "#0ecb81", "#f6465d"
    a, b = pd.Timestamp("2026-10-29 16:00", tz="UTC"), pd.Timestamp("2026-10-30 12:00", tz="UTC")
    fig, axes = plt.subplots(3, 1, figsize=(9.5, 7), sharex=True, facecolor=bg,
                             gridspec_kw={"height_ratios": [2, 2, 1]})
    width = pd.Timedelta(minutes=10)
    for ax, (title, d) in zip(axes, [("BTCUSDT spot, 15m", spot["BTC"]), ("BNBUSDT spot, 15m", spot["BNB"])]):
        d = d.loc[a:b]
        for t, r in d.iterrows():
            c = up if r.close >= r.open else down
            ax.vlines(t + pd.Timedelta(minutes=7.5), r.low, r.high, color=c, lw=0.8)
            ax.bar(t + pd.Timedelta(minutes=7.5), max(abs(r.close - r.open), 1e-6), bottom=min(r.open, r.close),
                   width=width, color=c)
        ax.set_title(title, color="#eaecef", fontsize=10, loc="left")
    s = pd.Series({pd.Timestamp(t, unit="s", tz="UTC"): v for t, v in oi}).loc[a:b]
    axes[2].plot(s.index, s.values, color="#fcd535", lw=1.3)
    axes[2].set_title("BTCUSDT perpetual: open interest, $M", color="#eaecef", fontsize=10, loc="left")
    for ax in axes:
        ax.set_facecolor(bg)
        ax.grid(color=grid, lw=0.6)
        ax.tick_params(colors=muted)
        for sp in ax.spines.values():
            sp.set_color(grid)
        for t, lab in [(T_FIRST_OUTFLOW, "20:05 outflow"), (T_CZ_POST, "21:15 CZ"), (T_HALT, "00:13 halt")]:
            ax.axvline(t, color="#fcd535", lw=0.7)
            if ax is axes[0]:
                ax.text(t, 0.97, f" {lab}", transform=ax.get_xaxis_transform(), color="#fcd535", fontsize=8, va="top")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
    fig.tight_layout()
    fig.savefig(IMG / "binance_impact.png", dpi=150, facecolor=bg)
    plt.close(fig)


def history_figure(m15: dict, d1: dict) -> None:
    """BTC and BNB seen at four zooms, with the hack marked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bg, grid, muted = "#181a20", "#2b3139", "#848e9c"
    hack = pd.Timestamp("2026-10-29 20:00", tz="UTC")
    fig, axes = plt.subplots(2, 4, figsize=(12, 5), facecolor=bg)
    for row, coin in zip(axes, ["BTC", "BNB"]):
        def line(bars):
            return pd.Series([b[4] for b in bars], index=pd.to_datetime([b[0] for b in bars], unit="s", utc=True))
        daily = line(d1[coin])
        week = line(m15[coin])[hack - pd.Timedelta(days=3.5):hack + pd.Timedelta(days=3.5)]
        views = [("Week", week), ("Month", daily[hack - pd.Timedelta(days=30):]),
                 ("Year", daily[hack - pd.Timedelta(days=365):]), ("All", daily)]
        for ax, (name, v) in zip(row, views):
            ax.plot(v.index, v.values, color="#0ecb81", lw=1)
            ax.axvline(hack, color="#fcd535", lw=0.9)
            ax.set_title(f"{coin}, {name}", color="#eaecef", fontsize=9.5, loc="left")
            if name == "All":
                ax.set_yscale("log")
            ax.set_facecolor(bg)
            ax.grid(color=grid, lw=0.5)
            ax.tick_params(colors=muted, labelsize=7)
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
            for sp in ax.spines.values():
                sp.set_color(grid)
    fig.tight_layout()
    fig.savefig(IMG / "binance_history.png", dpi=150, facecolor=bg)
    plt.close(fig)


def build() -> dict:
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    out = {"15m": {}, "fut": {}, "oi": {}, "1d": {}, "fc": {}}
    spot = {}
    res = json.loads((REPORTS / "results.json").read_text(encoding="utf-8"))
    fc = pd.DataFrame(res["nowcast"]["forecast"])
    for c in COINS:
        spot[c] = _15m(c, "spot")
        out["15m"][c] = _bars(spot[c])
        out["fut"][c] = _bars(_15m(c, "um"))
        out["oi"][c] = _open_interest(c)
        out["1d"][c] = _bars(_klines(c, "1d", "2017-08-01", today.date()))
        g = fc[fc.coin == c].sort_values("horizon")
        out["fc"][c] = [[int(pd.Timestamp(r.target_date, tz="UTC").timestamp()), r.p05, r.p50, r.p95]
                        for r in g.itertuples()]
    out["asof"] = int(pd.Timestamp(res["nowcast"]["asof"], tz="UTC").timestamp())
    text = "window.CANDLES=" + json.dumps(out, separators=(",", ":")) + ";\n"
    (ROOT / "docs" / "candles.js").write_text(text, encoding="utf-8")
    impact_figure(spot, None, out["oi"]["BTC"])
    history_figure(out["15m"], out["1d"])
    return out


if __name__ == "__main__":
    o = build()
    print({k: len(o[k]["BTC"]) for k in ["15m", "fut", "oi", "1d"]}, np.round(o["fc"]["BTC"][1][1:], 0))

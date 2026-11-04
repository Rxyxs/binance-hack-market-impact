"""Year-by-year view: returns, volatility, Binance volume, who was the aggressor, and hacks."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datasets

YEAR_END = "2026-11-02"  # 2026 is year-to-date


def _max_drawdown(close: pd.Series) -> float:
    return float((close / close.cummax() - 1).min())


def coin_years(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per coin and calendar year from Binance daily klines."""
    d = daily.copy()
    d["date"] = d["time"].dt.tz_localize(None)
    d["year"] = d["date"].dt.year
    d = d.sort_values(["coin", "date"])
    d["logret"] = d.groupby("coin")["close"].transform(lambda s: np.log(s).diff())
    rows = []
    for (coin, year), g in d.groupby(["coin", "year"]):
        if len(g) < 30:
            continue
        prev = d[(d.coin == coin) & (d.date < g.date.min())]
        start = prev["close"].iloc[-1] if len(prev) else g["open"].iloc[0]
        rows.append({
            "coin": coin, "year": year, "days": len(g),
            "return": g["close"].iloc[-1] / start - 1,
            "vol_ann": g["logret"].std() * np.sqrt(365),
            "max_drawdown": _max_drawdown(g["close"]),
            "usd_volume_bn": g["quote_volume"].sum() / 1e9,
            "trades_per_day_k": g["trades"].mean() / 1e3,
            "taker_buy_share": g["taker_buy_quote"].sum() / g["quote_volume"].sum(),
            "days_abs_move_5pct": int((g["logret"].abs() > np.log(1.05)).sum()),
        })
    return pd.DataFrame(rows)


def hacks_by_year(hacks: pd.DataFrame) -> pd.DataFrame:
    h = hacks.copy()
    h["year"] = h["date"].dt.year
    h["cex"] = h["targetType"].eq("CEX")
    out = h.groupby("year").agg(
        incidents=("amount", "size"),
        stolen_bn=("amount", lambda s: s.sum() / 1e9),
        cex_incidents=("cex", "sum"),
        cex_stolen_bn=("amount", lambda s: s[h.loc[s.index, "cex"]].sum() / 1e9),
        largest=("amount", lambda s: h.loc[s.idxmax(), "name"] if s.notna().any() else None),
        largest_bn=("amount", lambda s: s.max() / 1e9),
    ).reset_index()
    return out


def trend_before_hack(daily: pd.DataFrame, coin: str = "BTC",
                      asof: str = "2026-10-28") -> dict:
    """Was the market really in an uptrend on the eve of the hack?"""
    s = daily[daily.coin == coin].set_index(daily[daily.coin == coin]["time"].dt.tz_localize(None))["close"]
    s = s.loc[:asof]
    t = s.index[-1]

    def ret(since):
        base = s.loc[:since]
        return float(s.iloc[-1] / base.iloc[-1] - 1)

    return {
        "asof": str(t.date()), "close": float(s.iloc[-1]),
        "sma50": float(s.tail(50).mean()), "sma200": float(s.tail(200).mean()),
        "golden_cross": bool(s.tail(50).mean() > s.tail(200).mean()),
        "ret_ytd": ret("2025-12-31"), "ret_q3": float(s.loc["2026-09-30"] / s.loc["2026-06-30"] - 1),
        "ret_oct_to_eve": ret("2026-09-30"), "ret_90d": ret(t - pd.Timedelta(days=90)),
        "drawdown_from_2026_high": float(s.iloc[-1] / s.loc["2026-01-01":].max() - 1),
        "high_2026": float(s.loc["2026-01-01":].max()),
        "high_2026_date": str(s.loc["2026-01-01":].idxmax().date()),
    }


def run() -> dict:
    daily = datasets.daily_prices()
    hacks = datasets.hacks()
    cy = coin_years(daily)
    hy = hacks_by_year(hacks)
    return {"coin_years": cy, "hacks_by_year": hy,
            "trend": {c: trend_before_hack(daily, c) for c in ["BTC", "ETH", "BNB"]}}


if __name__ == "__main__":
    out = run()
    pd.set_option("display.width", 200)
    print(out["coin_years"].query("coin in ['BTC','ETH','BNB']").round(3).to_string())
    print(out["hacks_by_year"].round(3).to_string())
    print(out["trend"])

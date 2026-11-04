"""Daily event study of every centralized-exchange hack of $30M or more since 2011.

DefiLlama records the date of each incident but not the hour, so the event window is
day 0 and day +1. Abnormal return = return minus the mean of days -95..-6, standardized
by the standard deviation of that same window. Significance comes from placebo dates,
because crypto returns have tails too fat for a t-table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datasets

MIN_USD = 30e6
EST = (-95, -6)


def btc_daily_close() -> pd.Series:
    """Bitstamp before Binance listed BTCUSDT (2017-08-17), Binance after."""
    bs = datasets.btc_long_history().set_index("time")["close"]
    bs.index = bs.index.tz_localize(None)
    bn = datasets.daily_prices().query("coin == 'BTC'").set_index("time")["close"]
    bn.index = bn.index.tz_localize(None)
    return pd.concat([bs[bs.index < bn.index.min()], bn]).sort_index()


def btc_daily_returns() -> pd.Series:
    return np.log(btc_daily_close()).diff().dropna().rename("BTC")


def coin_daily_returns(coin: str) -> pd.Series:
    d = datasets.daily_prices().query("coin == @coin").set_index("time")["close"]
    d.index = d.index.tz_localize(None)
    return np.log(d).diff().dropna().rename(coin)


def standardized(r: pd.Series, day0: pd.Timestamp, horizons=(0, 1, 5, 10)) -> dict | None:
    if day0 not in r.index:
        return None
    i = r.index.get_loc(day0)
    if i + EST[0] < 0 or i + 1 >= len(r):
        return None
    est = r.iloc[i + EST[0]: i + EST[1] + 1]
    mu, sd = est.mean(), est.std()
    out = {"sigma": sd}
    for h in horizons:  # horizons past the last available day stay NaN (the 2026 hack)
        car = (r.iloc[i: i + h + 1] - mu).sum() if i + h < len(r) else np.nan
        out[f"car_{h}"] = car
        out[f"scar_{h}"] = car / (sd * np.sqrt(h + 1))
    n = min(6, len(r) - i)
    out["abs_sar_0_5"] = float((r.iloc[i: i + n] - mu).abs().mean() / sd)
    return out


def event_table(r: pd.Series, hacks: pd.DataFrame) -> pd.DataFrame:
    ev = hacks[(hacks.targetType == "CEX") & (hacks.amount >= MIN_USD)].copy()
    ev["day0"] = ev["date"].dt.normalize()
    rows = []
    for _, e in ev.iterrows():
        s = standardized(r, e.day0)
        if s:
            rows.append({"date": e.day0.date(), "name": e["name"], "amount_m": e.amount / 1e6, **s})
    return pd.DataFrame(rows)


def placebo(r: pd.Series, n_events: int, exclude: pd.DatetimeIndex, col: str = "scar_1",
            draws: int = 5000, seed: int = 7) -> np.ndarray:
    """Mean standardized CAR over random dates, same number of events, same estimation rule."""
    rng = np.random.default_rng(seed)
    days = r.index[-EST[0]: -11]
    bad = set()
    for d in exclude:
        bad.update(pd.date_range(d - pd.Timedelta(days=10), d + pd.Timedelta(days=10)))
    pool = np.array([d for d in days if d not in bad])
    # precompute the statistic once per candidate day, then resample
    stat = {}
    for d in pool:
        s = standardized(r, d)
        if s:
            stat[d] = s[col]
    vals = np.array(list(stat.values()))
    return np.array([rng.choice(vals, n_events, replace=False).mean() for _ in range(draws)]), vals


def run() -> dict:
    hacks = datasets.hacks()
    out = {}
    for coin, r in [("BTC", btc_daily_returns()), ("ETH", coin_daily_returns("ETH"))]:
        tab = event_table(r, hacks)
        dist, allvals = placebo(r, len(tab), pd.DatetimeIndex(pd.to_datetime(tab["date"])))
        obs = tab["scar_1"].mean()
        absdist, _ = placebo(r, len(tab), pd.DatetimeIndex(pd.to_datetime(tab["date"])),
                             col="abs_sar_0_5")
        binance = tab[(tab.name.str.contains("Binance")) & (pd.to_datetime(tab.date).dt.year == 2026)]
        b = binance.iloc[0] if len(binance) else None
        out[coin] = {
            "table": tab,
            "n_events": len(tab),
            "mean_scar_1": float(obs),
            "p_mean_scar_1": float((dist <= obs).mean()),
            "share_negative": float((tab["scar_1"] < 0).mean()),
            "mean_abs_sar_0_5": float(tab["abs_sar_0_5"].mean()),
            "p_abs_sar_0_5": float((absdist >= tab["abs_sar_0_5"].mean()).mean()),
            "placebo_abs_mean": float(absdist.mean()),
            "corr_size_scar_1": float(np.corrcoef(np.log(tab.amount_m), tab.scar_1)[0, 1]),
            "binance_2026": None if b is None else {
                "car_1": float(b.car_1), "scar_1": float(b.scar_1), "car_5": float(b.car_5),
                "car_10": float(b.car_10),
                "rank_among_hacks": int((tab.scar_1 < b.scar_1).sum() + 1),
                "pct_of_all_days": float((allvals < b.scar_1).mean()),
            },
        }
    return out


if __name__ == "__main__":
    res = run()
    for coin, v in res.items():
        print(coin, {k: v[k] for k in v if k != "table"})
        print(v["table"].sort_values("scar_1").round(3).to_string())

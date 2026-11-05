"""What came after: a week, a month, three months and a year after each exchange hack.

The October 2026 hack is too recent to show its one-year effect, but 35 earlier hacks are
not. Each one is compared with random dates of the same calendar year, so Bitcoin's huge
early drift is not credited to the hacks. Also here: how far each coin has recovered, and
volume and aggressive buying day by day around the hack.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datasets, eventstudy
from .config import T_FIRST_OUTFLOW, US_CLOSE

HORIZONS = (7, 30, 90, 365)
BIG_USD = 250e6
HACK_DAY = pd.Timestamp("2026-10-29")
COINS = ["BTC", "BNB", "ETH", "XRP", "SOL"]


def daily_latest(coin: str) -> pd.DataFrame:
    """Binance daily bars for a coin up to the last closed UTC day."""
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    d = datasets._klines(coin, "1d", "2017-08-01", today.date())
    d.index = d.index.tz_localize(None)
    return d


def btc_close() -> pd.Series:
    """Bitstamp before Binance listed BTC, Binance after, up to the last closed day."""
    old = eventstudy.btc_daily_close()
    new = daily_latest("BTC")["close"]
    return pd.concat([old[old.index < new.index.min()], new]).sort_index()


def _events(hacks: pd.DataFrame) -> pd.DataFrame:
    ev = hacks[(hacks.targetType == "CEX") & (hacks.amount >= eventstudy.MIN_USD)].copy()
    ev["day0"] = ev["date"].dt.normalize()
    return ev


def forward_return(close: pd.Series, day0: pd.Timestamp, h: int) -> float:
    """Simple return from the close before day0 to the close h days after day0."""
    i = close.index.searchsorted(day0)
    if i < 1 or i + h >= len(close):
        return np.nan
    return float(close.iloc[i + h] / close.iloc[i - 1] - 1)


def horizon_table(close: pd.Series, ev: pd.DataFrame, draws: int = 4000, seed: int = 5) -> pd.DataFrame:
    """Median Bitcoin return after hacks against random dates from the same calendar years."""
    rng = np.random.default_rng(seed)
    rows = []
    for label, sub in [("all", ev), ("big", ev[ev.amount >= BIG_USD])]:
        for h in HORIZONS:
            vals = {d: forward_return(close, d, h) for d in sub["day0"]}
            vals = {d: v for d, v in vals.items() if np.isfinite(v)}
            if len(vals) < 3:
                continue
            obs = np.array(list(vals.values()))
            pools = {}
            for y in {d.year for d in vals}:
                days = close.index[close.index.year == y]
                r = np.array([forward_return(close, d, h) for d in days])
                pools[y] = r[np.isfinite(r)]
            years = [d.year for d in vals]
            meds = np.array([np.median([rng.choice(pools[y]) for y in years]) for _ in range(draws)])
            rows.append({"group": label, "horizon": h, "n": len(obs), "median": float(np.median(obs)),
                         "share_up": float((obs > 0).mean()), "random_median": float(np.median(meds)),
                         "p": float(min(1.0, 2 * min((meds <= np.median(obs)).mean(),
                                                     (meds >= np.median(obs)).mean())))})
    return pd.DataFrame(rows)


def paths(close: pd.Series, ev: pd.DataFrame, before: int = 10, after: int = 30) -> pd.DataFrame:
    """Bitcoin path around each hack, as % change from the close before day 0."""
    out = {}
    for _, e in ev.iterrows():
        i = close.index.searchsorted(e.day0)
        if i < before + 1:
            continue
        seg = close.iloc[i - before - 1: i + after + 1]
        s = pd.Series(seg.values / close.iloc[i - 1] - 1, index=np.arange(-before - 1, -before - 1 + len(seg)))
        out[f"{e['name'].replace(' CEX', '')} {e.day0.year}"] = s
    return pd.DataFrame(out)


def days_to_recover(close: pd.Series, day0: pd.Timestamp) -> int | None:
    """Days until a daily close is back above the close before day 0."""
    i = close.index.searchsorted(day0)
    level = close.iloc[i - 1]
    after = close.iloc[i:]
    # a close that never fell below the level does not count as a recovery from a fall
    if (after.iloc[:2] >= level).all():
        return 0
    back = after[after >= level]
    return None if back.empty else int((back.index[0] - close.index[i - 1]).days)


def recovery_table(close: pd.Series, ev: pd.DataFrame) -> pd.DataFrame:
    big = ev[ev.amount >= 100e6].sort_values("day0")
    rows = [{"date": str(e.day0.date()), "name": e["name"].replace(" CEX", ""), "amount_m": e.amount / 1e6,
             "days_to_recover": days_to_recover(close, e.day0)} for _, e in big.iterrows()]
    return pd.DataFrame(rows)


def coin_recovery() -> pd.DataFrame:
    """Where each coin stands against its price when the hack began."""
    rows = []
    m = datasets.minute_spot()
    for c in COINS:
        one = m[m.coin == c].set_index("time")["close"].sort_index()
        pre = float(one.loc[:US_CLOSE - pd.Timedelta(minutes=1)].iloc[-1])
        low = one.loc[T_FIRST_OUTFLOW:]
        d = daily_latest(c)
        rows.append({"coin": c, "price_at_hack": pre, "low": float(low.min()),
                     "low_time": str(low.idxmin()), "low_change": float(low.min() / pre - 1),
                     "last_close": float(d["close"].iloc[-1]), "last_day": str(d.index[-1].date()),
                     "change_to_last": float(d["close"].iloc[-1] / pre - 1),
                     "recovered": bool((d["close"].loc["2026-10-30":] >= pre).any())})
    return pd.DataFrame(rows)


def days_around(coin: str, start: str = "2026-10-20") -> pd.DataFrame:
    """Each day: USD volume against the prior 30 days, share of aggressive buying, range."""
    d = daily_latest(coin)
    base = d["quote_volume"].shift(1).rolling(30).mean().where(d.index < HACK_DAY).ffill()
    out = pd.DataFrame({"coin": coin, "close": d["close"], "volume_bn": d["quote_volume"] / 1e9,
                        "volume_x_normal": d["quote_volume"] / base,
                        "buy_share": d["taker_buy_quote"] / d["quote_volume"],
                        "range_pct": d["high"] / d["low"] - 1})
    return out.loc[start:].reset_index(names="date")


def volatility_change(coin: str) -> dict:
    """Average daily high-low range in the 30 days before and in the days since."""
    d = daily_latest(coin)
    rng = d["high"] / d["low"] - 1
    return {"coin": coin, "range_before": float(rng.loc[:HACK_DAY - pd.Timedelta(days=1)].tail(30).mean()),
            "range_since": float(rng.loc[HACK_DAY:].mean()), "days_since": int((rng.index >= HACK_DAY).sum())}


def run() -> dict:
    close = btc_close()
    ev = _events(datasets.hacks())
    return {"horizons": horizon_table(close, ev), "paths": paths(close, ev),
            "recovery_hacks": recovery_table(close, ev), "coins": coin_recovery(),
            "days": pd.concat([days_around(c) for c in ["BTC", "BNB"]], ignore_index=True),
            "volatility": pd.DataFrame([volatility_change(c) for c in COINS])}


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    r = run()
    for k in ["horizons", "recovery_hacks", "coins", "volatility", "days"]:
        print("==", k)
        print(r[k].round(4).to_string())

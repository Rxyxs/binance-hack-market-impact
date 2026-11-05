"""Where could the price be in a week, a month, three months, six months and a year?

Not a price target. Each path resamples blocks of the coin's own past daily moves, with no
trend added, scaled from today's turbulence back to its normal level. The method is tested
first: from every month-start since 2020, using only earlier data, did the real price land
inside the 90% range as often as promised?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .aftermath import COINS, daily_latest

HORIZONS = (7, 30, 90, 180, 365)
SIMS = 4000
BLOCK = 10          # mean block length, days
HALF_LIFE = 30      # days for today's volatility to fade to its long-run level
LOOKBACK = 1460     # four years of daily moves
QS = (0.05, 0.25, 0.5, 0.75, 0.95)


def ewma_vol(r: np.ndarray, lam: float = 0.94) -> float:
    v = float(np.var(r[:30]))
    for x in r[30:]:
        v = lam * v + (1 - lam) * x * x
    return float(np.sqrt(v))


def simulate(r: np.ndarray, horizon: int, sims: int = SIMS, seed: int = 0) -> np.ndarray:
    """Terminal log change for each path (stationary block bootstrap with volatility fade)."""
    rng = np.random.default_rng(seed)
    hist = r[-LOOKBACK:]
    z = hist - hist.mean()  # no trend: the median path stays at today's price
    long_run = z.std()
    now = ewma_vol(hist)
    fade = np.exp(-np.log(2) * np.arange(horizon) / HALF_LIFE)
    scale = (long_run + (now - long_run) * fade) / long_run
    n = len(z)
    idx = np.zeros((sims, horizon), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, sims)
    for t in range(1, horizon):
        jump = rng.random(sims) < 1 / BLOCK
        idx[:, t] = np.where(jump, rng.integers(0, n, sims), (idx[:, t - 1] + 1) % n)
    return (z[idx] * scale).sum(axis=1)


def backtest(close: pd.Series, horizon: int) -> pd.DataFrame:
    """Month-start origins since 2020 with at least 400 days of history before them."""
    lr = np.log(close).diff().dropna()
    rows = []
    for t in pd.date_range("2020-01-01", close.index[-1], freq="MS"):
        hist = lr.loc[:t]
        future = close.loc[t:]
        if len(hist) < 400 or len(future) <= horizon or close.index[0] > t:
            continue
        sim = simulate(hist.values, horizon, sims=1000, seed=int(t.timestamp()) % 2**31)
        lo, hi = np.quantile(sim, [0.05, 0.95])
        realized = np.log(future.iloc[horizon] / future.iloc[0])
        rows.append({"origin": t, "horizon": horizon, "inside": lo <= realized <= hi,
                     "above_median": realized > np.median(sim), "width": hi - lo})
    return pd.DataFrame(rows)


def run() -> dict:
    fans, tests = [], []
    from .aftermath import coin_recovery
    pre = coin_recovery().set_index("coin")["price_at_hack"]
    for c in COINS:
        d = daily_latest(c)["close"]
        lr = np.log(d).diff().dropna().values
        for h in HORIZONS:
            sim = simulate(lr, h, seed=h)
            q = np.quantile(sim, QS)
            fans.append({"coin": c, "horizon": h, "asof": str(d.index[-1].date()), "last": float(d.iloc[-1]),
                         **{f"p{int(k * 100):02d}": float(d.iloc[-1] * np.exp(v)) for k, v in zip(QS, q)},
                         "prob_above_prehack": float((d.iloc[-1] * np.exp(sim) > pre[c]).mean())})
            t = backtest(d, h)
            tests.append({"coin": c, "horizon": h, "origins": len(t), "coverage_90": float(t["inside"].mean()),
                          "share_above_median": float(t["above_median"].mean())})
    return {"fan": pd.DataFrame(fans), "backtest": pd.DataFrame(tests)}


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    r = run()
    print(r["fan"].round(4).to_string())
    print(r["backtest"].round(3).to_string())
    print(r["backtest"].groupby("horizon")[["coverage_90", "share_above_median"]].mean().round(3))

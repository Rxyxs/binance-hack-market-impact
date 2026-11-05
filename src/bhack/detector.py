"""Could a market-data alarm have caught the hack before the exchange said anything?

The exchange's own token is the canary: a run on Binance should hit BNB harder than the
rest of the market. The score is BNB's 15-minute return minus beta times Bitcoin's,
divided by a robust scale from the previous seven days. The threshold is set on the 60
days before a 30-day hold-out so that it fires at most once a month there; the hold-out
then shows the false alarms a desk would really have seen.

It is tested on the 2026 hack and, untouched, on Binance's May 2019 hack (7,000 BTC).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sources

WINDOW = 15            # minutes
SCALE_DAYS = 7
EPISODE_GAP = pd.Timedelta(minutes=60)
ALARMS_PER_30D = 1

CASES = {
    "2026": {"start": "2026-07-01", "end": "2026-11-03",
             "event": "2026-10-29 20:05", "admitted": "2026-10-29 21:15",
             "source_admitted": "CZ post on X, 21:15 UTC"},
    "2019": {"start": "2019-02-25", "end": "2019-05-12",
             "event": "2019-05-07 17:15", "admitted": "2019-05-07 23:34",
             "source_admitted": "Binance announcement, about 23:34 UTC"},
}


def load(case: dict) -> pd.DataFrame:
    px = {}
    for c in ("BNB", "BTC"):
        k = sources.binance_klines(f"{c}USDT", "1m", case["start"], case["end"])
        s = k["close"]
        s.index = s.index + pd.Timedelta(minutes=1)
        px[c] = s
    return pd.DataFrame(px).ffill().dropna()


def score(px: pd.DataFrame) -> pd.Series:
    lp = np.log(px)
    r = lp.diff(WINDOW)
    # beta from 5-minute returns over the trailing week, known before each minute
    r5 = lp.resample("5min").last().diff()
    n = SCALE_DAYS * 288
    cov = r5["BNB"].rolling(n, min_periods=n // 2).cov(r5["BTC"])
    var = r5["BTC"].rolling(n, min_periods=n // 2).var()
    beta = (cov / var).shift(1).reindex(px.index, method="ffill")
    abn = r["BNB"] - beta * r["BTC"]
    # robust scale of the abnormal return over the trailing week, sampled every 15 minutes
    s15 = abn.resample("15min").last()
    m = SCALE_DAYS * 96
    med = s15.rolling(m, min_periods=m // 2).median()
    mad = (s15 - med).abs().rolling(m, min_periods=m // 2).median()
    scale = (1.4826 * mad).shift(1).reindex(px.index, method="ffill")
    return (abn / scale).rename("z")


def episodes(z: pd.Series, k: float) -> list[pd.Timestamp]:
    hits = z.index[z < -k]
    out = []
    for t in hits:
        if not out or t - out[-1] > EPISODE_GAP:
            out.append(t)
    return out


def calibrate(z: pd.Series) -> float:
    """Smallest threshold with at most ALARMS_PER_30D episodes per 30 days."""
    days = (z.index[-1] - z.index[0]) / pd.Timedelta(days=1)
    budget = int(np.floor(ALARMS_PER_30D * days / 30))
    for k in np.arange(3.0, 30.0, 0.25):
        if len(episodes(z, k)) <= budget:
            return float(k)
    return 30.0


def _relative(px: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> pd.Series:
    """BNB divided by BTC, as % change from the start of the window."""
    ratio = (px["BNB"] / px["BTC"]).loc[a:b]
    return 100 * (ratio / ratio.iloc[0] - 1)


def run_case(name: str) -> dict:
    case = CASES[name]
    px = load(case)
    z = score(px).dropna()
    event, admitted = pd.Timestamp(case["event"], tz="UTC"), pd.Timestamp(case["admitted"], tz="UTC")
    hold_start = event - pd.Timedelta(days=30)
    calib = z[(z.index >= hold_start - pd.Timedelta(days=60)) & (z.index < hold_start)]
    k = calibrate(calib)
    hold = z[(z.index >= hold_start) & (z.index < event - pd.Timedelta(minutes=WINDOW))]
    after = z[(z.index >= event) & (z.index < event + pd.Timedelta(hours=12))]
    first = after.index[after < -k]
    alarm = first[0] if len(first) else None
    return {
        "case": name, "threshold": k, "calibration_days": 60,
        "holdout_false_alarms_30d": len(episodes(hold, k)),
        "event": str(event), "admitted": str(admitted), "admitted_source": case["source_admitted"],
        "alarm": None if alarm is None else str(alarm),
        "minutes_after_event": None if alarm is None else (alarm - event) / pd.Timedelta(minutes=1),
        "minutes_before_admission": None if alarm is None else (admitted - alarm) / pd.Timedelta(minutes=1),
        "min_z_first_12h": float(after.min()), "min_z_time": str(after.idxmin()),
        "z_trace": z[(z.index >= event - pd.Timedelta(hours=3)) & (z.index < event + pd.Timedelta(hours=8))],
        "rel_trace": _relative(px, event - pd.Timedelta(hours=3), event + pd.Timedelta(hours=8)),
    }


def run() -> dict:
    return {n: run_case(n) for n in CASES}


if __name__ == "__main__":
    for n, r in run().items():
        print({k: v for k, v in r.items() if k != "z_trace"})

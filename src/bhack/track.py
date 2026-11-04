"""Score the published forecast against the closes that came after it.

The forecast in reports/results.json is frozen at the day it was made. Every run of this
module fetches the daily closes published since then and records, for each coin and
horizon, whether the close landed inside the 90% band and how far the median was from it,
next to the naive "no change" forecast. `python -m bhack.track` (also run daily by CI).
"""
from __future__ import annotations

import json

import pandas as pd
import requests

from . import sources
from .config import REPORTS

COINBASE = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "XRP": "XRP-USD"}


def realized(coin: str, start: str, end: str) -> pd.Series:
    """Daily closes (UTC day) from Binance's archive; Coinbase (USD) or OKX (USDT) for days
    Binance has not published yet or when its archive is unreachable. The series name says
    which source answered."""
    s = pd.Series(dtype=float)
    try:
        k = sources.binance_klines(f"{coin}USDT", "1d", start, end)
        if len(k):
            s = k["close"]
            s.index = s.index.tz_localize(None)
    except Exception:
        pass
    last = pd.Timestamp(end) - pd.Timedelta(days=1)
    if len(s) and s.index.max() >= last:
        return s.rename("binance")
    if coin in COINBASE:
        url = (f"https://api.exchange.coinbase.com/products/{COINBASE[coin]}/candles?granularity=86400"
               f"&start={start}T00:00:00Z&end={end}T00:00:00Z")
        rows = requests.get(url, timeout=60, headers=sources.UA).json()
        other = pd.Series({pd.Timestamp(r[0], unit="s"): float(r[4]) for r in rows}, name="coinbase")
    else:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={coin}-USDT&bar=1Dutc&limit=100"
        rows = requests.get(url, timeout=60, headers=sources.UA).json()["data"]
        other = pd.Series({pd.Timestamp(int(r[0]), unit="ms"): float(r[4]) for r in rows if r[8] == "1"},
                          name="okx")
    other = other.sort_index()
    other = other[(other.index >= start) & (other.index < end)]
    # Binance where it has the day, the other venue only for the days it is missing
    out = pd.concat([s, other[~other.index.isin(s.index)]]).sort_index()
    out.attrs["source"] = {d: ("binance" if d in s.index else other.name) for d in out.index}
    return out


def run(today: pd.Timestamp | None = None, build_site: bool = True) -> dict:
    res = json.loads((REPORTS / "results.json").read_text(encoding="utf-8"))
    fc = pd.DataFrame(res["nowcast"]["forecast"])
    fc["target_date"] = pd.to_datetime(fc["target_date"])
    asof = pd.Timestamp(res["nowcast"]["asof"])
    today = today or pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    rows = []
    for coin, g in fc.groupby("coin"):
        try:
            closes = realized(coin, str((asof + pd.Timedelta(days=1)).date()), str(today.date()))
        except Exception as e:  # a source unreachable from the runner leaves the coin pending
            print(f"{coin}: no closes ({type(e).__name__})")
            closes = pd.Series(dtype=float)
        for _, f in g.iterrows():
            day = f["target_date"]
            close = closes.get(day)
            src = closes.attrs.get("source", {}).get(day, "binance") if close is not None else None
            rows.append({
                "coin": coin, "horizon": int(f["horizon"]), "target_date": str(day.date()),
                "p05": f["p05"], "p50": f["p50"], "p95": f["p95"], "last_close": f["last_close"],
                "close": None if close is None else float(close), "source": src,
                "inside_90": None if close is None else bool(f["p05"] <= close <= f["p95"]),
                "median_error": None if close is None else float(close / f["p50"] - 1),
                "no_change_error": None if close is None else float(close / f["last_close"] - 1),
            })
    done = [r for r in rows if r["close"] is not None]
    out = {"asof": str(asof.date()), "checked": str(today.date()), "rows": rows,
           "resolved": len(done), "inside_90": sum(r["inside_90"] for r in done)}
    (REPORTS / "track.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    if build_site:
        from . import site
        site.build(res)
    return out


if __name__ == "__main__":
    o = run()
    print(f"{o['resolved']} resolved, {o['inside_90']} inside the 90% band")
    for r in o["rows"]:
        print(r)

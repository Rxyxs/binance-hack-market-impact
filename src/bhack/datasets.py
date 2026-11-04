"""Build the tidy parquet tables every analysis reads. `python -m bhack.datasets`."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import numpy as np
import pandas as pd

from . import snapshot, sources
from .config import COINS, WIN_END, WIN_START, WORK

DAILY_START = "2017-08-01"
DAILY_END = "2026-11-03"  # exclusive: last complete UTC day is 2026-11-02
# POL replaced MATIC one-for-one in September 2024; the two tickers form one history.
ALIASES = {"POL": ["MATICUSDT", "POLUSDT"]}
FUT_COINS = ["BTC", "ETH", "BNB", "XRP", "SOL"]
TRADE_COINS = ["BTC", "ETH", "BNB", "XRP", "SOL"]
TRADE_DAYS = pd.date_range("2026-10-28", "2026-10-31").date
MACRO_DAILY = ["^GSPC", "^NDX", "^VIX", "DX-Y.NYB", "GC=F", "CL=F", "BZ=F", "HG=F", "^TNX",
               "QQQ", "SPY", "COIN", "HOOD", "MSTR", "IBIT", "CRCL"]
FRED_SERIES = ["DGS10", "DGS2", "T10YIE", "BAMLH0A0HYM2", "DTWEXBGS", "USEPUINDXD", "DFF"]
WIKI = ["Bitcoin", "Ethereum", "Cryptocurrency", "Binance"]


def _symbols(coin: str) -> list[str]:
    return ALIASES.get(coin, [f"{coin}USDT"])


def _klines(coin: str, interval: str, start, end, market: str = "spot") -> pd.DataFrame:
    parts = [sources.binance_klines(s, interval, str(start), str(end), market) for s in _symbols(coin)]
    df = pd.concat([p for p in parts if len(p)])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.assign(coin=coin)


def daily_prices() -> pd.DataFrame:
    path = WORK / "daily.parquet"
    if path.exists():
        return pd.read_parquet(path)
    with ThreadPoolExecutor(6) as ex:
        frames = list(ex.map(lambda c: _klines(c, "1d", DAILY_START, DAILY_END), COINS))
    df = pd.concat(frames).reset_index()
    df.to_parquet(path, index=False)
    return df


def btc_long_history() -> pd.DataFrame:
    """Bitcoin since 2011 from Bitstamp, for the hacks that predate Binance."""
    path = WORK / "btc_bitstamp_daily.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = sources.bitstamp_ohlc("btcusd", 86400, "2011-09-01", DAILY_END).reset_index()
    df.to_parquet(path, index=False)
    return df


def minute_spot() -> pd.DataFrame:
    path = WORK / "minute_spot.parquet"
    if path.exists():
        return pd.read_parquet(path)
    s, e = WIN_START.date(), WIN_END.date()
    with ThreadPoolExecutor(6) as ex:
        frames = list(ex.map(lambda c: _klines(c, "1m", s, e), COINS))
    df = pd.concat(frames).reset_index()
    df.to_parquet(path, index=False)
    return df


def minute_futures() -> pd.DataFrame:
    path = WORK / "minute_futures.parquet"
    if path.exists():
        return pd.read_parquet(path)
    s, e = WIN_START.date(), WIN_END.date()
    frames = [_klines(c, "1m", s, e, market="um") for c in FUT_COINS]
    df = pd.concat(frames).reset_index()
    df.to_parquet(path, index=False)
    return df


def futures_metrics() -> pd.DataFrame:
    """Five-minute open interest and long/short ratios from Binance USD-M futures."""
    path = WORK / "futures_metrics.parquet"
    if path.exists():
        return pd.read_parquet(path)
    days = pd.date_range(WIN_START.date(), WIN_END.date() - timedelta(days=1)).date
    frames = []
    for c in FUT_COINS:
        for d in days:
            m = sources.binance_daily("metrics", f"{c}USDT", d, market="um")
            if m is not None:
                frames.append(m.assign(coin=c))
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(path, index=False)
    return df


def funding_history() -> pd.DataFrame:
    path = WORK / "funding.parquet"
    if path.exists():
        return pd.read_parquet(path)
    frames = [sources.binance_funding(f"{c}USDT", "2019-09-01", DAILY_END).assign(coin=c)
              for c in FUT_COINS]
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(path, index=False)
    return df


SIZE_BINS = [0, 1e3, 1e4, 1e5, 1e6, np.inf]
SIZE_LABELS = ["<1k", "1k-10k", "10k-100k", "100k-1M", ">1M"]


def trade_flow() -> pd.DataFrame:
    """Per-minute taker buy and sell dollars split by trade size, from every spot trade.

    An aggregated trade groups fills of one taker order at one price, so its notional is a
    reasonable proxy for the size of the order that hit the book.
    """
    path = WORK / "trade_flow.parquet"
    if path.exists():
        return pd.read_parquet(path)
    frames = []
    for c in TRADE_COINS:
        for d in TRADE_DAYS:
            t = sources.binance_daily("aggTrades", f"{c}USDT", d)
            if t is None:
                continue
            t["usd"] = t["price"] * t["qty"]
            t["side"] = np.where(t["buyer_maker"], "sell", "buy")  # maker was the buyer -> taker sold
            t["size"] = pd.cut(t["usd"], SIZE_BINS, labels=SIZE_LABELS, right=False)
            t["minute"] = t["time"].dt.floor("min")
            g = (t.groupby(["minute", "side", "size"], observed=True)["usd"]
                 .agg(["sum", "count"]).reset_index())
            frames.append(g.assign(coin=c))
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(path, index=False)
    return df


CB_PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "XRP": "XRP-USD",
               "USDT": "USDT-USD"}
OKX_INST = {"BTC": "BTC-USDT", "ETH": "ETH-USDT", "BNB": "BNB-USDT", "SOL": "SOL-USDT",
            "XRP": "XRP-USDT"}


def other_venues() -> pd.DataFrame:
    """One-minute closes on Coinbase (USD) and OKX (USDT) for the same window."""
    path = WORK / "venues.parquet"
    if path.exists():
        return pd.read_parquet(path)
    frames = []
    for c, p in CB_PRODUCTS.items():
        d = sources.coinbase_candles(p, WIN_START, WIN_END)
        frames.append(d[["close", "volume"]].assign(coin=c, venue="coinbase").reset_index())
    for c, inst in OKX_INST.items():
        d = sources.okx_candles(inst, WIN_START, WIN_END)
        frames.append(d[["close", "volume"]].assign(coin=c, venue="okx").reset_index())
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(path, index=False)
    return df


def macro_daily() -> pd.DataFrame:
    path = WORK / "macro_daily.parquet"
    if path.exists():
        return pd.read_parquet(path)
    y = sources.yahoo(MACRO_DAILY, "2016-01-01", "2026-11-03", "1d")
    y["date"] = y["time"].dt.tz_localize(None).dt.normalize()
    wide = y.pivot_table(index="date", columns="ticker", values="close")
    vol = y.pivot_table(index="date", columns="ticker", values="volume")
    wide = wide.join(vol[["COIN", "HOOD", "MSTR", "IBIT", "CRCL"]].add_suffix("_vol"))
    for s in FRED_SERIES:
        wide = wide.join(sources.fred(s), how="outer")
    wide = wide.join(sources.gpr_daily(), how="outer")
    wide = wide.join(sources.fear_greed(), how="outer")
    for a in WIKI:
        wide = wide.join(sources.wiki_views(a), how="outer")
    wide = wide.join(sources.stablecoin_supply(), how="outer")
    wide = wide.join(sources.binance_reserves().groupby(level=0).last(), how="outer")
    for ch in ["hash-rate", "miners-revenue", "n-transactions"]:
        wide = wide.join(sources.blockchain_chart(ch).groupby(level=0).mean(), how="outer")
    wide.index.name = "date"
    wide = wide.sort_index().loc["2016-01-01":"2026-11-02"]
    wide.to_parquet(path)
    return wide


def hacks() -> pd.DataFrame:
    path = WORK / "hacks.parquet"
    if path.exists():
        return pd.read_parquet(path)
    h = sources.defillama_hacks()
    h["chain"] = h["chain"].apply(lambda v: ",".join(v) if isinstance(v, list) else v)
    keep = ["date", "name", "classification", "technique", "amount", "chain", "targetType",
            "bridgeHack", "returnedFunds", "source"]
    h = h[keep].sort_values("date").reset_index(drop=True)
    h.to_parquet(path, index=False)
    return h


def build_all() -> None:
    steps = [snapshot.yahoo_minutes, hacks, daily_prices, btc_long_history, minute_spot,
             minute_futures, futures_metrics, funding_history, trade_flow, other_venues,
             macro_daily]
    for f in steps:
        out = f()
        print(f"{f.__name__:18s} {len(out):>10,} rows")


if __name__ == "__main__":
    build_all()

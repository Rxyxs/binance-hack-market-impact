"""Downloaders for every public source the project uses. None needs an API key.

Each function caches the raw response under data/raw/ and returns a tidy DataFrame,
so a second run reads from disk.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from .config import RAW

UA = {"User-Agent": "Mozilla/5.0 (research; binance-hack-market-impact)"}
BINANCE = "https://data.binance.vision/data"
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def _download(url: str, dest: Path, retries: int = 4, pause: float = 2.0,
              headers: dict | None = None) -> Path | None:
    """Fetch url into dest once. Returns None when the server says the file does not exist."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=UA if headers is None else headers, timeout=120)
        except requests.RequestException:
            time.sleep(pause * (attempt + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 200:
            dest.write_bytes(r.content)
            return dest
        time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"could not download {url}")


def _get_json(url: str, dest: Path, refresh: bool = False, pause: float = 0.0):
    if refresh and dest.exists():
        dest.unlink()
    path = _download(url, dest)
    if pause:
        time.sleep(pause)
    return None if path is None else json.loads(path.read_text(encoding="utf-8"))


def _to_utc(ts: pd.Series) -> pd.Series:
    """Binance switched spot timestamps from milliseconds to microseconds on 2025-01-01."""
    ts = pd.to_numeric(ts)
    unit_us = ts > 10**14
    out = pd.to_datetime(ts.where(~unit_us, ts // 1000), unit="ms", utc=True)
    return out


def _read_zip_csv(path: Path, names: list[str] | None) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), header=None, names=names, low_memory=False)
    first = df.iloc[:, 0].astype(str)
    return df[first.str.match(r"^\d")].reset_index(drop=True)  # futures files carry a header row


def _months(start: date, end: date):
    m = date(start.year, start.month, 1)
    while m < end:
        yield m
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)


# ---------------------------------------------------------------- Binance public archive

def binance_klines(symbol: str, interval: str, start: str, end: str,
                   market: str = "spot") -> pd.DataFrame:
    """Klines between start (inclusive) and end (exclusive) from data.binance.vision.

    Monthly files cover closed months; days of a month whose monthly file is not yet
    published come from daily files.
    """
    base = f"{BINANCE}/{market}" if market == "spot" else f"{BINANCE}/futures/{market}"
    s, e = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    today = datetime.now(timezone.utc).date()
    recent = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)
    frames = []
    for m in _months(s, e):
        name = f"{symbol}-{interval}-{m:%Y-%m}.zip"
        dest = RAW / "binance" / market / "klines" / symbol / interval / name
        path = _download(f"{base}/monthly/klines/{symbol}/{interval}/{name}", dest)
        if path is not None:
            frames.append(_read_zip_csv(path, KLINE_COLS))
            continue
        if m < recent:  # an old month with no monthly file: the pair did not trade then
            continue
        d = max(m, s)
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        while d < min(nxt, e):
            name = f"{symbol}-{interval}-{d:%Y-%m-%d}.zip"
            dest = RAW / "binance" / market / "klines" / symbol / interval / name
            path = _download(f"{base}/daily/klines/{symbol}/{interval}/{name}", dest)
            if path is not None:
                frames.append(_read_zip_csv(path, KLINE_COLS))
            d += timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=KLINE_COLS)
    df = pd.concat(frames, ignore_index=True)
    df["time"] = _to_utc(df["open_time"])
    num = ["open", "high", "low", "close", "volume", "quote_volume", "trades",
           "taker_buy_base", "taker_buy_quote"]
    df[num] = df[num].apply(pd.to_numeric)
    df = df.drop(columns=["open_time", "close_time", "ignore"]).drop_duplicates("time")
    lo, hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    return df[(df.time >= lo) & (df.time < hi)].set_index("time").sort_index()


def binance_daily(kind: str, symbol: str, day: date, market: str = "spot") -> pd.DataFrame | None:
    """One daily file of aggTrades (spot or um) or metrics (um)."""
    base = f"{BINANCE}/{market}" if market == "spot" else f"{BINANCE}/futures/{market}"
    name = f"{symbol}-{kind}-{day:%Y-%m-%d}.zip"
    dest = RAW / "binance" / market / kind / symbol / name
    path = _download(f"{base}/daily/{kind}/{symbol}/{name}", dest)
    if path is None:
        return None
    if kind == "aggTrades":
        cols = ["agg_id", "price", "qty", "first_id", "last_id", "time", "buyer_maker", "best"]
        df = _read_zip_csv(path, cols)
        df["time"] = _to_utc(df["time"])
        df[["price", "qty"]] = df[["price", "qty"]].apply(pd.to_numeric)
        df["buyer_maker"] = df["buyer_maker"].astype(str).str.lower().eq("true")
        return df[["time", "price", "qty", "buyer_maker"]]
    if kind == "metrics":
        with zipfile.ZipFile(path) as z:
            df = pd.read_csv(z.open(z.namelist()[0]))
        df["time"] = pd.to_datetime(df["create_time"], utc=True)
        return df.drop(columns=["create_time"])
    raise ValueError(kind)


def binance_funding(symbol: str, start: str, end: str) -> pd.DataFrame:
    frames = []
    for m in _months(pd.Timestamp(start).date(), pd.Timestamp(end).date()):
        name = f"{symbol}-fundingRate-{m:%Y-%m}.zip"
        dest = RAW / "binance" / "um" / "fundingRate" / symbol / name
        path = _download(f"{BINANCE}/futures/um/monthly/fundingRate/{symbol}/{name}", dest)
        if path is None:
            continue
        with zipfile.ZipFile(path) as z:
            frames.append(pd.read_csv(z.open(z.namelist()[0])))
    if not frames:
        return pd.DataFrame(columns=["time", "funding"])
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["calc_time"], unit="ms", utc=True)
    return df.rename(columns={"last_funding_rate": "funding"})[["time", "funding"]]


# ---------------------------------------------------------------- other exchanges

def coinbase_candles(product: str, start: pd.Timestamp, end: pd.Timestamp,
                     granularity: int = 60) -> pd.DataFrame:
    """Coinbase Exchange public candles, 300 per request."""
    cache = RAW / "coinbase" / f"{product}_{granularity}_{start:%Y%m%d}_{end:%Y%m%d}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows, t = [], start
    step = pd.Timedelta(seconds=granularity * 300)
    while t < end:
        u = min(t + step, end)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles?"
               f"granularity={granularity}&start={t:%Y-%m-%dT%H:%M:%SZ}&end={u:%Y-%m-%dT%H:%M:%SZ}")
        for attempt in range(5):
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                rows.extend(r.json())
                break
            time.sleep(1 + attempt)
        time.sleep(0.15)
        t = u
    df = pd.DataFrame(rows, columns=["ts", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df.drop(columns="ts").drop_duplicates("time").set_index("time").sort_index()
    df = df[(df.index >= start) & (df.index < end)]
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def okx_candles(inst: str, start: pd.Timestamp, end: pd.Timestamp, bar: str = "1m") -> pd.DataFrame:
    """OKX public history candles, 100 per request, paginated backwards from end."""
    cache = RAW / "okx" / f"{inst}_{bar}_{start:%Y%m%d}_{end:%Y%m%d}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows, after = [], int(end.timestamp() * 1000)
    lo = int(start.timestamp() * 1000)
    while after > lo:
        url = (f"https://www.okx.com/api/v5/market/history-candles?instId={inst}"
               f"&bar={bar}&after={after}&limit=100")
        data = None
        for attempt in range(5):
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and r.json().get("code") == "0":
                data = r.json()["data"]
                break
            time.sleep(1 + attempt)
        if not data:
            break
        rows.extend(data)
        after = int(data[-1][0])
        time.sleep(0.12)
    cols = ["ts", "open", "high", "low", "close", "volume", "vol_ccy", "vol_quote", "confirm"]
    df = pd.DataFrame(rows, columns=cols)
    df["time"] = pd.to_datetime(pd.to_numeric(df["ts"]), unit="ms", utc=True)
    df = df.drop(columns=["ts", "confirm"]).apply(lambda c: pd.to_numeric(c) if c.name != "time" else c)
    df = df.drop_duplicates("time").set_index("time").sort_index()
    df = df[(df.index >= start) & (df.index < end)]
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def bitstamp_ohlc(pair: str, step: int, start: str, end: str) -> pd.DataFrame:
    """Bitstamp OHLC since 2011; used for Bitcoin before Binance existed."""
    cache = RAW / "bitstamp" / f"{pair}_{step}_{start}_{end}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    t0 = int(pd.Timestamp(start, tz="UTC").timestamp())
    t1 = int(pd.Timestamp(end, tz="UTC").timestamp())
    rows = []
    while t0 < t1:
        url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/?step={step}&limit=1000&start={t0}"
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        data = r.json()["data"]["ohlc"]
        if not data:
            break
        rows.extend(data)
        last = int(data[-1]["timestamp"])
        if last <= t0:
            break
        t0 = last + step
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["timestamp"].astype(int), unit="s", utc=True)
    df = df.drop(columns="timestamp").set_index("time").astype(float)
    df = df[~df.index.duplicated()].sort_index()
    df = df[df.index < pd.Timestamp(end, tz="UTC")]
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


# ---------------------------------------------------------------- markets and macro

def yahoo(tickers: list[str], start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """Long table (time, ticker, open, high, low, close, volume) from Yahoo Finance."""
    import yfinance as yf

    tag = hashlib.md5("|".join(sorted(tickers)).encode()).hexdigest()[:10]
    cache = RAW / "yahoo" / f"{tag}_{interval}_{start}_{end}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    frames = []
    for t in tickers:
        d = yf.download(t, start=start, end=end, interval=interval, progress=False,
                        auto_adjust=True, threads=False)
        if d.empty:
            continue
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        d.index = (d.index.tz_convert("UTC") if d.index.tz is not None
                   else d.index.tz_localize("UTC"))
        d.index.name = "time"
        frames.append(d.assign(ticker=t).reset_index())
        time.sleep(0.5)
    df = pd.concat(frames, ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df


def fred(series: str) -> pd.Series:
    dest = RAW / "fred" / f"{series}.csv"
    # FRED stalls requests that send a browser-like user agent; the library default works
    _download(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", dest, headers={})
    df = pd.read_csv(dest)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.rename(series).dropna()


def gpr_daily() -> pd.DataFrame:
    """Caldara-Iacoviello daily Geopolitical Risk index: war and terror news in 10 papers."""
    dest = RAW / "gpr" / "data_gpr_daily_recent.dta"
    _download("https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.dta", dest)
    g = pd.read_stata(dest)
    g["date"] = pd.to_datetime(g["date"])
    return g.set_index("date")[["GPRD", "GPRD_ACT", "GPRD_THREAT"]]


def fear_greed() -> pd.Series:
    data = _get_json("https://api.alternative.me/fng/?limit=0&format=json",
                     RAW / "feargreed" / "fng.json")
    df = pd.DataFrame(data["data"])
    s = pd.Series(df["value"].astype(float).values,
                  index=pd.to_datetime(df["timestamp"].astype(int), unit="s"))
    return s.sort_index().rename("fear_greed")


def wiki_views(article: str, start: str = "20150701", end: str | None = None) -> pd.Series:
    end = end or datetime.now(timezone.utc).strftime("%Y%m%d")
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
           f"all-access/user/{article}/daily/{start}/{end}")
    data = _get_json(url, RAW / "wiki" / f"{article}_{start}_{end}.json")
    df = pd.DataFrame(data["items"])
    return pd.Series(df["views"].values, index=pd.to_datetime(df["timestamp"].str[:8]),
                     name=f"wiki_{article.lower()}")


def defillama_hacks() -> pd.DataFrame:
    data = _get_json("https://api.llama.fi/hacks", RAW / "defillama" / "hacks.json")
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], unit="s")
    return df


def stablecoin_supply() -> pd.Series:
    data = _get_json("https://stablecoins.llama.fi/stablecoincharts/all",
                     RAW / "defillama" / "stablecoins_all.json")
    rows = [(int(d["date"]), d["totalCirculatingUSD"].get("peggedUSD")) for d in data]
    s = pd.Series([v for _, v in rows], index=pd.to_datetime([t for t, _ in rows], unit="s"))
    return s.astype(float).rename("stablecoin_usd")


def binance_reserves() -> pd.Series:
    """Total assets DefiLlama tracks on Binance's published wallet addresses (USD)."""
    data = _get_json("https://api.llama.fi/protocol/binance-cex", RAW / "defillama" / "binance_cex.json")
    tvl = pd.DataFrame(data["tvl"])
    return pd.Series(tvl["totalLiquidityUSD"].values,
                     index=pd.to_datetime(tvl["date"], unit="s"), name="binance_assets_usd")


def blockchain_chart(name: str) -> pd.Series:
    url = f"https://api.blockchain.info/charts/{name}?timespan=all&format=json&sampled=false"
    data = _get_json(url, RAW / "blockchain" / f"{name}.json")
    df = pd.DataFrame(data["values"])
    return pd.Series(df["y"].values, index=pd.to_datetime(df["x"], unit="s"), name=name)


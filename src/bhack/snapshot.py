"""Freeze the one source that stops serving the hack window after a few weeks.

Yahoo keeps one-minute bars for only 30 days, so they are saved to data/snapshot/
(versioned) the first time the project runs. Everything else is re-downloadable.
"""
import pandas as pd

from . import sources
from .config import SNAPSHOT, WIN_END, WIN_START

# Index futures trade nearly 24 h, so they keep pricing macro news after the 16:00 New York
# close, which is when the hack began. Stocks are the crypto-exposed equities.
MACRO_1M = ["NQ=F", "ES=F", "DX-Y.NYB", "GC=F", "CL=F", "^TNX"]
STOCKS_1M = ["COIN", "HOOD", "MSTR", "IBIT", "CRCL"]


def yahoo_minutes() -> pd.DataFrame:
    path = SNAPSHOT / "yahoo_1m.parquet"
    if path.exists():
        return pd.read_parquet(path)
    chunks = []
    t = WIN_START
    while t < WIN_END:  # Yahoo serves at most 8 days of minute bars per request
        u = min(t + pd.Timedelta(days=6), WIN_END)
        chunks.append(sources.yahoo(MACRO_1M + STOCKS_1M, f"{t:%Y-%m-%d}", f"{u:%Y-%m-%d}", "1m"))
        t = u
    df = pd.concat(chunks).drop_duplicates(["ticker", "time"])
    df = df[["time", "ticker", "close", "volume"]].sort_values(["ticker", "time"])
    df.to_parquet(path, index=False)
    return df


if __name__ == "__main__":
    y = yahoo_minutes()
    print(y.groupby("ticker")["time"].agg(["min", "max", "count"]))

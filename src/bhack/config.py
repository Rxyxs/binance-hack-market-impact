"""Paths, coin universe and the key timestamps of the October 2026 Binance hack."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"            # re-downloadable, git-ignored
WORK = DATA / "work"          # derived parquet files, git-ignored
SNAPSHOT = DATA / "snapshot"  # small files that sources stop serving after a few weeks; versioned
CATALOG = DATA / "catalog"    # hand-curated tables with a source URL per row; versioned
REPORTS = ROOT / "reports"
IMG = ROOT / "docs" / "img"

# Chains TRM Labs lists as drained (Ethereum, Bitcoin, Tron, XRP Ledger, Solana, Arbitrum,
# Optimism, Base, Avalanche, Polygon). The native coin of each chain is "stolen".
STOLEN = ["BTC", "ETH", "XRP", "SOL", "TRX", "AVAX", "ARB", "OP", "POL"]
# Large coins whose chains were not touched. They trade on the same exchange and share
# the same market factor, so they are the control group for "was the loot dumped?".
UNTOUCHED = ["DOGE", "ADA", "LTC", "BCH", "DOT", "ATOM", "NEAR", "XLM", "HBAR", "SUI",
             "APT", "FIL", "ETC"]
# BNB is the exchange's own token: exposed to Binance itself, not to the loot.
EXCHANGE_TOKEN = ["BNB"]
COINS = ["BTC", "ETH", "BNB", "XRP", "SOL", "TRX", "AVAX", "ARB", "OP", "POL"] + UNTOUCHED

# Coins stolen in native units (TRM Labs, 2026-10-30). Used to size the overhang.
STOLEN_UNITS = {"BTC": 18_270, "ETH": 200_630, "XRP": 233.46e6, "SOL": 970_500,
                "TRX": 46.4e6, "ARB": 74.6e6}

UTC = "UTC"
T_FIRST_OUTFLOW = pd.Timestamp("2026-10-29 20:05", tz=UTC)  # XRP Ledger wallets, TRM
T_BTC_ETH_DRAIN = pd.Timestamp("2026-10-29 20:20", tz=UTC)  # BTC hot wallet + EIP-7702
T_CZ_POST = pd.Timestamp("2026-10-29 21:15", tz=UTC)        # "does look like a hack"
T_BINANCE_AWARE = pd.Timestamp("2026-10-29 21:24", tz=UTC)  # first official statement
T_HALT = pd.Timestamp("2026-10-30 00:13", tz=UTC)           # deposits and withdrawals paused
T_REOPEN = pd.Timestamp("2026-11-01 06:00", tz=UTC)         # phase one of withdrawals
US_CLOSE = pd.Timestamp("2026-10-29 20:00", tz=UTC)         # 16:00 New York (EDT)

# Last UTC day (exclusive) used by the aftermath and scenario analyses, so a rerun gives the same
# numbers. The interactive chart keeps updating on its own.
ANALYSIS_END = "2026-11-06"

# Minute-level window studied around the hack.
WIN_START = pd.Timestamp("2026-10-22", tz=UTC)
WIN_END = pd.Timestamp("2026-11-03", tz=UTC)  # exclusive

for p in (RAW, WORK, SNAPSHOT, CATALOG, REPORTS, IMG):
    p.mkdir(parents=True, exist_ok=True)

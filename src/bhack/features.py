"""Daily feature panel for the forecasting models.

Row (coin, t) holds only what was public at 00:00 UTC of day t+1, when day t's candle
closes. US market closes (20:00-21:00 UTC) are known by then. Series that are compiled
from the day's news or published the next morning (FRED, the geopolitical risk index,
policy uncertainty, Fear & Greed, Wikipedia views, on-chain charts, the hack register)
enter with one extra day of lag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datasets

TARGET_COINS = ["BTC", "ETH", "BNB", "XRP", "SOL"]
PANEL_START = "2019-01-01"

GROUPS = {
    "price_volume": ["r1", "r3", "r7", "r14", "r30", "r90", "rv7", "rv30", "rv_ratio", "range1",
                     "range7", "vol_z", "trades_z", "buy_share_1", "buy_share_7", "buy_share_dev",
                     "sma50_gap", "sma200_gap", "dd90", "btc_r1", "btc_r7", "mkt_r1", "mkt_r7",
                     "dispersion"],
    "derivatives": ["funding_1", "funding_7"],
    "macro_markets": ["spx_r1", "ndx_r1", "ndx_r5", "vix", "vix_chg5", "dxy_r5", "us10y",
                      "us10y_chg5", "gold_r5", "brent_r5", "brent_r20", "copper_r5", "us2y",
                      "breakeven10", "hy_spread", "hy_chg5", "fed_funds"],
    "war_policy_news": ["gpr_log", "gpr_7", "gpr_threat_7", "gpr_act_7", "gpr_vs_90",
                        "epu_7", "epu_vs_90"],
    "sentiment_attention": ["fng", "fng_chg7", "wiki_btc", "wiki_crypto", "wiki_binance"],
    "onchain_supply": ["hash_chg7", "hash_chg30", "miner_rev_chg30", "stable_g7", "stable_g30",
                       "binance_assets_g7"],
    "hacks": ["hack_usd_7", "hack_cex_usd_30", "days_since_cex_100m"],
    "calendar": ["dow"],
}
FEATURES = [f for g in GROUPS.values() for f in g]


def _coin_block(d: pd.DataFrame) -> pd.DataFrame:
    d = d.sort_index()
    c = d["close"]
    lr = np.log(c).diff()
    out = pd.DataFrame(index=d.index)
    out["close"] = c
    out["r1"] = lr
    for k in (3, 7, 14, 30, 90):
        out[f"r{k}"] = np.log(c / c.shift(k))
    out["rv7"] = lr.rolling(7).std()
    out["rv30"] = lr.rolling(30).std()
    out["rv_ratio"] = out.rv7 / out.rv30
    out["range1"] = np.log(d["high"] / d["low"])
    out["range7"] = out["range1"].rolling(7).mean()
    lq = np.log(d["quote_volume"].clip(lower=1))
    out["vol_z"] = (lq - lq.rolling(30).mean()) / lq.rolling(30).std()
    lt = np.log(d["trades"].clip(lower=1))
    out["trades_z"] = (lt - lt.rolling(30).mean()) / lt.rolling(30).std()
    share = d["taker_buy_quote"] / d["quote_volume"]
    out["buy_share_1"] = share
    out["buy_share_7"] = d["taker_buy_quote"].rolling(7).sum() / d["quote_volume"].rolling(7).sum()
    out["buy_share_dev"] = out["buy_share_7"] - share.rolling(90).mean()
    out["sma50_gap"] = np.log(c / c.rolling(50).mean())
    out["sma200_gap"] = np.log(c / c.rolling(200).mean())
    out["dd90"] = c / c.rolling(90).max() - 1
    # targets
    out["y1"] = lr.shift(-1)
    out["y7"] = np.log(c.shift(-7) / c)
    fut = pd.concat([lr.shift(-k) for k in range(1, 8)], axis=1)
    out["rv7_fwd"] = np.sqrt((fut ** 2).mean(axis=1, skipna=False))
    return out


def _lag(s: pd.Series, idx: pd.DatetimeIndex, days: int = 1) -> pd.Series:
    """Align a daily series to crypto days, carry it over weekends, then lag it."""
    s = s.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(idx.union(s.index)).ffill().reindex(idx).shift(days)


def macro_block(idx: pd.DatetimeIndex) -> pd.DataFrame:
    m = datasets.macro_daily()
    out = pd.DataFrame(index=idx)

    def mk(col, lag):
        return _lag(m[col].dropna(), idx, lag)

    spx, ndx = mk("^GSPC", 0), mk("^NDX", 0)
    out["spx_r1"] = np.log(spx / spx.shift(1))
    out["ndx_r1"] = np.log(ndx / ndx.shift(1))
    out["ndx_r5"] = np.log(ndx / ndx.shift(5))
    vix = mk("^VIX", 0)
    out["vix"], out["vix_chg5"] = vix, vix - vix.shift(5)
    dxy = mk("DX-Y.NYB", 0)
    out["dxy_r5"] = np.log(dxy / dxy.shift(5))
    tnx = mk("^TNX", 0)
    out["us10y"], out["us10y_chg5"] = tnx, tnx - tnx.shift(5)
    for name, col, k in [("gold_r5", "GC=F", 5), ("brent_r5", "BZ=F", 5), ("brent_r20", "BZ=F", 20),
                         ("copper_r5", "HG=F", 5)]:
        x = mk(col, 0)
        out[name] = np.log(x / x.shift(k))
    out["us2y"] = mk("DGS2", 1)
    out["breakeven10"] = mk("T10YIE", 1)
    hy = mk("BAMLH0A0HYM2", 1)
    out["hy_spread"], out["hy_chg5"] = hy, hy - hy.shift(5)
    out["fed_funds"] = mk("DFF", 1)

    g = np.log(mk("GPRD", 1).clip(lower=1))
    out["gpr_log"] = g
    out["gpr_7"] = g.rolling(7).mean()
    out["gpr_threat_7"] = np.log(mk("GPRD_THREAT", 1).clip(lower=1)).rolling(7).mean()
    out["gpr_act_7"] = np.log(mk("GPRD_ACT", 1).clip(lower=1)).rolling(7).mean()
    out["gpr_vs_90"] = out["gpr_7"] - g.rolling(90).mean()
    e = np.log(mk("USEPUINDXD", 1).clip(lower=1))
    out["epu_7"] = e.rolling(7).mean()
    out["epu_vs_90"] = out["epu_7"] - e.rolling(90).mean()

    f = mk("fear_greed", 1)
    out["fng"], out["fng_chg7"] = f, f - f.shift(7)
    for name, col in [("wiki_btc", "wiki_bitcoin"), ("wiki_crypto", "wiki_cryptocurrency"),
                      ("wiki_binance", "wiki_binance")]:
        v = np.log(mk(col, 1).clip(lower=1))
        out[name] = v.rolling(7).mean() - v.rolling(90).mean()

    h = mk("hash-rate", 1)
    out["hash_chg7"] = np.log(h.rolling(7).mean() / h.rolling(7).mean().shift(7))
    out["hash_chg30"] = np.log(h.rolling(7).mean() / h.rolling(7).mean().shift(30))
    mr = mk("miners-revenue", 1)
    out["miner_rev_chg30"] = np.log(mr.rolling(7).mean() / mr.rolling(7).mean().shift(30))
    st = mk("stablecoin_usd", 1)
    out["stable_g7"] = np.log(st / st.shift(7))
    out["stable_g30"] = np.log(st / st.shift(30))
    ba = mk("binance_assets_usd", 1)
    out["binance_assets_g7"] = np.log(ba / ba.shift(7))
    return out


def hack_block(idx: pd.DatetimeIndex) -> pd.DataFrame:
    h = datasets.hacks()
    h = h.assign(day=h["date"].dt.normalize())
    allh = h.groupby("day")["amount"].sum()
    cex = h[h.targetType == "CEX"].groupby("day")["amount"].sum()
    big = h[(h.targetType == "CEX") & (h.amount >= 100e6)]["day"].sort_values()
    full = pd.date_range(min(idx.min(), allh.index.min()), idx.max())
    a = allh.reindex(full, fill_value=0)
    c = cex.reindex(full, fill_value=0)
    out = pd.DataFrame(index=full)
    out["hack_usd_7"] = np.log1p(a.rolling(7).sum())
    out["hack_cex_usd_30"] = np.log1p(c.rolling(30).sum())
    last = pd.Series(pd.NaT, index=full, dtype="datetime64[ns]")
    hit = full[full.isin(big)]
    last.loc[hit] = hit
    last = last.ffill()
    days = (pd.Series(full, index=full) - last).dt.days
    out["days_since_cex_100m"] = days.clip(upper=365).fillna(365)
    return out.shift(1).reindex(idx)


def build() -> pd.DataFrame:
    from .config import WORK
    path = WORK / "panel.parquet"
    if path.exists():
        return pd.read_parquet(path)
    daily = datasets.daily_prices()
    daily = daily.assign(date=daily["time"].dt.tz_localize(None).dt.normalize())
    wide_close = daily.pivot_table(index="date", columns="coin", values="close")
    mkt_ret = np.log(wide_close).diff()
    idx = wide_close.index
    mkt = pd.DataFrame(index=idx)
    mkt["btc_r1"] = mkt_ret["BTC"]
    mkt["btc_r7"] = np.log(wide_close["BTC"] / wide_close["BTC"].shift(7))
    mkt["mkt_r1"] = mkt_ret.mean(axis=1)
    mkt["mkt_r7"] = mkt_ret.rolling(7).sum().mean(axis=1)
    mkt["dispersion"] = mkt_ret.std(axis=1)
    macro = macro_block(idx)
    hk = hack_block(idx)

    fund = datasets.funding_history()
    fund = fund.assign(date=fund["time"].dt.tz_localize(None).dt.normalize())
    fund = fund.groupby(["coin", "date"])["funding"].mean()

    frames = []
    for c in TARGET_COINS:
        d = daily[daily.coin == c].set_index("date")
        blk = _coin_block(d)
        f = fund.get(c, pd.Series(dtype=float)) if c in fund.index.get_level_values(0) else pd.Series(dtype=float)
        f = f.reindex(blk.index)
        blk["funding_1"] = f
        blk["funding_7"] = f.rolling(7, min_periods=3).mean()
        blk = blk.join(mkt).join(macro).join(hk)
        blk["dow"] = blk.index.dayofweek
        frames.append(blk.assign(coin=c))
    panel = pd.concat(frames).reset_index().rename(columns={"index": "date"})
    panel = panel[panel.date >= PANEL_START].sort_values(["date", "coin"]).reset_index(drop=True)
    panel.to_parquet(path, index=False)
    return panel


if __name__ == "__main__":
    p = build()
    print(p.shape, p.date.min(), p.date.max())
    cov = p[FEATURES].notna().mean().sort_values()
    print(cov.head(15).round(3).to_string())
    print(p[p.date == p.date.max()][["coin", "close", "r1", "vix", "gpr_log", "fng", "brent_r20"]])

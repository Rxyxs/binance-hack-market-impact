"""Minute-level anatomy of the night of 29 October 2026.

Two shocks landed within minutes of each other: the hack (first outflow 20:05 UTC) and the
after-hours earnings of Amazon and Intel (released after the 20:00 UTC New York close),
which pushed Nasdaq futures down. Every abnormal return here is measured against a model
fitted on the week before, so the earnings shock is not credited to the hack.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import datasets, snapshot
from .config import (STOLEN, STOLEN_UNITS, T_BINANCE_AWARE, T_CZ_POST,
                     T_FIRST_OUTFLOW, T_HALT, T_REOPEN, UNTOUCHED, US_CLOSE)

PRE = (pd.Timestamp("2026-10-22", tz="UTC"), pd.Timestamp("2026-10-29 12:00", tz="UTC"))
T0 = US_CLOSE  # 20:00 UTC, five minutes before the first outflow
WINDOWS = {
    "before_admission": (T0, T_CZ_POST),           # 20:00-21:15: on-chain only, no statement
    "admitted_open": (T_CZ_POST, T_HALT),           # 21:15-00:13: admitted, withdrawals open
    "halt_first_6h": (T_HALT, T_HALT + pd.Timedelta(hours=6)),
    "night_total": (T0, pd.Timestamp("2026-10-30 06:00", tz="UTC")),
    "to_reopen": (T0, T_REOPEN),
    "to_nov2_close": (T0, pd.Timestamp("2026-11-03", tz="UTC")),
}
CHECKPOINTS = {"20:05 first outflow": T_FIRST_OUTFLOW, "21:15 CZ post": T_CZ_POST,
               "21:24 Binance statement": T_BINANCE_AWARE, "00:13 halt": T_HALT,
               "06:00 Oct 30": pd.Timestamp("2026-10-30 06:00", tz="UTC"),
               "06:00 Nov 1 reopen": T_REOPEN,
               "Nov 2 close": pd.Timestamp("2026-11-03", tz="UTC")}


def closes() -> pd.DataFrame:
    """Wide minute closes indexed by the bar's END time, so index t = price at t."""
    m = datasets.minute_spot()
    w = m.pivot_table(index="time", columns="coin", values="close")
    w.index = w.index + pd.Timedelta(minutes=1)
    return w.sort_index().ffill()


def price_at(w: pd.DataFrame | pd.Series, t: pd.Timestamp):
    return w.loc[:t].iloc[-1]


def window_return(w, a, b):
    return np.log(price_at(w, b) / price_at(w, a))


def betas_to_btc(w: pd.DataFrame, freq: str = "5min") -> pd.Series:
    r = np.log(w.loc[PRE[0]:PRE[1]].resample(freq).last()).diff().dropna()
    x = r["BTC"]
    return r.apply(lambda y: np.cov(y, x)[0, 1] / x.var())


def paths(w: pd.DataFrame) -> pd.DataFrame:
    """Cumulative log return from 20:00 UTC to each checkpoint, per coin."""
    base = price_at(w, T0)
    return pd.DataFrame({k: np.log(price_at(w, t) / base) for k, t in CHECKPOINTS.items()})


def abnormal_vs_btc(w: pd.DataFrame) -> pd.DataFrame:
    """Return of each coin minus beta x BTC return, per window."""
    beta = betas_to_btc(w)
    rows = []
    for name, (a, b) in WINDOWS.items():
        r = window_return(w, a, b)
        rows.append(pd.DataFrame({"window": name, "coin": r.index, "ret": r.values,
                                  "beta": beta.reindex(r.index).values,
                                  "abn": (r - beta * r["BTC"]).values}))
    df = pd.concat(rows, ignore_index=True)
    df["group"] = np.select([df.coin.eq("BNB"), df.coin.isin(STOLEN), df.coin.isin(UNTOUCHED)],
                            ["exchange token", "stolen chain", "untouched chain"], "other")
    return df


def stolen_vs_untouched(ab: pd.DataFrame, draws: int = 20000, seed: int = 11) -> pd.DataFrame:
    """Difference in mean abnormal return, drained chains minus untouched chains, with a
    two-sided permutation p-value (labels shuffled among the 21 coins). BTC is left out:
    its abnormal return against itself is zero by construction."""
    rng = np.random.default_rng(seed)
    rows = []
    for win, g in ab[(ab.coin != "BTC") & ab.group.isin(["stolen chain", "untouched chain"])].groupby("window"):
        x = g["abn"].values
        lab = g["group"].eq("stolen chain").values
        obs = x[lab].mean() - x[~lab].mean()
        perm = np.array([(lambda p: x[p].mean() - x[~p].mean())(rng.permutation(lab)) for _ in range(draws)])
        rows.append({"window": win, "stolen_mean": x[lab].mean(), "untouched_mean": x[~lab].mean(),
                     "diff": obs, "p_perm": float((np.abs(perm) >= abs(obs)).mean()),
                     "n_stolen": int(lab.sum()), "n_untouched": int((~lab).sum())})
    return pd.DataFrame(rows)


def overhang(w: pd.DataFrame) -> pd.DataFrame:
    """Stolen coins as a share of a normal day's Binance spot volume for that coin."""
    m = datasets.minute_spot()
    pre = m[(m.time >= PRE[0]) & (m.time < PRE[1])]
    days = (PRE[1] - PRE[0]) / pd.Timedelta(days=1)
    vol = pre.groupby("coin")["volume"].sum() / days
    out = pd.DataFrame({"stolen_units": pd.Series(STOLEN_UNITS)})
    out["daily_volume_units"] = vol.reindex(out.index)
    out["stolen_vs_daily_volume"] = out.stolen_units / out.daily_volume_units
    out["usd_at_20h"] = out.stolen_units * price_at(w, T0).reindex(out.index)
    return out


# ------------------------------------------------------------------- hack vs Nasdaq

def macro_minutes() -> pd.DataFrame:
    y = snapshot.yahoo_minutes()
    w = y.pivot_table(index="time", columns="ticker", values="close")
    w.index = w.index + pd.Timedelta(minutes=1)
    return w.sort_index()


def btc_vs_futures(w: pd.DataFrame, freq: str = "5min") -> dict:
    """Fit BTC returns on Nasdaq futures, dollar and gold in the pre-week, then split
    each window's BTC move into the part those markets explain and the rest."""
    mac = macro_minutes()[["NQ=F", "DX-Y.NYB", "GC=F"]]
    px = w[["BTC", "ETH", "BNB"]].join(mac, how="left")
    pre = np.log(px.loc[PRE[0]:PRE[1]].resample(freq).last()).diff()
    pre = pre.dropna()
    X = np.column_stack([np.ones(len(pre)), pre[["NQ=F", "DX-Y.NYB", "GC=F"]].values])
    fits = {}
    for c in ["BTC", "ETH", "BNB"]:
        coef, *_ = np.linalg.lstsq(X, pre[c].values, rcond=None)
        resid = pre[c].values - X @ coef
        r2 = 1 - resid.var() / pre[c].var()
        fits[c] = {"beta_nq": coef[1], "beta_dxy": coef[2], "beta_gold": coef[3],
                   "r2": r2, "n": len(pre)}

    mac_ff = mac.ffill()
    windows = {"us_session_oct29": (pd.Timestamp("2026-10-29 13:30", tz="UTC"), T0), **WINDOWS}
    rows = []
    for name, (a, b) in windows.items():
        dm = np.log(price_at(mac_ff, b) / price_at(mac_ff, a))
        for c in ["BTC", "ETH", "BNB"]:
            f = fits[c]
            actual = float(window_return(w[c], a, b))
            explained = f["beta_nq"] * dm["NQ=F"] + f["beta_dxy"] * dm["DX-Y.NYB"] + f["beta_gold"] * dm["GC=F"]
            rows.append({"window": name, "coin": c, "actual": actual, "explained": float(explained),
                         "abnormal": actual - float(explained), "nq_move": float(dm["NQ=F"])})
    return {"fits": fits, "decomposition": pd.DataFrame(rows)}


# ------------------------------------------------------------------- order flow

def flow_by_window() -> pd.DataFrame:
    """Taker net flow (buy - sell, USD) per window, against the same clock hours of the
    seven previous days."""
    m = datasets.minute_spot()
    m = m.assign(t=m.time + pd.Timedelta(minutes=1),
                 sell=m.quote_volume - m.taker_buy_quote,
                 net=2 * m.taker_buy_quote - m.quote_volume)
    rows = []
    for name, (a, b) in WINDOWS.items():
        if (b - a) > pd.Timedelta(hours=12):
            continue
        cur = m[(m.t > a) & (m.t <= b)].groupby("coin")[["quote_volume", "net"]].sum()
        base = []
        for k in range(1, 8):
            sa, sb = a - pd.Timedelta(days=k), b - pd.Timedelta(days=k)
            base.append(m[(m.t > sa) & (m.t <= sb)].groupby("coin")[["quote_volume", "net"]].sum())
        base = pd.concat(base).groupby(level=0).mean()
        for c in cur.index:
            rows.append({"window": name, "coin": c,
                         "volume_musd": cur.loc[c, "quote_volume"] / 1e6,
                         "volume_x_normal": cur.loc[c, "quote_volume"] / base.loc[c, "quote_volume"],
                         "net_taker_musd": cur.loc[c, "net"] / 1e6,
                         "buy_share": 0.5 + cur.loc[c, "net"] / (2 * cur.loc[c, "quote_volume"]),
                         "normal_buy_share": 0.5 + base.loc[c, "net"] / (2 * base.loc[c, "quote_volume"])})
    return pd.DataFrame(rows)


def flow_by_size() -> pd.DataFrame:
    """Net taker selling by order size, hack night against the same hours a day earlier."""
    f = datasets.trade_flow()
    f = f.assign(t=f.minute + pd.Timedelta(minutes=1))
    a, b = WINDOWS["night_total"]
    rows = []
    for label, (sa, sb) in {"hack_night": (a, b),
                            "night_before": (a - pd.Timedelta(days=1), b - pd.Timedelta(days=1))}.items():
        g = f[(f.t > sa) & (f.t <= sb)]
        p = g.pivot_table(index=["coin", "size"], columns="side", values="sum", aggfunc="sum",
                          observed=True).fillna(0)
        p["net_musd"] = (p["buy"] - p["sell"]) / 1e6
        p["gross_musd"] = (p["buy"] + p["sell"]) / 1e6
        rows.append(p.reset_index().assign(period=label))
    return pd.concat(rows, ignore_index=True)


def taker_minutes(coin: str, a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    m = datasets.minute_spot().query("coin == @coin")
    m = m.assign(t=m.time + pd.Timedelta(minutes=1)).set_index("t")
    m = m.loc[a:b]
    return pd.DataFrame({"close": m.close, "usd": m.quote_volume,
                         "net": 2 * m.taker_buy_quote - m.quote_volume})


# ------------------------------------------------------------------- derivatives

def open_interest() -> pd.DataFrame:
    """Open interest (USD) change over each window, Binance USD-M perpetuals."""
    mt = datasets.futures_metrics()
    oi = mt.pivot_table(index="time", columns="coin", values="sum_open_interest_value").sort_index()
    rows = []
    for name, (a, b) in WINDOWS.items():
        if b > oi.index.max():
            continue
        a0, b0 = price_at(oi, a), price_at(oi, b)
        for c in oi.columns:
            rows.append({"window": name, "coin": c, "oi_start_musd": a0[c] / 1e6,
                         "oi_end_musd": b0[c] / 1e6, "oi_change": b0[c] / a0[c] - 1})
    return pd.DataFrame(rows)


def basis(w: pd.DataFrame) -> pd.DataFrame:
    """Perpetual futures minus spot, in basis points, per minute."""
    f = datasets.minute_futures().pivot_table(index="time", columns="coin", values="close")
    f.index = f.index + pd.Timedelta(minutes=1)
    common = f.columns.intersection(w.columns)
    return 1e4 * np.log(f[common] / w[common].reindex(f.index)).dropna(how="all")


# ------------------------------------------------------------------- other venues

PHASES = {"week_before": (PRE[0], T0), "hack_night": (T0, T_HALT),
          "withdrawals_halted": (T_HALT, T_REOPEN),
          "reopened": (T_REOPEN, pd.Timestamp("2026-11-03", tz="UTC"))}


def venue_gaps(w: pd.DataFrame) -> pd.DataFrame:
    """Binance price minus the same coin on Coinbase (in USD) and OKX (in USDT), in bp."""
    v = datasets.other_venues()
    v = v.assign(t=v.time + pd.Timedelta(minutes=1))
    cb = v[v.venue == "coinbase"].pivot_table(index="t", columns="coin", values="close")
    okx = v[v.venue == "okx"].pivot_table(index="t", columns="coin", values="close")
    out = {}
    usdt = cb["USDT"]
    for c in ["BTC", "ETH", "SOL", "XRP"]:
        bn_usd = w[c].reindex(cb.index) * usdt
        out[f"{c} vs Coinbase"] = 1e4 * np.log(bn_usd / cb[c])
    for c in ["BTC", "ETH", "BNB", "SOL", "XRP"]:
        out[f"{c} vs OKX"] = 1e4 * np.log(w[c].reindex(okx.index) / okx[c])
    out["USDT on Coinbase"] = 1e4 * np.log(usdt)
    return pd.DataFrame(out).sort_index()


def gap_summary(g: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, (a, b) in PHASES.items():
        x = g[(g.index > a) & (g.index <= b)]
        for col in g.columns:
            s = x[col].dropna()
            rows.append({"phase": name, "pair": col, "mean_bp": s.mean(), "median_bp": s.median(),
                         "p05_bp": s.quantile(0.05), "p95_bp": s.quantile(0.95), "n": len(s)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- stocks

def btc_at_us_close(days: pd.DatetimeIndex) -> pd.Series:
    """Bitcoin price at 16:00 New York on each trading day, from hourly bars, so the
    Bitcoin factor covers exactly the same close-to-close interval as the stocks."""
    from . import sources
    h = sources.binance_klines("BTCUSDT", "1h", "2025-12-01", "2026-11-03")["close"]
    h.index = h.index + pd.Timedelta(hours=1)  # bar end
    out = {}
    for d in days:
        t = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta(hours=16)
        t = t.tz_convert("UTC")
        if h.index.min() <= t <= h.index.max():
            out[d] = h.loc[:t].iloc[-1]
    return pd.Series(out, name="BTC")


def stock_reaction(event_day: str = "2026-10-30", est_days: int = 120) -> pd.DataFrame:
    """Abnormal return of crypto-exposed stocks on the first session after the hack.

    Two-factor market model: QQQ and Bitcoin measured from one New York close to the next.
    The hack began five minutes after the 29 October close, so it falls in the 30 October
    session for stocks.
    """
    mac = datasets.macro_daily()
    px = mac[["QQQ", "COIN", "HOOD", "MSTR", "IBIT", "CRCL"]].dropna(how="all")
    px = px[px["QQQ"].notna()].loc["2026-01-01":]
    px["BTC"] = btc_at_us_close(px.index)
    r = np.log(px).diff()
    day = pd.Timestamp(event_day)
    rows = []
    for d in [pd.Timestamp("2026-10-29"), day, pd.Timestamp("2026-11-02")]:
        hist = r.loc[:d].iloc[:-1].tail(est_days)
        for s in ["COIN", "HOOD", "MSTR", "IBIT", "CRCL"]:
            h = hist[[s, "QQQ", "BTC"]].dropna()
            if len(h) < 60 or d not in r.index:
                continue
            X = np.column_stack([np.ones(len(h)), h["QQQ"], h["BTC"]])
            coef, *_ = np.linalg.lstsq(X, h[s].values, rcond=None)
            sd = (h[s].values - X @ coef).std(ddof=3)
            one = r.loc[d]
            pred_qqq_only = coef[0] + coef[1] * one["QQQ"]
            pred = pred_qqq_only + coef[2] * one["BTC"]
            rows.append({"day": str(d.date()), "stock": s, "ret": one[s], "qqq": one["QQQ"],
                         "btc": one["BTC"], "beta_qqq": coef[1], "beta_btc": coef[2],
                         "abn_vs_qqq": one[s] - pred_qqq_only, "abn_vs_qqq_btc": one[s] - pred,
                         "t_stat": (one[s] - pred) / sd})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- reserves

def reserves() -> pd.DataFrame:
    s = datasets.macro_daily()["binance_assets_usd"].dropna()
    return s.loc["2026-09-01":].to_frame()


def reserve_flows(start: str = "2026-10-15") -> pd.DataFrame:
    """Daily change in the assets DefiLlama tracks on Binance wallets, split into net flows
    (change in token quantities at today's price) and price effect (the rest)."""
    import json

    from .config import RAW
    d = json.loads((RAW / "defillama" / "binance_cex.json").read_text(encoding="utf-8"))
    q = pd.DataFrame([x["tokens"] for x in d["tokens"]],
                     index=pd.to_datetime([x["date"] for x in d["tokens"]], unit="s"))
    usd = pd.DataFrame([x["tokens"] for x in d["tokensInUsd"]],
                       index=pd.to_datetime([x["date"] for x in d["tokensInUsd"]], unit="s"))
    # several snapshots can share a day (the last one is intraday): keep the first per day
    q = q[~q.index.normalize().duplicated(keep="first")]
    usd = usd[~usd.index.normalize().duplicated(keep="first")]
    q.index, usd.index = q.index.normalize(), usd.index.normalize()
    q, usd = q.loc[start:].fillna(0), usd.loc[start:].fillna(0)
    price = (usd / q.replace(0, np.nan)).ffill()
    total = usd.sum(axis=1)
    flows = (q.diff() * price).sum(axis=1)
    out = pd.DataFrame({"assets_bn": total / 1e9, "change_bn": total.diff() / 1e9,
                        "net_flow_bn": flows / 1e9})
    out["price_effect_bn"] = out["change_bn"] - out["net_flow_bn"]
    for k in ["BTC", "ETH", "USDT", "USDC", "XRP", "SOL"]:
        if k in q:
            out[f"{k}_units_change"] = q[k].diff()
    return out


def run() -> dict:
    w = closes()
    return {
        "paths": paths(w),
        "abnormal": abnormal_vs_btc(w),
        "overhang": overhang(w),
        "macro": btc_vs_futures(w),
        "flow": flow_by_window(),
        "flow_size": flow_by_size(),
        "oi": open_interest(),
        "basis": basis(w),
        "gaps": gap_summary(venue_gaps(w)),
        "stocks": stock_reaction(),
        "reserves": reserves(),
    }


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    res = run()
    for k, v in res.items():
        print("=" * 20, k)
        if isinstance(v, dict):
            for kk, vv in v.items():
                print(kk, vv if not isinstance(vv, pd.DataFrame) else vv.round(4).to_string())
        elif k == "basis":
            print(v.describe().round(2).to_string())
        else:
            print(v.round(4).to_string())

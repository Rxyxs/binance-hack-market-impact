"""Static figures for the README and the page (docs/img/*.png)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import IMG, T_CZ_POST, T_FIRST_OUTFLOW, T_HALT, T_REOPEN, US_CLOSE  # noqa: E402

# Validated categorical slots (adjacent and all-pairs CVD checks pass for the first three)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
GRAY_SERIES = "#a8a69f"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "lines.linewidth": 1.4, "figure.dpi": 150,
})


def _save(fig, name: str):
    fig.savefig(IMG / f"{name}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def _vline(ax, t, label, y=0.98, color=INK2):
    ax.axvline(t, color=color, lw=0.8, zorder=1)
    ax.text(t, y, f" {label}", transform=ax.get_xaxis_transform(), fontsize=7.5, color=INK2,
            va="top", ha="left")


def _pct(ax, axis="y", decimals=0):
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.{decimals}f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


# ------------------------------------------------------------------ the night

def night(w: pd.DataFrame, nq: pd.Series):
    a, b = pd.Timestamp("2026-10-29 18:00", tz="UTC"), pd.Timestamp("2026-10-30 08:00", tz="UTC")
    base = w.loc[:US_CLOSE].iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axvspan(US_CLOSE, T_CZ_POST, color="#f0efec", zorder=0)
    nqb = nq.loc[:US_CLOSE].dropna().iloc[-1]
    q = 100 * (nq.loc[a:b].dropna() / nqb - 1)
    q = q.resample("1min").last()  # leaves the futures' daily halt as a gap, not a straight line
    ax.plot(q.index, q.values, color=GRAY_SERIES, lw=1.2, label="Nasdaq-100 futures")
    ends = []
    for coin, col in [("BTC", BLUE), ("BNB", ORANGE), ("ETH", AQUA)]:
        s = 100 * (w[coin].loc[a:b] / base[coin] - 1)
        ax.plot(s.index, s.values, color=col, label=coin)
        ends.append((s.values[-1], f"{coin} {s.values[-1]:+.1f}%", INK))
    qe = q.dropna()
    ends.append((qe.values[-1], f"NQ {qe.values[-1]:+.1f}%", INK2))
    ends.sort()
    ys = [e[0] for e in ends]
    for i in range(1, len(ys)):  # keep end labels at least 0.35 pp apart
        ys[i] = max(ys[i], ys[i - 1] + 0.35)
    for (v, lab, col), y in zip(ends, ys):
        ax.text(b + pd.Timedelta(minutes=8), y, lab, color=col, fontsize=8, va="center")
    for t, lab, y in [(T_FIRST_OUTFLOW, "20:05 first outflow", 0.06), (T_CZ_POST, "21:15 CZ: 'looks like a hack'", 0.12),
                      (T_HALT, "00:13 withdrawals halted", 0.06)]:
        ax.axvline(t, color=INK2, lw=0.8, zorder=1)
        ax.text(t, y, f" {lab}", transform=ax.get_xaxis_transform(), fontsize=7.5, color=INK2,
                va="bottom", ha="left")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xlim(a, b + pd.Timedelta(minutes=120))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
    ax.set_ylabel("change since 20:00 UTC")
    _pct(ax)
    ax.set_title("29-30 October 2026, minute by minute (UTC)")
    ax.legend(loc="upper right", ncol=4, fontsize=8, bbox_to_anchor=(1, 1.0))
    _save(fig, "night")


def decomposition(dec: pd.DataFrame):
    wins = [("before_admission", "20:00-21:15, before any statement"),
            ("to_nov2_close", "20:00 Oct 29 to the close of Nov 2")]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.3))
    coins = ["BTC", "ETH", "BNB"]
    for ax, (win, title) in zip(axes, wins):
        d = dec[dec.window == win].set_index("coin").loc[coins]
        y = np.arange(len(coins))
        ex, ab = 100 * d["explained"].values, 100 * d["abnormal"].values
        ax.barh(y - 0.17, ex, height=0.32, color=BLUE, label="explained by Nasdaq futures, dollar, gold")
        ax.barh(y + 0.17, ab, height=0.32, color=ORANGE, label="abnormal: the hack")
        for i in range(len(coins)):
            for v, off in [(ex[i], -0.17), (ab[i], 0.17)]:
                ax.text(v, y[i] + off, f" {v:+.1f} " if v >= 0 else f" {v:+.1f} ", va="center",
                        ha="left" if v >= 0 else "right", fontsize=7.5, color=INK2)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_yticks(y, [f"{c}\ntotal {100 * t:+.1f}%" for c, t in zip(coins, d["actual"].values)],
                      fontsize=8)
        ax.set_title(title, fontsize=9.5)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5, integer=True))
        _pct(ax, "x", 0)
        lo = min(ex.min(), ab.min(), 0) * 1.35
        hi = max(ex.max(), ab.max(), 0) * 1.35 + 0.3
        ax.set_xlim(lo, hi)
        ax.invert_yaxis()
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.13), ncol=2, fontsize=8)
    fig.tight_layout()
    _save(fig, "decomposition")


def cross_section(ab: pd.DataFrame, window: str = "to_reopen"):
    d = ab[(ab.window == window) & (ab.coin != "BTC") & (ab.group != "other")].copy()
    order = {"exchange token": 0, "stolen chain": 1, "untouched chain": 2}
    d = d.sort_values(["group", "abn"], key=lambda s: s.map(order) if s.name == "group" else s)
    colors = {"exchange token": ORANGE, "stolen chain": BLUE, "untouched chain": AQUA}
    fig, ax = plt.subplots(figsize=(8, 6.2))
    y = np.arange(len(d))
    ax.hlines(y, 0, 100 * d["abn"], color=GRID, lw=1.2)
    for g, c in colors.items():
        m = d.group.eq(g).values
        ax.scatter(100 * d["abn"].values[m], y[m], s=36, color=c, label=g, zorder=3,
                   edgecolor=SURFACE, linewidth=1)
        mean = 100 * d.loc[d.group == g, "abn"].mean()
        ax.text(1.0, y[m].mean(), f"{g}\nmean {mean:+.1f} pp", transform=ax.get_yaxis_transform(),
                fontsize=8, color=INK2, va="center", ha="left")
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_yticks(y, d.coin)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    _pct(ax, "x", 0)
    ax.set_xlabel("return minus beta x Bitcoin, 20:00 Oct 29 to withdrawals reopening (pp)")
    ax.set_title("Coins from drained chains did no worse than the rest")
    ax.legend(loc="lower left", fontsize=8)
    _save(fig, "cross_section")


def flow(minutes: dict[str, pd.DataFrame], baseline: dict[str, pd.Series], size: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 3.6), gridspec_kw={"width_ratios": [1.3, 1]})
    for coin, col in [("BTC", BLUE), ("BNB", ORANGE)]:
        m = minutes[coin]
        c = m["net"].cumsum() / 1e6
        a1.plot(c.index, c.values, color=col, label=f"{coin}, hack night")
        bl = baseline[coin]
        a1.plot(c.index[:len(bl)], bl.values[:len(c)], color=col, lw=0.9, alpha=0.45,
                label=f"{coin}, average of 7 prior nights")
    _vline(a1, T_CZ_POST, "21:15")
    _vline(a1, T_HALT, "00:13")
    a1.axhline(0, color=AXIS, lw=0.8)
    a1.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz="UTC"))
    a1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
    a1.set_ylabel("cumulative taker buys minus sells, $M")
    a1.set_title("Net taker flow, Binance spot, from 20:00 UTC", fontsize=9.5)
    a1.legend(fontsize=7.5, loc="lower left")
    s = size[size.coin == "BTC"].pivot_table(index="size", columns="period", values="net_musd",
                                             observed=True)
    labels = ["<1k", "1k-10k", "10k-100k", "100k-1M", ">1M"]
    s = s.reindex(labels).fillna(0)
    x = np.arange(len(labels))
    a2.bar(x - 0.2, s["night_before"], width=0.38, color=GRAY_SERIES, label="night before")
    a2.bar(x + 0.2, s["hack_night"], width=0.38, color=BLUE, label="hack night")
    a2.axhline(0, color=AXIS, lw=0.8)
    a2.set_xticks(x, labels, fontsize=8)
    a2.set_xlabel("size of each aggressive order, USD")
    a2.set_ylabel("net taker flow, $M")
    a2.set_title("BTC 20:00-06:00, by order size", fontsize=9.5)
    a2.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, "flow")


def venues(g: pd.DataFrame):
    cols = [("BTC vs Coinbase", BLUE), ("BNB vs OKX", ORANGE)]
    a, b = pd.Timestamp("2026-10-27", tz="UTC"), pd.Timestamp("2026-11-03", tz="UTC")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.axvspan(T_HALT, T_REOPEN, color="#f0efec", zorder=0)
    ax.text(T_HALT + (T_REOPEN - T_HALT) / 2, 0.96, "withdrawals halted", transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=8, color=INK2)
    for c, col in cols:
        s = g[c].loc[a:b].resample("15min").median()
        ax.plot(s.index, s.values, color=col, label=f"Binance {c}", lw=1.1)
    ax.axhline(0, color=AXIS, lw=0.8)
    _vline(ax, T_FIRST_OUTFLOW, "hack", y=0.85)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz="UTC"))
    ax.set_ylabel("price gap, basis points")
    ax.set_title("Binance prices against other exchanges (15-minute medians)")
    ax.legend(fontsize=8, loc="upper left")
    _save(fig, "venues")


# ------------------------------------------------------------------ history

def event_study(tab: pd.DataFrame, placebo_vals: np.ndarray):
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    lo, hi = np.quantile(placebo_vals, [0.05, 0.95])
    ax.axhspan(lo, hi, color="#f0efec", zorder=0)
    ax.text(0.01, hi, " 90% of random two-day windows", transform=ax.get_yaxis_transform(),
            fontsize=7.5, color=INK2, va="bottom")
    is_b = tab.name.str.contains("Binance") & (pd.to_datetime(tab.date).dt.year == 2026)
    ax.scatter(tab.amount_m[~is_b], tab.scar_1[~is_b], s=26, color=BLUE, edgecolor=SURFACE,
               lw=1, zorder=3, label="other exchange hacks")
    ax.scatter(tab.amount_m[is_b], tab.scar_1[is_b], s=60, color=ORANGE, edgecolor=SURFACE,
               lw=1, zorder=4, label="Binance, Oct 2026")
    for _, r in tab.iterrows():
        yr = pd.Timestamp(r.date).year
        if r.amount_m >= 400 or abs(r.scar_1) > 1.9:
            below = r["name"].startswith("Mt. Gox")
            ax.annotate(f"{r['name'].replace(' CEX', '')} {yr}", (r.amount_m, r.scar_1),
                        xytext=(4, -10 if below else 3), textcoords="offset points", fontsize=7.5,
                        color=INK2)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks([30, 100, 300, 1000, 3000], ["$30M", "$100M", "$300M", "$1B", "$3B"])
    ax.set_xlabel("amount stolen (log scale)")
    ax.set_ylabel("Bitcoin abnormal return, days 0-1 (sd units)")
    ax.set_title("36 exchange hacks of $30M or more since 2011: no average effect on Bitcoin")
    ax.legend(fontsize=8, loc="upper right")
    _save(fig, "event_study")


def history(btc: pd.Series, hacks: pd.DataFrame, by_year: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True,
                                 gridspec_kw={"height_ratios": [2.2, 1]})
    a1.plot(btc.index, btc.values, color=BLUE, lw=1.0)
    a1.set_yscale("log")
    a1.set_ylabel("Bitcoin, USD (log)")
    big = hacks[(hacks.targetType == "CEX") & (hacks.amount >= 100e6)]
    for _, h in big.iterrows():
        d = h.date.normalize()
        if d < btc.index.min():
            continue
        p = btc.loc[:d].iloc[-1]
        a1.scatter([d], [p], s=10 + 60 * np.sqrt(h.amount / 1e9), color=ORANGE, zorder=3,
                   edgecolor=SURFACE, lw=1)
        if h.amount >= 450e6:
            a1.annotate(f"{h['name'].replace(' CEX', '')}", (d, p), xytext=(-6, 9),
                        textcoords="offset points", fontsize=7.5, color=INK2, ha="right")
    a1.set_title("Bitcoin and every exchange hack of $100M or more (dot area ~ amount)")
    yrs = pd.to_datetime(by_year.year.astype(str) + "-07-01")
    a2.bar(yrs, by_year.stolen_bn - by_year.cex_stolen_bn, width=300, color=GRAY_SERIES,
           label="DeFi, bridges, other")
    a2.bar(yrs, by_year.cex_stolen_bn, width=300, bottom=by_year.stolen_bn - by_year.cex_stolen_bn,
           color=ORANGE, label="centralized exchanges")
    a2.set_ylabel("stolen per year, $bn")
    a2.text(yrs.iloc[-1], by_year.stolen_bn.iloc[-1], "to 2 Nov", ha="center", va="bottom", fontsize=7.5,
            color=INK2)
    a2.legend(fontsize=8, loc="upper left")
    _save(fig, "history")


def context_2026(btc: pd.Series, brent: pd.Series, us10y: pd.Series, gpr: pd.Series):
    a = pd.Timestamp("2026-01-01")
    fig, axes = plt.subplots(4, 1, figsize=(9, 7.2), sharex=True)
    series = [(btc, "Bitcoin, USD", BLUE), (brent, "Brent crude, USD/bbl", INK2),
              (us10y, "US 10-year yield, %", INK2), (gpr.rolling(7).mean(), "Geopolitical risk index (7-day mean)", INK2)]
    for ax, (s, lab, col) in zip(axes, series):
        s = s.loc[a:].dropna()
        ax.plot(s.index, s.values, color=col, lw=1.1)
        ax.set_title(lab, fontsize=9)
    marks = [("2026-02-28", "Iran war begins"), ("2026-04-08", "ceasefire"), ("2026-06-17", "peace memo"),
             ("2026-07-08", "truce collapses"), ("2026-09-24", "Bitget hack"), ("2026-10-29", "Binance hack")]
    for ax in axes:
        for d, lab in marks:
            ax.axvline(pd.Timestamp(d), color=ORANGE if "hack" in lab else AXIS, lw=0.8, zorder=1)
    for i, (d, lab) in enumerate(marks):
        axes[0].text(pd.Timestamp(d), 1.03 + 0.11 * (i % 2), lab, transform=axes[0].get_xaxis_transform(),
                     fontsize=7, color=INK2, ha="center", va="bottom")
    axes[0].set_title("Bitcoin, USD", fontsize=9, pad=26)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.tight_layout()
    _save(fig, "context_2026")


def detector_traces(cases: dict):
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.4))
    for ax, key, title in [(axes[0], "2026", "October 2026"), (axes[1], "2019", "May 2019")]:
        c = cases[key]
        z = c["z_trace"]
        ax.plot(z.index, z.values, color=BLUE, lw=0.9)
        ax.axhline(-c["threshold"], color=ORANGE, lw=1)
        ax.text(z.index[0], -c["threshold"], f" alarm level -{c['threshold']:.1f}", fontsize=7.5,
                color=INK2, va="bottom")
        _vline(ax, pd.Timestamp(c["event"]), "theft", y=0.2)
        _vline(ax, pd.Timestamp(c["admitted"]), "admitted", y=0.1)
        if c["alarm"]:
            t = pd.Timestamp(c["alarm"])
            ax.scatter([t], [z.loc[t]], color=ORANGE, s=30, zorder=4)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
        ax.set_title(f"{title}: BNB abnormal move vs BTC (robust z)", fontsize=9)
    _save(fig, "detector")


# ------------------------------------------------------------------ models

def skill(y1: pd.DataFrame, y7: pd.DataFrame, vol: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.2))
    models = [("base_mean", "historical mean"), ("ridge", "ridge"), ("lgb", "LightGBM"), ("mlp", "MLP")]
    x = np.arange(len(models))
    for off, (tab, lab, col) in zip([-0.2, 0.2], [(y1, "next day", BLUE), (y7, "next 7 days", AQUA)]):
        t = tab[tab.coin == "all"].set_index("model")
        vals = [100 * t.loc[m, "r2_vs_zero"] if m in t.index else np.nan for m, _ in models]
        a1.bar(x + off, vals, width=0.38, color=col, label=lab)
    a1.axhline(0, color=AXIS, lw=0.8)
    a1.set_xticks(x, [m[1] for m in models], fontsize=8)
    a1.set_ylabel("out-of-sample R2 vs predicting 0, %")
    a1.set_title("Returns: no model beats 'no change'")
    a1.legend(fontsize=8)
    t = vol[vol.coin == "all"].set_index("model")
    vm = [("base_persist", "last 30 days"), ("har", "HAR"), ("ridge", "ridge"), ("lgb", "LightGBM"),
          ("mlp", "MLP")]
    vals = [100 * t.loc[m, "r2"] if m in t.index else np.nan for m, _ in vm]
    a2.bar(np.arange(len(vm)), vals, width=0.6, color=[GRAY_SERIES, BLUE, GRAY_SERIES, GRAY_SERIES, GRAY_SERIES])
    for i, v in enumerate(vals):
        a2.text(i, v, f"{v:.0f}%", ha="center", va="bottom", fontsize=8, color=INK2)
    a2.set_xticks(np.arange(len(vm)), [m[1] for m in vm], fontsize=8)
    a2.set_ylabel("out-of-sample R2, log volatility, %")
    a2.set_title("Volatility: past volatility does the work")
    fig.tight_layout()
    _save(fig, "skill")


def ablation(ab: pd.DataFrame):
    names = {"derivatives": "futures funding", "macro_markets": "stocks, rates, dollar, oil",
             "war_policy_news": "war and policy news indices", "sentiment_attention": "Fear & Greed, Wikipedia",
             "onchain_supply": "hash rate, stablecoins, reserves", "hacks": "hack register"}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.4), sharey=True)
    for ax, (tgt, title) in zip(axes, [("y1", "Next-day return"), ("rv7_fwd", "Next-week volatility")]):
        d = ab[(ab.target == tgt) & (ab.group != "all")].set_index("group").loc[list(names)]
        v = -100 * d["add_to_price_mse_change"].values
        y = np.arange(len(d))
        ax.barh(y, v, color=[BLUE if x > 0 else GRAY_SERIES for x in v], height=0.6)
        for i, x in enumerate(v):
            ax.text(x, i, f" {x:+.1f}%", va="center", ha="left" if x >= 0 else "right", fontsize=8,
                    color=INK2)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_yticks(y, [names[g] for g in d.index], fontsize=8)
        ax.set_title(title, fontsize=9.5)
        _pct(ax, "x", 1)
        lo, hi = min(v.min(), 0), max(v.max(), 0)
        pad = 0.35 * (hi - lo)
        ax.set_xlim(lo - pad, hi + pad)
        ax.invert_yaxis()
    fig.suptitle("Out-of-sample error reduction when each group is added to price and volume data "
                 "(positive = helps)", x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    _save(fig, "ablation")


def nowcast(hist: dict[str, pd.Series], fc: pd.DataFrame):
    coins = list(hist)
    fig, axes = plt.subplots(1, len(coins), figsize=(11, 2.8))
    for ax, c in zip(axes, coins):
        h = hist[c].iloc[-45:]
        ax.plot(h.index, h.values, color=BLUE, lw=1.1)
        f = fc[fc.coin == c].sort_values("horizon")
        last_t, last_p = h.index[-1], h.values[-1]
        t = [last_t] + list(f["target_date"])
        ax.fill_between(t, [last_p] + list(f["p05"]), [last_p] + list(f["p95"]), color=BLUE, alpha=0.15,
                        lw=0)
        ax.plot(t, [last_p] + list(f["p50"]), color=BLUE, lw=1.1, ls=(0, (1, 1.5)))
        ax.set_title(c, fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.tick_params(axis="x", labelsize=7, rotation=0)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=20))
    fig.suptitle("Price paths with the 90% band for the next 1 and 7 days (dotted: median)",
                 x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    _save(fig, "nowcast")


def reserve_flows(fl: pd.DataFrame):
    """Daily net flows on Binance wallets, dated by the day they happened."""
    d = fl.dropna(subset=["net_flow_bn"]).copy()
    d.index = d.index - pd.Timedelta(days=1)  # a 00:00 snapshot closes the previous day
    fig, ax = plt.subplots(figsize=(9, 3.2))
    col = [ORANGE if x.date() in (pd.Timestamp("2026-10-29").date(),) else
           (BLUE if v < -1.5 else GRAY_SERIES) for x, v in zip(d.index, d.net_flow_bn)]
    ax.bar(d.index, d.net_flow_bn, width=0.75, color=col)
    for t, v in d.net_flow_bn.items():
        if abs(v) > 1.4:
            ax.text(t, v, f"{v:+.1f}", ha="center", va="top" if v < 0 else "bottom", fontsize=8,
                    color=INK2)
    ax.text(pd.Timestamp("2026-10-29"), 0.5, "theft", ha="center", fontsize=8, color=INK2)
    ax.text(pd.Timestamp("2026-10-30") + pd.Timedelta(hours=12), 0.5, "halted", ha="center",
            fontsize=8, color=INK2)
    ax.text(pd.Timestamp("2026-11-01") + pd.Timedelta(hours=12), 0.5, "reopened", ha="center",
            fontsize=8, color=INK2)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_ylabel("net flow, $bn")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.set_title("Coins entering and leaving Binance's wallets per day (price moves removed)")
    _save(fig, "reserve_flows")


def stocks(st: pd.DataFrame):
    d = st[st.day == "2026-10-30"].set_index("stock")
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    y = np.arange(len(d))
    v = 100 * d["abn_vs_qqq_btc"].values
    sd = 100 * (d["abn_vs_qqq_btc"] / d["t_stat"]).values
    ax.errorbar(v, y, xerr=1.96 * sd, fmt="o", color=BLUE, ecolor=GRAY_SERIES, elinewidth=1.2,
                capsize=0, ms=6)
    for i, x in enumerate(v):
        ax.text(x, i - 0.22, f"{x:+.1f}%", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_yticks(y, d.index)
    ax.set_ylim(len(d) - 0.5, -0.8)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    _pct(ax, "x", 0)
    ax.set_xlabel("abnormal return on 30 Oct vs Nasdaq-100 and Bitcoin (bars: 95% range of normal days)")
    ax.set_title("Crypto stocks on the first session after the hack")
    _save(fig, "stocks")

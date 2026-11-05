"""Static figures in Spanish (docs/img/es/) and English (docs/img/). Every title states what
the chart shows, and labels avoid jargon. `render_all` needs the downloaded data and
reports/results.json; it never refits a model."""
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
RED = "#e34948"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE, BAND = "#e1e0d9", "#c3c2b7", "#fcfcfb", "#f0efec"
GRAY_SERIES = "#a8a69f"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "lines.linewidth": 1.4, "figure.dpi": 150, "axes.axisbelow": True,
})

LANG = "es"
MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def T(es: str, en: str) -> str:
    return es if LANG == "es" else en


def N(x: float, d: int = 1, sign: bool = False, suffix: str = "") -> str:
    """Number with the decimal mark of the current language."""
    s = f"{x:+,.{d}f}" if sign else f"{x:,.{d}f}"
    if LANG == "es":
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s + suffix


def _save(fig, name: str):
    folder = IMG / "es" if LANG == "es" else IMG
    folder.mkdir(parents=True, exist_ok=True)
    fig.savefig(folder / f"{name}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def _vline(ax, t, label, y=0.98, color=INK2):
    ax.axvline(t, color=color, lw=0.8, zorder=1)
    ax.text(t, y, f" {label}", transform=ax.get_xaxis_transform(), fontsize=8, color=INK2, va="top", ha="left")


def _pct(ax, axis="y", d=0, sign=False):
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: N(v, d, sign, "%"))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _thousands(ax):
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: N(v, 0)))


def _day_month(ax):
    months = MONTHS_ES if LANG == "es" else MONTHS_EN
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: (lambda d: f"{d.day} {months[d.month - 1]}")(mdates.num2date(v))))


def _month(ax):
    months = MONTHS_ES if LANG == "es" else MONTHS_EN
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: months[mdates.num2date(v).month - 1]))


# ------------------------------------------------------------------ the night

def night(w: pd.DataFrame, nq: pd.Series):
    a, b = pd.Timestamp("2026-10-29 18:00", tz="UTC"), pd.Timestamp("2026-10-30 08:00", tz="UTC")
    base = w.loc[:US_CLOSE].iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axvspan(US_CLOSE, T_CZ_POST, color=BAND, zorder=0)
    nqb = nq.loc[:US_CLOSE].dropna().iloc[-1]
    q = 100 * (nq.loc[a:b].dropna() / nqb - 1)
    q = q.resample("1min").last()  # leaves the futures' daily halt as a gap, not a straight line
    ax.plot(q.index, q.values, color=GRAY_SERIES, lw=1.2, label=T("Bolsa tecnológica (futuros Nasdaq)", "Tech stocks (Nasdaq futures)"))
    ends = []
    for coin, col in [("BTC", BLUE), ("BNB", ORANGE), ("ETH", AQUA)]:
        s = 100 * (w[coin].loc[a:b] / base[coin] - 1)
        ax.plot(s.index, s.values, color=col, label=coin)
        ends.append((s.values[-1], f"{coin} {N(s.values[-1], 1, True, '%')}", INK))
    qe = q.dropna()
    ends.append((qe.values[-1], f"Nasdaq {N(qe.values[-1], 1, True, '%')}", INK2))
    ends.sort()
    ys = [e[0] for e in ends]
    for i in range(1, len(ys)):  # keep end labels at least 0.35 pp apart
        ys[i] = max(ys[i], ys[i - 1] + 0.35)
    for (_, lab, col), y in zip(ends, ys):
        ax.text(b + pd.Timedelta(minutes=8), y, lab, color=col, fontsize=8, va="center")
    for t, lab, y in [(T_FIRST_OUTFLOW, T("20:05 sale el primer robo", "20:05 first theft"), 0.06),
                      (T_CZ_POST, T("21:15 CZ: \"parece un hackeo\"", "21:15 CZ: \"looks like a hack\""), 0.12),
                      (T_HALT, T("00:13 suspenden retiros", "00:13 withdrawals halted"), 0.06)]:
        ax.axvline(t, color=INK2, lw=0.8, zorder=1)
        ax.text(t, y, f" {lab}", transform=ax.get_xaxis_transform(), fontsize=8, color=INK2, va="bottom", ha="left")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xlim(a, b + pd.Timedelta(minutes=130))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
    ax.set_ylabel(T("cambio desde las 20:00 UTC", "change since 20:00 UTC"))
    ax.set_xlabel(T("hora UTC, noche del 29 al 30 de octubre", "UTC time, night of 29-30 October"))
    _pct(ax)
    ax.set_title(T("BNB se desplomó antes de que nadie hablara; el Nasdaq también caía",
                   "BNB plunged before anyone spoke; the Nasdaq was falling too"))
    ax.legend(loc="upper right", ncol=4, fontsize=8)
    _save(fig, "night")


def decomposition(dec: pd.DataFrame):
    wins = [("before_admission", T("Primeros 75 minutos (20:00-21:15)", "First 75 minutes (20:00-21:15)")),
            ("to_nov2_close", T("Hasta el cierre del 2 de noviembre", "To the close of 2 November"))]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.7))
    coins = ["BTC", "ETH", "BNB"]
    for ax, (win, title) in zip(axes, wins):
        d = dec[dec.window == win].set_index("coin").loc[coins]
        y = np.arange(len(coins))
        ex, ab = 100 * d["explained"].values, 100 * d["abnormal"].values
        ax.barh(y - 0.17, ex, height=0.32, color=GRAY_SERIES,
                label=T("lo que predicen Nasdaq, dólar y oro", "predicted by Nasdaq, dollar and gold"))
        ax.barh(y + 0.17, ab, height=0.32, color=ORANGE,
                label=T("el resto: efecto propio del hackeo", "the rest: the hack's own effect"))
        for i in range(len(coins)):
            for v, off in [(ex[i], -0.17), (ab[i], 0.17)]:
                ax.text(v, y[i] + off, f" {N(v, 1, True)} ", va="center", ha="left" if v >= 0 else "right",
                        fontsize=8, color=INK2)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_yticks(y, [f"{c}\n{T('cayó', 'fell')} {N(-100 * t, 1, False, '%')}" for c, t in zip(coins, d["actual"].values)],
                      fontsize=8.5)
        ax.set_title(title, fontsize=10)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5, integer=True))
        _pct(ax, "x")
        ax.set_xlim(min(ex.min(), ab.min(), 0) * 1.35, max(ex.max(), ab.max(), 0) * 1.35 + 0.3)
        ax.invert_yaxis()
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, fontsize=8.5)
    fig.suptitle(T("El hackeo pesó al comienzo; a los 4 días, la mayor parte de la caída de BTC la predice el Nasdaq",
                   "The hack mattered at first; four days on, the Nasdaq predicts most of BTC's fall"),
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    _save(fig, "decomposition")


def cross_section(ab: pd.DataFrame, window: str = "to_reopen"):
    d = ab[(ab.window == window) & (ab.coin != "BTC") & (ab.group != "other")].copy()
    order = {"exchange token": 0, "stolen chain": 1, "untouched chain": 2}
    names = {"exchange token": T("token de Binance", "Binance's token"),
             "stolen chain": T("cadenas robadas", "drained chains"),
             "untouched chain": T("cadenas no tocadas", "untouched chains")}
    d = d.sort_values(["group", "abn"], key=lambda s: s.map(order) if s.name == "group" else s)
    colors = {"exchange token": ORANGE, "stolen chain": BLUE, "untouched chain": AQUA}
    fig, ax = plt.subplots(figsize=(8, 6.2))
    y = np.arange(len(d))
    ax.hlines(y, 0, 100 * d["abn"], color=GRID, lw=1.2)
    for g, c in colors.items():
        m = d.group.eq(g).values
        ax.scatter(100 * d["abn"].values[m], y[m], s=36, color=c, label=names[g], zorder=3, edgecolor=SURFACE, linewidth=1)
        mean = 100 * d.loc[d.group == g, "abn"].mean()
        ax.text(1.0, y[m].mean(), f"{names[g]}\n{T('promedio', 'average')} {N(mean, 1, True)}",
                transform=ax.get_yaxis_transform(), fontsize=8, color=INK2, va="center", ha="left")
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_yticks(y, d.coin)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    _pct(ax, "x", 0, True)
    ax.set_xlabel(T("a la derecha le fue mejor que a Bitcoin; a la izquierda, peor (20:00 del 29 oct a la reapertura)",
                    "right: did better than Bitcoin; left: worse (20:00 Oct 29 to the reopening)"))
    ax.set_title(T("Las monedas robadas no cayeron más que las otras", "Stolen coins did not fall more than the others"))
    ax.legend(loc="lower left", fontsize=8)
    _save(fig, "cross_section")


def flow(minutes: dict[str, pd.DataFrame], baseline: dict[str, pd.Series], size: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 3.7), gridspec_kw={"width_ratios": [1.3, 1]})
    for coin, col in [("BTC", BLUE), ("BNB", ORANGE)]:
        m = minutes[coin]
        c = m["net"].cumsum() / 1e6
        a1.plot(c.index, c.values, color=col, label=T(f"{coin}, noche del hackeo", f"{coin}, hack night"))
        bl = baseline[coin]
        a1.plot(c.index[:len(bl)], bl.values[:len(c)], color=col, lw=0.9, alpha=0.45,
                label=T(f"{coin}, promedio 7 noches previas", f"{coin}, average of 7 prior nights"))
    _vline(a1, T_CZ_POST, "21:15")
    _vline(a1, T_HALT, "00:13")
    a1.axhline(0, color=AXIS, lw=0.8)
    a1.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz="UTC"))
    a1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
    a1.set_ylabel(T("compras menos ventas a mercado, US$ M", "market buys minus sells, $M"))
    a1.set_title(T("Vendieron de golpe, en dos oleadas", "They sold in two waves"), fontsize=10)
    a1.legend(fontsize=7.5, loc="lower left")
    s = size[size.coin == "BTC"].pivot_table(index="size", columns="period", values="net_musd", observed=True)
    order = ["<1k", "1k-10k", "10k-100k", "100k-1M", ">1M"]
    labels = T("<1 mil|1-10 mil|10-100 mil|100 mil-1 M|>1 M", "<1k|1k-10k|10k-100k|100k-1M|>1M").split("|")
    s = s.reindex(order).fillna(0)
    x = np.arange(len(order))
    a2.bar(x - 0.2, s["night_before"], width=0.38, color=GRAY_SERIES, label=T("noche anterior", "night before"))
    a2.bar(x + 0.2, s["hack_night"], width=0.38, color=BLUE, label=T("noche del hackeo", "hack night"))
    a2.axhline(0, color=AXIS, lw=0.8)
    a2.set_xticks(x, labels, fontsize=7.5)
    a2.set_xlabel(T("tamaño de cada orden, US$", "size of each order, USD"))
    a2.set_ylabel(T("compras menos ventas, US$ M", "buys minus sells, $M"))
    a2.set_title(T("BTC: pesan las órdenes chicas", "BTC: small orders weigh most"), fontsize=10)
    a2.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, "flow")


def hack_days(days: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    w = pd.Timedelta(hours=8)
    for off, (c, col) in zip([-1, 0], [("BTC", BLUE), ("BNB", ORANGE)]):
        d = days[days.coin == c]
        t = pd.to_datetime(d["date"]) + pd.Timedelta(hours=12)
        a1.bar(t + off * w + w / 2, d["volume_x_normal"], width=w, color=col, label=c)
        a2.plot(t, 100 * d["buy_share"], color=col, marker="o", ms=4, label=c)
    b = days[days.coin == "BNB"]
    top = b.loc[b["volume_x_normal"].idxmax()]
    a1.annotate(f"BNB: {N(top['volume_x_normal'], 1)} {T('veces lo normal', 'times normal')}",
                (pd.Timestamp(top["date"]), top["volume_x_normal"]), xytext=(-6, -6), textcoords="offset points",
                fontsize=8.5, color=INK2, ha="right")
    a1.axhline(1, color=INK2, lw=0.8)
    a1.text(pd.to_datetime(days["date"]).min(), 1.08, T(" 1 = volumen normal", " 1 = normal volume"), fontsize=8, color=INK2)
    a1.set_ylabel(T("volumen / promedio de\nlos 30 días previos", "volume / average of\nprior 30 days"))
    a1.set_title(T("El hackeo multiplicó el volumen dos días; después volvió a lo normal",
                   "The hack multiplied volume for two days, then it went back to normal"))
    a1.legend(fontsize=8, loc="upper right")
    a2.axhline(50, color=INK2, lw=0.8)
    a2.text(pd.to_datetime(days["date"]).min(), 50.4, T(" sobre 50%: dominan los compradores", " above 50%: buyers dominate"),
            fontsize=8, color=INK2)
    a2.set_ylabel(T("% del volumen iniciado\npor compradores", "% of volume started\nby buyers"))
    _pct(a2)
    for ax in (a1, a2):
        ax.axvline(pd.Timestamp("2026-10-29 20:00"), color=RED, lw=1)
    a2.text(pd.Timestamp("2026-10-29 20:00"), 0.03, T(" hackeo", " hack"), transform=a2.get_xaxis_transform(), color=INK2, fontsize=8)
    a2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    _day_month(a2)
    fig.tight_layout()
    _save(fig, "hack_days")


def venues(g: pd.DataFrame):
    a, b = pd.Timestamp("2026-10-27", tz="UTC"), pd.Timestamp("2026-11-03", tz="UTC")
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.axvspan(T_HALT, T_REOPEN, color=BAND, zorder=0)
    ax.text(T_HALT + (T_REOPEN - T_HALT) / 2, 0.96, T("retiros suspendidos", "withdrawals halted"),
            transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=8, color=INK2)
    for c, col, lab in [("BTC vs Coinbase", BLUE, T("BTC: Binance vs Coinbase", "BTC: Binance vs Coinbase")),
                        ("BNB vs OKX", ORANGE, T("BNB: Binance vs OKX", "BNB: Binance vs OKX"))]:
        s = g[c].loc[a:b].resample("15min").median() / 100
        ax.plot(s.index, s.values, color=col, label=lab, lw=1.1)
    ax.axhline(0, color=AXIS, lw=0.8)
    _vline(ax, T_FIRST_OUTFLOW, T("hackeo", "hack"), y=0.85)
    _day_month(ax)
    ax.set_ylabel(T("Binance más caro en...", "Binance dearer by..."))
    _pct(ax, "y", 2)
    ax.set_title(T("Sin poder retirar, Binance quedó apenas 0,1% más caro: el mercado no temió una quiebra",
                   "Unable to withdraw, Binance sat just 0.1% dearer: the market did not fear a collapse"))
    ax.legend(fontsize=8, loc="upper left")
    _save(fig, "venues")


def reserve_flows(rf: dict):
    d = pd.DataFrame(rf).T
    d.index = pd.to_datetime(d.index)
    d = d.dropna(subset=["net_flow_bn"]).sort_index()
    fig, ax = plt.subplots(figsize=(9, 3.4))
    theft = pd.Timestamp("2026-10-29")
    col = [ORANGE if x == theft else (BLUE if v < -1.5 else GRAY_SERIES) for x, v in zip(d.index, d.net_flow_bn)]
    ax.bar(d.index, d.net_flow_bn, width=0.75, color=col)
    for t, v in d.net_flow_bn.items():
        if abs(v) > 1.4:
            ax.text(t, v, N(v, 1, True), ha="center", va="top" if v < 0 else "bottom", fontsize=8.5, color=INK2)
    for t, lab in [(theft, T("robo", "theft")), (pd.Timestamp("2026-10-30 12:00"), T("cerrado", "halted")),
                   (pd.Timestamp("2026-11-01 12:00"), T("clientes retiran", "customers withdraw"))]:
        ax.text(t, 0.55, lab, ha="center", fontsize=8.5, color=INK2)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_ylabel(T("entradas menos salidas,\nmiles de millones US$", "inflows minus outflows,\n$ billion"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    _day_month(ax)
    ax.set_title(T("Después del robo, los clientes retiraron otros US$8.700 millones en dos días",
                   "After the theft, customers withdrew another $8.7 billion in two days"))
    _save(fig, "reserve_flows")


def stocks(st: pd.DataFrame):
    d = st[st.day == "2026-10-30"].set_index("stock").loc[["COIN", "HOOD", "MSTR", "CRCL", "IBIT"]]
    names = {"COIN": "Coinbase", "HOOD": "Robinhood", "MSTR": "Strategy", "CRCL": "Circle", "IBIT": "IBIT (ETF BTC)"}
    real = 100 * d["ret"].values
    expected = real - 100 * d["abn_vs_qqq_btc"].values
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(y - 0.19, expected, height=0.36, color=GRAY_SERIES, label=T("lo esperable por Nasdaq y Bitcoin", "expected from Nasdaq and Bitcoin"))
    ax.barh(y + 0.19, real, height=0.36, color=BLUE, label=T("lo que cayó de verdad", "what it really fell"))
    for i in range(len(d)):
        ax.text(expected[i], y[i] - 0.19, f" {N(expected[i], 1, True, '%')} ", va="center", ha="right", fontsize=8, color=INK2)
        ax.text(real[i], y[i] + 0.19, f" {N(real[i], 1, True, '%')} ", va="center", ha="right", fontsize=8, color=INK2)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_yticks(y, [names[s] for s in d.index])
    ax.set_xlim(min(real.min(), expected.min()) * 1.3, 0.5)
    ax.invert_yaxis()
    _pct(ax, "x")
    ax.set_title(T("Las acciones cripto cayeron casi lo esperable el 30 de octubre", "Crypto stocks fell about as expected on 30 October"))
    ax.legend(fontsize=8, loc="lower left", bbox_to_anchor=(0, -0.3), ncol=2)
    _save(fig, "stocks")


def detector_traces(cases: dict):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    titles = {"2026": T("2026: el precio avisó 42 min antes", "2026: price warned 42 min before"),
              "2019": T("2019: el precio esperó el anuncio", "2019: price waited for the announcement")}
    for ax, key in zip(axes, ["2026", "2019"]):
        c = cases[key]
        s = c["rel_trace"]
        ev, ad = pd.Timestamp(c["event"]), pd.Timestamp(c["admitted"])
        ax.plot(s.index, s.values, color=BLUE, lw=1)
        ax.axvspan(ev, ad, color=BAND, zorder=0)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.axvline(ev, color=INK2, lw=0.8)
        ax.axvline(ad, color=INK2, lw=0.8)
        lo = s.min()
        ax.text(ev, 0.03, T(" robo", " theft"), transform=ax.get_xaxis_transform(), fontsize=8, color=INK2)
        ax.text(ad, 0.92, T(" lo admiten", " admitted"), transform=ax.get_xaxis_transform(), fontsize=8, color=INK2)
        t = pd.Timestamp(c["alarm"])
        v = s.loc[:t].iloc[-1]
        ax.scatter([t], [v], color=ORANGE, s=45, zorder=4, edgecolor=SURFACE, lw=1)
        ax.annotate(T("alarma", "alarm") + f" {t:%H:%M}", (t, v), xytext=(8, -2 if key == "2019" else 4),
                    textcoords="offset points", fontsize=8.5, color=INK, ha="left", va="center")
        ax.set_ylim(lo * 1.15, max(s.max(), 0) + 0.8)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=3 if key == "2019" else 2, tz="UTC"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
        ax.set_title(titles[key], fontsize=10)
        ax.set_ylabel(T("BNB comparado con BTC", "BNB compared with BTC"))
        _pct(ax, "y", 0, True)
    fig.tight_layout()
    _save(fig, "detector")


# ------------------------------------------------------------------ history

def event_study(tab: pd.DataFrame, placebo_vals: np.ndarray):
    tab = pd.DataFrame(tab)
    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    lo, hi = np.quantile(placebo_vals, [0.05, 0.95])
    ax.axhspan(lo, hi, color=BAND, zorder=0)
    ax.text(0.99, hi, T("zona gris: lo normal en 9 de cada 10 pares de días ", "grey zone: normal on 9 of 10 two-day windows "),
            transform=ax.get_yaxis_transform(), fontsize=8, color=INK2, va="bottom", ha="right")
    is_b = tab.name.str.contains("Binance") & (pd.to_datetime(tab.date).dt.year == 2026)
    ax.scatter(tab.amount_m[~is_b], tab.scar_1[~is_b], s=26, color=BLUE, edgecolor=SURFACE, lw=1, zorder=3,
               label=T("otros hackeos a exchanges", "other exchange hacks"))
    ax.scatter(tab.amount_m[is_b], tab.scar_1[is_b], s=60, color=ORANGE, edgecolor=SURFACE, lw=1, zorder=4,
               label=T("Binance, oct 2026", "Binance, Oct 2026"))
    for _, r in tab.iterrows():
        yr = pd.Timestamp(r.date).year
        if r.amount_m >= 400 or abs(r.scar_1) > 1.9:
            below = r["name"].startswith("Mt. Gox")
            ax.annotate(f"{r['name'].replace(' CEX', '')} {yr}", (r.amount_m, r.scar_1),
                        xytext=(4, -10 if below else 3), textcoords="offset points", fontsize=8, color=INK2)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xscale("log")
    ax.set_xticks([30, 100, 300, 1000, 3000], [T("US$30 M", "$30M"), T("US$100 M", "$100M"), T("US$300 M", "$300M"),
                                               T("US$1.000 M", "$1B"), T("US$3.000 M", "$3B")])
    ax.minorticks_off()
    ax.set_xlabel(T("monto robado", "amount stolen"))
    ax.set_ylabel(T("movimiento de BTC en 2 días\n(en movimientos típicos; abajo = cae)", "BTC move over 2 days\n(in typical moves; down = fell)"))
    ax.set_title(T("Robar más no significa que Bitcoin caiga más: casi todos los hackeos quedan en la zona normal",
                   "Stealing more does not mean Bitcoin falls more: most hacks stay in the normal zone"), fontsize=10.5)
    ax.legend(fontsize=8, loc="lower center")
    _save(fig, "event_study")


def history(btc: pd.Series, hacks: pd.DataFrame, by_year: pd.DataFrame):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    a1.plot(btc.index, btc.values, color=BLUE, lw=1.0)
    a1.set_yscale("log")
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: N(v, 0)))
    a1.set_ylabel(T("Bitcoin, US$ (escala logarítmica)", "Bitcoin, USD (log scale)"))
    big = hacks[(hacks.targetType == "CEX") & (hacks.amount >= 100e6)]
    for _, h in big.iterrows():
        d = h.date.normalize()
        if d < btc.index.min():
            continue
        p = btc.loc[:d].iloc[-1]
        a1.scatter([d], [p], s=10 + 60 * np.sqrt(h.amount / 1e9), color=ORANGE, zorder=3, edgecolor=SURFACE, lw=1)
        if h.amount >= 450e6:
            a1.annotate(h["name"].replace(" CEX", ""), (d, p), xytext=(-6, 9), textcoords="offset points",
                        fontsize=8, color=INK2, ha="right")
    a1.set_title(T("Bitcoin siguió subiendo pese a cada gran hackeo (punto naranjo = hackeo a exchange de US$100 M o más)",
                   "Bitcoin kept climbing despite every big hack (orange dot = exchange hack of $100M or more)"), fontsize=10.5)
    by_year = pd.DataFrame(by_year)
    yrs = pd.to_datetime(by_year.year.astype(str) + "-07-01")
    a2.bar(yrs, by_year.stolen_bn - by_year.cex_stolen_bn, width=300, color=GRAY_SERIES, label=T("DeFi, puentes y otros", "DeFi, bridges, other"))
    a2.bar(yrs, by_year.cex_stolen_bn, width=300, bottom=by_year.stolen_bn - by_year.cex_stolen_bn, color=ORANGE,
           label=T("exchanges centralizados", "centralized exchanges"))
    a2.set_ylabel(T("robado por año,\nmiles de millones US$", "stolen per year,\n$ billion"))
    a2.text(yrs.iloc[-1], by_year.stolen_bn.iloc[-1], T("al 2 nov", "to 2 Nov"), ha="center", va="bottom", fontsize=8, color=INK2)
    a2.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    _save(fig, "history")


def annual(coin_years: list[dict]):
    cy = pd.DataFrame(coin_years)
    coins = ["BTC", "ETH", "BNB", "XRP", "SOL"]
    years = list(range(2018, 2027))
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), gridspec_kw={"height_ratios": [1.5, 1, 1]})
    a = axes[0]
    ret = cy.pivot_table(index="coin", columns="year", values="return").reindex(index=coins, columns=years) * 100
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("div", [RED, "#f0efec", BLUE])
    a.imshow(np.clip(ret.values, -100, 100), cmap=cmap, vmin=-100, vmax=100, aspect="auto")
    for i in range(len(coins)):
        for j in range(len(years)):
            v = ret.values[i, j]
            if np.isfinite(v):
                strong = abs(v) > 65
                a.text(j, i, N(v, 0, True, "%"), ha="center", va="center", fontsize=8.5, color="#ffffff" if strong else INK)
    a.set_xticks(range(len(years)), [str(y) if y < 2026 else T("2026*", "2026*") for y in years])
    a.set_yticks(range(len(coins)), coins)
    a.grid(False)
    a.spines[["left", "bottom"]].set_visible(False)
    a.set_title(T("Retorno de cada año (azul sube, rojo baja). *2026 hasta el 2 de noviembre",
                  "Return each year (blue up, red down). *2026 to 2 November"), fontsize=10.5)
    b = axes[1]
    w = 0.27
    for off, (c, col) in zip([-w, 0, w], [("BTC", BLUE), ("ETH", AQUA), ("BNB", ORANGE)]):
        s = cy[cy.coin == c].set_index("year")["usd_volume_bn"].reindex(years)
        b.bar(np.arange(len(years)) + off, s.values, width=w, color=col, label=c)
    b.set_xticks(range(len(years)), [str(y) if y < 2026 else "2026*" for y in years])
    b.set_ylabel(T("miles de millones US$", "$ billion"))
    b.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: N(v, 0)))
    b.set_title(T("Volumen en Binance spot por año (pares USDT): en 2026 va muy por debajo de 2021-2022",
                  "Volume on Binance spot per year (USDT pairs): 2026 runs far below 2021-2022"), fontsize=10.5)
    b.legend(fontsize=8, ncol=3)
    c_ = axes[2]
    for c, col in [("BTC", BLUE), ("ETH", AQUA), ("BNB", ORANGE)]:
        s = cy[cy.coin == c].set_index("year")["taker_buy_share"].reindex(years) * 100
        c_.plot(np.arange(len(years)), s.values, color=col, marker="o", ms=4, label=c)
    c_.axhline(50, color=INK2, lw=0.8)
    c_.set_xticks(range(len(years)), [str(y) if y < 2026 else "2026*" for y in years])
    _pct(c_)
    c_.set_ylabel(T("% iniciado por compradores", "% started by buyers"))
    c_.set_title(T("Compras contra ventas a mercado: casi siempre cerca de 50%, sin señal de tendencia anual",
                   "Market buys against sells: nearly always close to 50%, no annual signal"), fontsize=10.5)
    fig.tight_layout()
    _save(fig, "annual")


def context_2026(btc: pd.Series, brent: pd.Series, us10y: pd.Series, gpr: pd.Series):
    a = pd.Timestamp("2026-01-01")
    fig, axes = plt.subplots(4, 1, figsize=(9, 7.4), sharex=True)
    series = [(btc, T("Bitcoin, US$", "Bitcoin, USD"), BLUE), (brent, T("Petróleo Brent, US$ por barril", "Brent crude, USD per barrel"), INK2),
              (us10y, T("Tasa del bono a 10 años de EE.UU., %", "US 10-year yield, %"), INK2),
              (gpr.rolling(7).mean(), T("Índice de riesgo geopolítico (noticias de guerra, promedio 7 días)", "Geopolitical risk index (war news, 7-day mean)"), INK2)]
    for ax, (s, lab, col) in zip(axes, series):
        s = s.loc[a:].dropna()
        ax.plot(s.index, s.values, color=col, lw=1.1)
        ax.set_title(lab, fontsize=9.5)
    marks = [("2026-02-28", T("inicia guerra Irán", "Iran war begins")), ("2026-04-08", T("alto al fuego", "ceasefire")),
             ("2026-06-17", T("memo de paz", "peace memo")), ("2026-07-08", T("cae la tregua", "truce collapses")),
             ("2026-09-24", T("hackeo Bitget", "Bitget hack")), ("2026-10-29", T("hackeo Binance", "Binance hack"))]
    for ax in axes:
        for d, lab in marks:
            ax.axvline(pd.Timestamp(d), color=ORANGE if d >= "2026-09" else AXIS, lw=0.8, zorder=1)
    for i, (d, lab) in enumerate(marks):
        axes[0].text(pd.Timestamp(d), 1.03 + 0.11 * (i % 2), lab, transform=axes[0].get_xaxis_transform(), fontsize=7.5,
                     color=INK2, ha="center", va="bottom")
    axes[0].set_title(T("Bitcoin, US$", "Bitcoin, USD"), fontsize=9.5, pad=26)
    _thousands(axes[0])
    _month(axes[-1])
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    fig.tight_layout()
    _save(fig, "context_2026")


def after_hacks(paths: pd.DataFrame, horizons: list[dict]):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [1.35, 1]})
    p = 100 * paths
    now = [c for c in p.columns if c.startswith("Binance") and c.endswith("2026")]
    past = p.drop(columns=now)
    for c in past.columns:
        a1.plot(past.index, past[c], color=GRAY_SERIES, lw=0.5, alpha=0.5)
    q1, med, q3 = past.quantile(0.25, axis=1), past.median(axis=1), past.quantile(0.75, axis=1)
    a1.fill_between(past.index, q1, q3, color=BLUE, alpha=0.15, lw=0, label=T("la mitad central de los casos", "middle half of cases"))
    a1.plot(past.index, med, color=BLUE, lw=2, label=T("caso típico (mediana)", "typical case (median)"))
    a1.plot(p.index, p[now[0]], color=ORANGE, lw=2.2, label=T("Binance 2026 (hasta hoy)", "Binance 2026 (so far)"))
    a1.axvline(0, color=INK2, lw=0.8)
    a1.axhline(0, color=AXIS, lw=0.8)
    a1.set_ylim(-35, 45)
    a1.set_xlabel(T("días desde el hackeo", "days since the hack"))
    a1.set_ylabel(T("BTC comparado con el día antes", "BTC against the day before"))
    _pct(a1, "y", 0, True)
    a1.set_title(T("35 hackeos: BTC 30 días después", "35 hacks: BTC 30 days later"), fontsize=10)
    a1.legend(fontsize=8, loc="upper left")
    h = pd.DataFrame(horizons)
    h = h[h.group == "all"]
    x = np.arange(len(h))
    a2.bar(x - 0.2, 100 * h["median"], width=0.38, color=BLUE, label=T("después de un hackeo", "after a hack"))
    a2.bar(x + 0.2, 100 * h["random_median"], width=0.38, color=GRAY_SERIES, label=T("fecha al azar del mismo año", "random date, same year"))
    for i, (u, v) in enumerate(zip(100 * h["median"], 100 * h["random_median"])):
        a2.text(i - 0.2, u, N(u, 1, True), ha="center", va="bottom" if u >= 0 else "top", fontsize=8, color=INK2)
        a2.text(i + 0.2, v, N(v, 1, True), ha="center", va="bottom" if v >= 0 else "top", fontsize=8, color=INK2)
    a2.axhline(0, color=AXIS, lw=0.8)
    a2.set_xticks(x, T("1 semana|1 mes|3 meses|1 año", "1 week|1 month|3 months|1 year").split("|"))
    _pct(a2, "y", 0, True)
    a2.set_title(T("Retorno típico de BTC por plazo", "BTC's typical return by horizon"), fontsize=10)
    a2.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    _save(fig, "after_hacks")


def recovery(coins: list[dict]):
    d = pd.DataFrame(coins)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(8.5, 3.3))
    low, last = 100 * d["low_change"].values, 100 * d["change_to_last"].values
    ax.hlines(y, low, last, color=GRID, lw=3)
    ax.scatter(low, y, color=RED, s=55, zorder=3, label=T("peor momento", "worst moment"), edgecolor=SURFACE, lw=1)
    ax.scatter(last, y, color=BLUE, s=55, zorder=3, label=T(f"último cierre ({d['last_day'].iloc[0][8:]} nov)", f"last close (Nov {d['last_day'].iloc[0][8:]})"),
               edgecolor=SURFACE, lw=1)
    for i in range(len(d)):
        ax.text(low[i], i - 0.27, N(low[i], 1, True, "%"), ha="center", fontsize=8, color=INK2)
        ax.text(last[i], i - 0.27, N(last[i], 1, True, "%"), ha="center", fontsize=8, color=INK2)
    ax.axvline(0, color=INK2, lw=0.9)
    ax.text(0, -0.62, T(" 0% = precio cuando partió el hackeo", " 0% = price when the hack began"), fontsize=8, color=INK2, va="center")
    ax.set_yticks(y, d.coin)
    ax.set_ylim(len(d) - 0.4, -0.7)
    _pct(ax, "x", 0, True)
    ax.set_title(T("ETH y XRP ya recuperaron el precio previo; BTC está cerca; BNB y SOL siguen abajo",
                   "ETH and XRP are back above the earlier price; BTC is close; BNB and SOL remain below"), fontsize=10.5)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.08), ncol=2)
    _save(fig, "recovery")


# ------------------------------------------------------------------ models

def skill(y1: list[dict], vol: list[dict], gru: dict):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.7))
    t = {d["model"]: d for d in y1 if d["coin"] == "all"}
    names = [("ridge", "Ridge"), ("lgb", "LightGBM"), ("mlp", T("Red MLP", "MLP net"))]
    vals = [50.0] + [100 * t[m]["hit_rate"] for m, _ in names] + [100 * gru["y1"]["hit_rate"]]
    labs = [T("moneda\nal aire", "coin\nflip")] + [n for _, n in names] + [T("Red GRU", "GRU net")]
    a1.bar(range(len(vals)), vals, width=0.6, color=[GRAY_SERIES] + [BLUE] * 4)
    for i, v in enumerate(vals):
        a1.text(i, v + 0.1, N(v, 1, False, "%"), ha="center", va="bottom", fontsize=8.5, color=INK2)
    a1.set_ylim(0, 65)
    a1.axhline(50, color=INK2, lw=0.8)
    a1.set_xticks(range(len(vals)), labs, fontsize=8.5)
    _pct(a1)
    a1.set_ylabel(T("días en que acertó si sube o baja", "days it got up or down right"))
    a1.set_title(T("Precio de mañana: casi una moneda al aire", "Tomorrow's price: nearly a coin flip"), fontsize=10)
    v = {d["model"]: d for d in vol if d["coin"] == "all"}
    vm = [("har", T("Solo volatilidad\npasada (HAR)", "Past volatility\nonly (HAR)")), ("lgb", T("LightGBM\n65 variables", "LightGBM\n65 features")),
          ("ridge", "Ridge"), ("mlp", T("Red MLP", "MLP net")), (None, T("Red GRU", "GRU net"))]
    vv = [100 * (v[m]["r2"] if m else gru["vol"]["r2"]) for m, _ in vm]
    a2.bar(range(len(vm)), vv, width=0.6, color=[AQUA] + [BLUE] * 4)
    for i, x in enumerate(vv):
        a2.text(i, x, N(x, 1, False, "%"), ha="center", va="bottom", fontsize=8.5, color=INK2)
    a2.set_xticks(range(len(vm)), [n for _, n in vm], fontsize=8)
    a2.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
    _pct(a2)
    a2.set_ylabel(T("variación anticipada", "variation anticipated"))
    a2.set_title(T("Turbulencia próxima semana: 65 variables no superan al modelo simple", "Next week's turbulence: 65 features don't beat the simple model"), fontsize=10)
    fig.tight_layout()
    _save(fig, "skill")


def ablation(ab: list[dict]):
    ab = pd.DataFrame(ab)
    names = {"derivatives": T("financiamiento de futuros", "futures funding"), "macro_markets": T("bolsa, tasas, dólar, petróleo", "stocks, rates, dollar, oil"),
             "war_policy_news": T("noticias de guerra y política", "war and policy news"), "sentiment_attention": T("Fear & Greed, Wikipedia", "Fear & Greed, Wikipedia"),
             "onchain_supply": T("hash rate, stablecoins, reservas", "hash rate, stablecoins, reserves"), "hacks": T("registro de hackeos", "hack register")}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.5), sharey=True)
    for ax, (tgt, title) in zip(axes, [("y1", T("Para el precio de mañana", "For tomorrow's price")),
                                       ("rv7_fwd", T("Para la turbulencia de la próxima semana", "For next week's turbulence"))]):
        d = ab[(ab.target == tgt) & (ab.group != "all")].set_index("group").loc[list(names)]
        v = -100 * d["add_to_price_mse_change"].values
        y = np.arange(len(d))
        ax.barh(y, v, color=[BLUE if x > 0 else GRAY_SERIES for x in v], height=0.6)
        for i, x in enumerate(v):
            ax.text(x, i, f" {N(x, 1, True, '%')} ", va="center", ha="left" if x >= 0 else "right", fontsize=8, color=INK2)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_yticks(y, [names[g] for g in d.index], fontsize=8.5)
        ax.set_title(title, fontsize=9.5)
        _pct(ax, "x", 1)
        lo, hi = min(v.min(), 0), max(v.max(), 0)
        ax.set_xlim(lo - 0.35 * (hi - lo), hi + 0.35 * (hi - lo))
        ax.invert_yaxis()
    fig.suptitle(T("Agregar noticias y guerra al precio y volumen casi siempre empeora el pronóstico (a la izquierda = peor)",
                   "Adding news and war data to price and volume nearly always worsens the forecast (left = worse)"),
                 x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    _save(fig, "ablation")


def nowcast(hist: dict[str, pd.Series], fc: list[dict]):
    fc = pd.DataFrame(fc)
    fc["target_date"] = pd.to_datetime(fc["target_date"])
    coins = list(hist)
    fig, axes = plt.subplots(1, len(coins), figsize=(11.5, 2.9))
    for ax, c in zip(axes, coins):
        h = hist[c].iloc[-45:]
        ax.plot(h.index, h.values, color=BLUE, lw=1.1)
        f = fc[fc.coin == c].sort_values("horizon")
        last_t, last_p = h.index[-1], h.values[-1]
        t = [last_t] + list(f["target_date"])
        ax.fill_between(t, [last_p] + list(f["p05"]), [last_p] + list(f["p95"]), color=BLUE, alpha=0.15, lw=0)
        ax.plot(t, [last_p] + list(f["p50"]), color=BLUE, lw=1.1, ls=(0, (1, 1.5)))
        ax.set_title(c, fontsize=9.5)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=20))
        _day_month(ax)
        ax.tick_params(axis="x", labelsize=7.5)
    fig.suptitle(T("Pronóstico congelado: los próximos 7 días con 90% de probabilidad en la zona azul",
                   "Frozen forecast: the next 7 days with a 90% chance inside the blue zone"), x=0.01, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    _save(fig, "nowcast")


def scenarios(hist: dict[str, pd.Series], fan: list[dict], pre: dict[str, float]):
    fan = pd.DataFrame(fan)
    coins = ["BTC", "ETH", "BNB", "XRP", "SOL"]
    fig = plt.figure(figsize=(11, 6.6))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.5, 1])
    big = fig.add_subplot(gs[0, :])
    axes = [big] + [fig.add_subplot(gs[1, i]) for i in range(4)]
    for ax, c in zip(axes, coins):
        h = hist[c].iloc[-(240 if c == "BTC" else 120):]
        f = fan[fan.coin == c].sort_values("horizon")
        t0, p0 = h.index[-1], h.values[-1]
        t = [t0] + [t0 + pd.Timedelta(days=int(x)) for x in f["horizon"]]
        ax.plot(h.index, h.values, color=BLUE, lw=1.1, label=T("precio real", "actual price"))
        ax.fill_between(t, [p0] + list(f["p05"]), [p0] + list(f["p95"]), color=BLUE, alpha=0.13, lw=0,
                        label=T("9 de cada 10 caminos", "9 of 10 paths"))
        ax.fill_between(t, [p0] + list(f["p25"]), [p0] + list(f["p75"]), color=BLUE, alpha=0.25, lw=0,
                        label=T("5 de cada 10 caminos", "5 of 10 paths"))
        ax.axhline(pre[c], color=ORANGE, lw=1, label=T("precio cuando partió el hackeo", "price when the hack began"))
        ax.axvline(t0, color=AXIS, lw=0.8)
        ax.set_title(c, fontsize=9.5)
        months = 3 if c == "BTC" else 6
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=months))
        months_names = MONTHS_ES if LANG == "es" else MONTHS_EN
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: (lambda d: f"{months_names[d.month - 1]} {d.year % 100}")(mdates.num2date(v))))
        ax.tick_params(labelsize=8)
        if c != "XRP":
            _thousands(ax)
        if c == "BTC":
            for _, r in f.iterrows():
                if r.horizon in (30, 365):
                    d = t0 + pd.Timedelta(days=int(r.horizon))
                    ax.annotate(f"{N(r.p05, 0)} - {N(r.p95, 0)}", (d, r.p95), xytext=(0, 4), textcoords="offset points",
                                ha="center", fontsize=8, color=INK2)
            ax.legend(fontsize=8, loc="upper left", ncol=4)
    fig.suptitle(T("Hacia dónde podría ir el precio en un año: no es una predicción, es el rango de lo posible",
                   "Where the price could go in a year: not a prediction, the range of what is possible"),
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    _save(fig, "scenarios")


def render_all(r: dict) -> None:
    """Every static figure in both languages, from the data on disk and the results file."""
    global LANG
    from . import aftermath, candles, datasets, detector, eventstudy, intraday
    w = intraday.closes()
    nq = intraday.macro_minutes()["NQ=F"]
    gaps = intraday.venue_gaps(w)
    a, b = intraday.T0, pd.Timestamp("2026-10-30 06:00", tz="UTC")
    mins = {c: intraday.taker_minutes(c, a, b) for c in ["BTC", "BNB"]}
    base = {}
    for c in ["BTC", "BNB"]:
        nights = [intraday.taker_minutes(c, a - pd.Timedelta(days=k), b - pd.Timedelta(days=k))["net"]
                  .cumsum().reset_index(drop=True) / 1e6 for k in range(1, 8)]
        base[c] = pd.concat(nights, axis=1).mean(axis=1)
    btc_r = eventstudy.btc_daily_returns()
    _, allvals = eventstudy.placebo(btc_r, 5, pd.DatetimeIndex([]), draws=10)
    btc_long = eventstudy.btc_daily_close()
    hacks = datasets.hacks()
    mac = datasets.macro_daily()
    btc_close = datasets.daily_prices().query("coin == 'BTC'").set_index("time")["close"]
    btc_close.index = btc_close.index.tz_localize(None)
    det = detector.run()
    latest = {c: aftermath.daily_latest(c)["close"] for c in aftermath.COINS}
    am = aftermath.run()
    hist_now = {c: s.loc[:r["nowcast"]["asof"]] for c, s in latest.items()}
    pre = {d["coin"]: d["price_at_hack"] for d in r["aftermath"]["coins"]}
    abn = pd.DataFrame(r["abnormal_vs_btc"])
    dec = pd.DataFrame(r["decomposition"])
    fsize = pd.DataFrame(r["flow_size"])
    for lang in ("es", "en"):
        LANG = lang
        night(w, nq)
        decomposition(dec)
        cross_section(abn)
        flow(mins, base, fsize)
        hack_days(pd.DataFrame(r["aftermath"]["days"]))
        venues(gaps)
        event_study(r["event_study"]["BTC"]["table"], allvals)
        history(btc_long, hacks, r["hacks_by_year"])
        annual(r["coin_years"])
        reserve_flows(r["reserve_flows"])
        context_2026(btc_close, mac["BZ=F"], mac["^TNX"], mac["GPRD"])
        detector_traces(det)
        after_hacks(am["paths"], r["aftermath"]["horizons"])
        recovery(r["aftermath"]["coins"])
        skill(r["forecast"]["y1_scores"], r["forecast"]["vol_scores"], r["gru"])
        ablation(r["forecast"]["ablation"])
        nowcast(hist_now, r["nowcast"]["forecast"])
        scenarios(latest, r["scenarios"]["fan"], pre)
        stocks(pd.DataFrame(r["stocks"]))
    candles.build()

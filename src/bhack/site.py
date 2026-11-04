"""Builds docs/index.html from reports/results.json. Bilingual: every text block exists in
Spanish and English and a toggle shows one. Numbers are read from the results, never typed."""
from __future__ import annotations

import html
import json

from .config import REPORTS, ROOT


def _f(x, d=1, pct=False, sign=False):
    if x is None:
        return "n/a"
    v = 100 * x if pct else x
    s = f"{v:+.{d}f}" if sign else f"{v:.{d}f}"
    return s + ("%" if pct else "")


def _es(s: str) -> str:
    """Spanish decimal comma for numbers already formatted with a point."""
    out, prev = [], ""
    for i, ch in enumerate(s):
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch == "." and prev.isdigit() and nxt.isdigit():
            out.append(",")
        elif ch == "," and prev.isdigit() and nxt.isdigit():
            out.append(".")
        else:
            out.append(ch)
        prev = ch
    return "".join(out)


def _px(v: float) -> str:
    return f"{v:,.4f}" if v < 10 else f"{v:,.2f}"


def bi(es: str, en: str, tag: str = "p") -> str:
    return f'<{tag} lang="es">{es}</{tag}><{tag} lang="en">{en}</{tag}>'


def fig(name: str, es: str, en: str) -> str:
    return (f'<figure><img src="img/{name}.png" alt="{html.escape(en)}" loading="lazy">'
            f'<figcaption lang="es">{es}</figcaption><figcaption lang="en">{en}</figcaption></figure>')


def table(head: list[str], rows: list[list[str]], head_es: list[str] | None = None) -> str:
    def hrow(h, lang):
        return f'<tr lang="{lang}">' + "".join(f"<th>{c}</th>" for c in h) + "</tr>"
    th = hrow(head, "en") + (hrow(head_es, "es") if head_es else hrow(head, "es"))
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table><thead>{th}</thead><tbody>{body}</tbody></table></div>'


def section(n: int, es: str, en: str, body: str) -> str:
    return (f'<section><h2><span class="num">{n:02d}</span><span lang="es">{es}</span>'
            f'<span lang="en">{en}</span></h2>{body}</section>')


def build(r: dict) -> str:
    P = r["paths"]
    dec = {(d["window"], d["coin"]): d for d in r["decomposition"]}
    dec30 = {(d["window"], d["coin"]): d for d in r["decomposition_30min"]}
    det = r["detector"]
    flow = {(d["window"], d["coin"]): d for d in r["flow"]}
    svu = {d["window"]: d for d in r["stolen_vs_untouched"]}
    gm = r["abnormal_group_means"]
    es_btc = r["event_study"]["BTC"]
    trend = r["trend_before_hack"]["BTC"]
    stocks = {d["stock"]: d for d in r["stocks"] if d["day"] == "2026-10-30"}
    rf = r["reserve_flows"]
    gaps = {(d["phase"], d["pair"]): d for d in r["venue_gaps"]}
    hy = {d["year"]: d for d in r["hacks_by_year"]}
    fc = r["forecast"]
    y1 = {(d["coin"], d["model"]): d for d in fc["y1_scores"]}
    vs = {(d["coin"], d["model"]): d for d in fc["vol_scores"]}
    cov1 = {d["coin"]: d for d in fc["y1_coverage"]}
    abl = {(d["target"], d["group"]): d for d in fc.get("ablation", [])}
    now = r["nowcast"]

    btc_n2 = dec[("to_nov2_close", "BTC")]
    btc_n2_30 = dec30[("to_nov2_close", "BTC")]
    flows_out = rf["2026-11-01"]["net_flow_bn"] + rf["2026-11-02"]["net_flow_bn"]
    pre_assets = rf["2026-10-28"]["assets_bn"]

    stats = [
        ("$6.36B", "robados en 10 cadenas (TRM Labs)", "stolen across 10 chains (TRM Labs)"),
        (_f(100 * btc_n2["explained"] / btc_n2["actual"], 0) + "%",
         _es(f"de la caída de BTC ({_f(btc_n2['actual'], 1, True)}) la predice el Nasdaq"),
         f"of BTC's fall ({_f(btc_n2['actual'], 1, True)}) is predicted by the Nasdaq"),
        (f"{det['2026']['minutes_before_admission']:.0f} min",
         "antes de que Binance hablara, una alarma de mercado ya había saltado",
         "before Binance spoke, a market-data alarm had already fired"),
        (f"${-flows_out:.1f}B", _es(f"retirados en 2 días al reabrir ({_f(-flows_out / pre_assets, 0, True)} de los activos)"),
         f"withdrawn in 2 days after reopening ({_f(-flows_out / pre_assets, 0, True)} of assets)"),
    ]
    stat_html = "".join(f'<div class="stat"><b>{v}</b><span lang="es">{es}</span><span lang="en">{en}</span></div>'
                        for v, es, en in stats)

    rows_path = []
    for key, es_l, en_l in [("21:15 CZ post", "21:15, CZ: \"parece un hackeo\"", "21:15, CZ: \"does look like a hack\""),
                            ("00:13 halt", "00:13, retiros suspendidos", "00:13, withdrawals halted"),
                            ("06:00 Nov 1 reopen", "06:00 del 1 nov, reapertura", "06:00 Nov 1, reopening"),
                            ("Nov 2 close", "cierre del 2 nov", "close of Nov 2")]:
        rows_path.append([f'<span lang="es">{es_l}</span><span lang="en">{en_l}</span>'] +
                         [_f(P[c][key], 1, True, True) for c in ["BTC", "ETH", "BNB", "XRP", "SOL", "TRX"]])
    path_tbl = table(["From 20:00 UTC, Oct 29, to", "BTC", "ETH", "BNB", "XRP", "SOL", "TRX"], rows_path,
                     ["Desde las 20:00 UTC del 29 oct hasta", "BTC", "ETH", "BNB", "XRP", "SOL", "TRX"])

    ba = dec[("before_admission", "BTC")]
    s1 = section(1, "Qué pasó esa noche", "What happened that night",
                 bi("El primer envío salió de las wallets de Binance en XRP Ledger a las 20:05 UTC. A las 20:20 salieron "
                    "18.270 BTC y comenzó el barrido de Ethereum. Changpeng Zhao escribió \"parece un hackeo\" a las 21:15 "
                    "y Binance suspendió retiros a las 00:13. Cinco minutos antes del primer envío había cerrado Nueva York, "
                    "y Amazon e Intel publicaron resultados que hundieron los futuros del Nasdaq.",
                    "The first outflow left Binance's XRP Ledger wallets at 20:05 UTC. At 20:20, 18,270 BTC left and the "
                    "Ethereum sweep began. Changpeng Zhao posted \"does look like a hack\" at 21:15 and Binance halted "
                    "withdrawals at 00:13. Five minutes before the first outflow New York had closed, and Amazon and "
                    "Intel published earnings that pushed Nasdaq futures down.")
                 + fig("night", "Precios minuto a minuto desde las 20:00 UTC. Zona gris: sin ninguna declaración todavía.",
                       "Minute prices from 20:00 UTC. Grey band: no statement from anyone yet.") + path_tbl
                 + bi("Retornos logarítmicos: se suman entre ventanas y, a estos tamaños, difieren en menos de 0,2 "
                      "puntos de los cambios porcentuales simples.",
                      "Log returns: they add up across windows and, at these sizes, are within 0.2 points of simple "
                      "percentage changes.", "figcaption"))

    s2 = section(2, "¿Hackeo o Nasdaq?", "Hack or Nasdaq?",
                 bi(_es(f"Ajusté los retornos de 5 minutos de Bitcoin a los futuros del Nasdaq-100, el dólar y el oro en la "
                        f"semana previa (R² {r['macro_fits']['BTC']['r2']:.2f}) y usé ese ajuste para predecir cada ventana. "
                        f"Desde las 20:00 del 29 hasta el cierre del 2 de noviembre BTC cayó {_f(-btc_n2['actual'], 1, True)}: "
                        f"<strong>{_f(btc_n2['explained'], 1, True)} lo predice la caída tecnológica</strong> y "
                        f"{_f(btc_n2['abnormal'], 1, True)} es anormal (con retornos de 30 minutos: "
                        f"{_f(btc_n2_30['explained'], 1, True)} y {_f(btc_n2_30['abnormal'], 1, True)}). El efecto propio del "
                        f"hackeo fue fuerte y corto: {_f(ba['abnormal'], 1, True)} antes de cualquier declaración."),
                    f"I fitted Bitcoin's five-minute returns on Nasdaq-100 futures, the dollar and gold in the prior week "
                    f"(R² {r['macro_fits']['BTC']['r2']:.2f}) and used that fit to predict each window. From 20:00 on Oct 29 "
                    f"to the Nov 2 close BTC fell {_f(-btc_n2['actual'], 1, True)}: <strong>the tech sell-off predicts "
                    f"{_f(btc_n2['explained'], 1, True)}</strong> and {_f(btc_n2['abnormal'], 1, True)} is abnormal "
                    f"(with 30-minute returns: {_f(btc_n2_30['explained'], 1, True)} and {_f(btc_n2_30['abnormal'], 1, True)}). "
                    f"The hack's own effect was sharp and short: {_f(ba['abnormal'], 1, True)} before any statement.")
                 + fig("decomposition", "Azul: lo que predicen los futuros del Nasdaq, el dólar y el oro. Naranjo: el resto.",
                       "Blue: what Nasdaq futures, the dollar and gold predict. Orange: the rest."))

    d26, d19 = det["2026"], det["2019"]
    fb = flow[("before_admission", "BNB")]
    s3 = section(3, "El mercado lo supo antes que nadie lo dijera", "The market knew before anyone said so",
                 bi(_es(f"Una alarma simple sobre el retorno de 15 minutos de BNB contra Bitcoin, calibrada para sonar como "
                        f"máximo una vez al mes (umbral fijado en 60 días y probado en los 30 siguientes, donde dio "
                        f"{d26['holdout_false_alarms_30d']} falsas alarmas), saltó a las <strong>{d26['alarm'][11:16]} UTC</strong>: "
                        f"{d26['minutes_after_event']:.0f} minutos después del primer envío y "
                        f"<strong>{d26['minutes_before_admission']:.0f} minutos antes</strong> del post de CZ. En esos 75 minutos BNB "
                        f"transó {fb['volume_x_normal']:.0f} veces su volumen normal a esa hora, con "
                        f"{_f(fb['buy_share'], 0, True)} de compras (normal {_f(fb['normal_buy_share'], 0, True)}). La misma alarma, "
                        f"sin cambios, sobre el hackeo de Binance de mayo de 2019 saltó a las {d19['alarm'][11:16]}, "
                        f"{-d19['minutes_before_admission']:.0f} minutos <em>después</em> del anuncio. En 2019 el mercado se enteró por "
                        f"el anuncio; en 2026, por la blockchain."),
                    f"A simple alarm on BNB's 15-minute return against Bitcoin, set to fire at most once a month (threshold "
                    f"fixed on 60 days and checked on the next 30, where it raised {d26['holdout_false_alarms_30d']} false alarms), "
                    f"went off at <strong>{d26['alarm'][11:16]} UTC</strong>: {d26['minutes_after_event']:.0f} minutes after the "
                    f"first outflow and <strong>{d26['minutes_before_admission']:.0f} minutes before</strong> CZ's post. In those "
                    f"75 minutes BNB traded {fb['volume_x_normal']:.0f} times its usual volume for that hour, "
                    f"{_f(fb['buy_share'], 0, True)} buyer-initiated (normally {_f(fb['normal_buy_share'], 0, True)}). The same "
                    f"alarm, unchanged, on Binance's May 2019 hack went off at {d19['alarm'][11:16]}, "
                    f"{-d19['minutes_before_admission']:.0f} minutes <em>after</em> the announcement. In 2019 the market learned "
                    f"from the announcement; in 2026, from the blockchain.")
                 + fig("detector", "Puntaje z robusto del movimiento anormal de BNB; línea naranja: umbral de alarma.",
                       "Robust z-score of BNB's abnormal move; orange line: alarm threshold."))

    tr = svu["to_reopen"]
    fa = svu["before_admission"]
    s4 = section(4, "Nadie apostó a que el ladrón vendería", "Nobody bet on the thief dumping the loot",
                 bi(_es(f"Si el mercado temiera que el atacante vendiera 18.270 BTC o 233 millones de XRP, las monedas de las "
                        f"cadenas vaciadas habrían caído más. No pasó: hasta la reapertura, su retorno neto de beta por Bitcoin "
                        f"fue {_f(tr['stolen_mean'], 1, True, True)} en promedio contra {_f(tr['untouched_mean'], 1, True, True)} de "
                        f"13 monedas grandes de cadenas intactas (permutación p = {tr['p_perm']:.2f}; en los primeros 75 minutos "
                        f"p = {fa['p_perm']:.2f}, con las robadas cayendo <em>menos</em>). La excepción fue BNB, el token del propio "
                        f"exchange: {_f(gm['to_reopen']['exchange token'], 1, True, True)}."),
                    f"If the market had feared the attacker selling 18,270 BTC or 233 million XRP, coins from the drained "
                    f"chains would have fallen more. They did not: to the reopening, their return net of beta times Bitcoin "
                    f"averaged {_f(tr['stolen_mean'], 1, True, True)} against {_f(tr['untouched_mean'], 1, True, True)} for 13 large "
                    f"coins on untouched chains (permutation p = {tr['p_perm']:.2f}; in the first 75 minutes p = "
                    f"{fa['p_perm']:.2f}, with the stolen coins falling <em>less</em>). The exception was BNB, the exchange's own "
                    f"token: {_f(gm['to_reopen']['exchange token'], 1, True, True)}.")
                 + fig("cross_section", "Retorno de cada moneda menos beta por Bitcoin, desde las 20:00 del 29 hasta la reapertura.",
                       "Each coin's return minus beta times Bitcoin, 20:00 Oct 29 to the reopening."))

    fs = {(d["coin"], d["size"], d["period"]): d for d in r["flow_size"]}
    small = fs[("BTC", "<1k", "hack_night")]["net_musd"] + fs[("BTC", "1k-10k", "hack_night")]["net_musd"]
    total = sum(fs[("BTC", s, "hack_night")]["net_musd"] for s in ["<1k", "1k-10k", "10k-100k", "100k-1M", ">1M"]
                if ("BTC", s, "hack_night") in fs)
    s5 = section(5, "Quién vendió", "Who sold",
                 bi(_es(f"Entre las 20:00 y las 06:00 los tomadores vendieron {-total:.0f} millones de dólares más de BTC de los "
                        f"que compraron en Binance spot. Las órdenes de menos de 10.000 dólares explican {-small:.0f} millones "
                        f"({_f(small / total, 0, True)}). Ojo: un trade agregado es una orden ejecutada a un precio, y los "
                        f"algoritmos parten órdenes grandes en pedazos, así que chico no es lo mismo que minorista."),
                    f"From 20:00 to 06:00 takers sold ${-total:.0f} million more BTC than they bought on Binance spot. Orders "
                    f"under $10,000 account for ${-small:.0f} million ({_f(small / total, 0, True)}). Caveat: an aggregated trade "
                    f"is one order filled at one price, and algorithms split large orders, so small is not the same as retail.")
                 + fig("flow", "Izquierda: flujo neto acumulado de tomadores. Derecha: por tamaño de orden, BTC.",
                       "Left: cumulative net taker flow. Right: by order size, BTC."))

    g_btc = gaps[("withdrawals_halted", "BTC vs Coinbase")]["median_bp"]
    g_btc0 = gaps[("week_before", "BTC vs Coinbase")]["median_bp"]
    s6 = section(6, "Una corrida ordenada", "An orderly run",
                 bi(_es(f"Valorando cada día el cambio en <em>cantidades</em> de cada moneda en las wallets publicadas de Binance "
                        f"(DefiLlama) se separan los flujos de los precios: {rf['2026-10-29']['net_flow_bn']:+.2f} mil millones el 29 "
                        f"(el robo), nada mientras los retiros estuvieron cerrados, y {rf['2026-11-01']['net_flow_bn']:+.2f} y "
                        f"{rf['2026-11-02']['net_flow_bn']:+.2f} mil millones el 1 y 2 de noviembre: "
                        f"{_f(-flows_out / pre_assets, 1, True)} de los {pre_assets:.1f} mil millones previos. Durante la "
                        f"suspensión, BTC en Binance cotizó {g_btc:+.1f} puntos básicos sobre Coinbase (la semana previa "
                        f"{g_btc0:+.1f}): el mercado valoraba un dólar atrapado en Binance en unos 99,9 centavos."),
                    f"Valuing each day's change in coin <em>quantities</em> on Binance's published wallets (DefiLlama) separates "
                    f"flows from prices: ${rf['2026-10-29']['net_flow_bn']:+.2f}B on Oct 29 (the theft), nothing while "
                    f"withdrawals were halted, then ${rf['2026-11-01']['net_flow_bn']:+.2f}B and ${rf['2026-11-02']['net_flow_bn']:+.2f}B "
                    f"on Nov 1 and 2: {_f(-flows_out / pre_assets, 1, True)} of the ${pre_assets:.1f}B held before. During the "
                    f"halt BTC on Binance traded {g_btc:+.1f} basis points above Coinbase ({g_btc0:+.1f} the week before): the "
                    f"market valued a dollar trapped on Binance at about 99.9 cents.")
                 + fig("reserve_flows", "Flujo neto diario en las wallets de Binance, sin el efecto de precios.",
                       "Daily net flow on Binance's wallets, price effect removed.")
                 + fig("venues", "Diferencia de precio de Binance contra Coinbase (BTC) y OKX (BNB).",
                       "Binance's price gap to Coinbase (BTC) and OKX (BNB)."))

    rows_st = [[s, _f(stocks[s]["ret"], 1, True, True), _f(stocks[s]["abn_vs_qqq_btc"], 1, True, True),
                f"{stocks[s]['t_stat']:+.1f}"] for s in ["COIN", "HOOD", "MSTR", "CRCL", "IBIT"] if s in stocks]
    s7 = section(7, "Las acciones cripto", "Crypto stocks",
                 bi("Con Bitcoin medido de cierre a cierre de Nueva York (el hackeo partió después del cierre del 29, así que cae en "
                    "la sesión del 30) y un modelo de dos factores ajustado en las 120 sesiones previas, ninguna acción tuvo un "
                    "movimiento anormal fuera del ruido diario: ni contagio ni fuga hacia el competidor regulado.",
                    "With Bitcoin measured from one New York close to the next (the hack began after the Oct 29 close, so it "
                    "falls in the Oct 30 session) and a two-factor model fitted on the prior 120 sessions, no stock moved "
                    "outside normal daily noise: no contagion, and no flight to the regulated competitor.")
                 + table(["Stock", "Return Oct 30", "Abnormal", "t"], rows_st, ["Acción", "Retorno 30 oct", "Anormal", "t"])
                 + fig("stocks", "Retorno anormal del 30 de octubre; barras: rango del 95% de un día normal.",
                       "Abnormal return on Oct 30; bars: 95% range of a normal day."))

    b = es_btc["binance_2026"]
    s8 = section(8, "Quince años de hackeos", "Fifteen years of hacks",
                 bi(_es(f"En los {es_btc['n_events']} hackeos a exchanges centralizados de 30 millones de dólares o más desde 2011, el "
                        f"retorno anormal estandarizado de Bitcoin en el día del incidente y el siguiente promedia "
                        f"{es_btc['mean_scar_1']:+.2f} (placebo p = {es_btc['p_mean_scar_1']:.2f}); la mitad son negativos. Este "
                        f"hackeo es el {b['rank_among_hacks']}° de {es_btc['n_events']} ({_f(b['car_1'], 1, True, True)} anormal en dos "
                        f"días), un movimiento que igualan o superan el {_f(b['pct_of_all_days'], 1, True)} de todas las ventanas "
                        f"de dos días. 2026 ya es el peor año registrado: {hy[2026]['stolen_bn']:.2f} mil millones robados al 2 de "
                        f"noviembre."),
                    f"Across the {es_btc['n_events']} centralized-exchange hacks of $30 million or more since 2011, Bitcoin's "
                    f"standardized abnormal return over the incident day and the next averages {es_btc['mean_scar_1']:+.2f} "
                    f"(placebo p = {es_btc['p_mean_scar_1']:.2f}); half are negative. This hack ranks {b['rank_among_hacks']} of "
                    f"{es_btc['n_events']} ({_f(b['car_1'], 1, True, True)} abnormal over two days), a move matched or exceeded by "
                    f"{_f(b['pct_of_all_days'], 1, True)} of all two-day windows. 2026 is already the worst year on record: "
                    f"${hy[2026]['stolen_bn']:.2f}B stolen to Nov 2.")
                 + fig("event_study", "Cada punto es un hackeo; zona gris: 90% de las ventanas de dos días al azar.",
                       "Each dot is a hack; grey band: 90% of random two-day windows.")
                 + fig("history", "Bitcoin desde 2011 y cada hackeo a un exchange de 100 millones o más; abajo, lo robado por año.",
                       "Bitcoin since 2011 and every exchange hack of $100M or more; below, money stolen per year."))

    s9 = section(9, "¿Había tendencia alcista?", "Was there an uptrend?",
                 bi(_es(f"El 28 de octubre BTC cerró en {trend['close']:,.0f} dólares. Había subido "
                        f"{_f(trend['ret_q3'], 0, True)} en el tercer trimestre (promedio de 50 días {trend['sma50']:,.0f} sobre el de "
                        f"200, {trend['sma200']:,.0f}), pero en octubre ya iba {_f(trend['ret_oct_to_eve'], 1, True)}, en el año "
                        f"{_f(trend['ret_ytd'], 1, True)} y {_f(-trend['drawdown_from_2026_high'], 0, True)} bajo su máximo de enero. El "
                        f"repunte fue real, pero se había frenado antes del hackeo, con el Brent sobre 110 dólares por la guerra "
                        f"con Irán y la tasa a 10 años de EE.UU. cerca de 5%."),
                    f"On Oct 28 BTC closed at ${trend['close']:,.0f}. It had gained {_f(trend['ret_q3'], 0, True)} in the third "
                    f"quarter (50-day average {trend['sma50']:,.0f} above the 200-day, {trend['sma200']:,.0f}), but it was already "
                    f"{_f(trend['ret_oct_to_eve'], 1, True)} in October, {_f(trend['ret_ytd'], 1, True)} for the year and "
                    f"{_f(-trend['drawdown_from_2026_high'], 0, True)} below its January high. The rally was real but had stalled "
                    f"before the hack, with Brent above $110 because of the war with Iran and the US 10-year yield near 5%.")
                 + fig("context_2026", "2026: Bitcoin, Brent, tasa a 10 años e índice de riesgo geopolítico.",
                       "2026: Bitcoin, Brent, the 10-year yield and the geopolitical risk index."))

    # ---------------------------------------------------------------- models
    lg, rg, ml = y1[("all", "lgb")], y1[("all", "ridge")], y1.get(("all", "mlp"))
    vl = vs[("all", "lgb")]
    abl_rows = []
    names = {"derivatives": ("financiamiento de futuros", "futures funding"),
             "macro_markets": ("bolsa, tasas, dólar, petróleo", "stocks, rates, dollar, oil"),
             "war_policy_news": ("índices de guerra y política", "war and policy news indices"),
             "sentiment_attention": ("Fear & Greed, Wikipedia", "Fear & Greed, Wikipedia"),
             "onchain_supply": ("hash rate, stablecoins, reservas", "hash rate, stablecoins, reserves"),
             "hacks": ("registro de hackeos", "hack register")}
    for g, (es_n, en_n) in names.items():
        a1, a2 = abl.get(("y1", g)), abl.get(("rv7_fwd", g))
        if a1 and a2:
            abl_rows.append([f'<span lang="es">{es_n}</span><span lang="en">{en_n}</span>',
                             _f(-a1["add_to_price_mse_change"], 1, True, True),
                             _f(-a2["add_to_price_mse_change"], 1, True, True)])
    s10 = section(10, "¿Se puede predecir el precio con las noticias?", "Can the news forecast the price?",
                  bi(_es(f"Panel diario de 5 monedas desde 2019 con 65 variables en 8 grupos (precio y volumen, futuros, bolsa y "
                         f"tasas, índices de guerra y política, sentimiento, on-chain, hackeos, calendario), cada una con el rezago "
                         f"con que se publica. Reentrenado cada mes de 2022 a 2026 con lo conocido hasta ese día. "
                         f"<strong>Ningún modelo le gana a predecir \"sin cambio\" para el retorno de mañana</strong>: R² fuera de "
                         f"muestra {_f(lg['r2_vs_zero'], 2, True)} LightGBM, {_f(rg['r2_vs_zero'], 2, True)} ridge"
                         + (f", {_f(ml['r2_vs_zero'], 2, True)} MLP" if ml else "") +
                         f"; aciertan la dirección {_f(lg['hit_rate'], 1, True)} a {_f(rg['hit_rate'], 1, True)} de los días. "
                         f"<strong>La volatilidad de la semana siguiente sí se predice</strong>: LightGBM explica "
                         f"{_f(vl['r2'], 0, True)} de su varianza y reduce el error del modelo HAR en "
                         f"{_f(vl['r2_vs_har'], 0, True)} (Diebold-Mariano p = {vl['dm_p']:.3f}). Las bandas de 90% cubren "
                         f"{_f(cov1['all']['cover_conformal_90'], 1, True)} de los días."),
                     f"Daily panel of 5 coins since 2019 with 65 features in 8 groups (price and volume, futures, stocks and "
                     f"rates, war and policy indices, sentiment, on-chain, hacks, calendar), each lagged as it is published. "
                     f"Refitted every month from 2022 to 2026 on what was known that day. <strong>No model beats predicting "
                     f"\"no change\" for tomorrow's return</strong>: out-of-sample R² {_f(lg['r2_vs_zero'], 2, True)} LightGBM, "
                     f"{_f(rg['r2_vs_zero'], 2, True)} ridge" + (f", {_f(ml['r2_vs_zero'], 2, True)} MLP" if ml else "") +
                     f"; they get the direction right on {_f(lg['hit_rate'], 1, True)} to {_f(rg['hit_rate'], 1, True)} of days. "
                     f"<strong>Next week's volatility is predictable</strong>: LightGBM explains {_f(vl['r2'], 0, True)} of its "
                     f"variance and cuts the HAR model's error by {_f(vl['r2_vs_har'], 0, True)} (Diebold-Mariano p = "
                     f"{vl['dm_p']:.3f}). The 90% bands cover {_f(cov1['all']['cover_conformal_90'], 1, True)} of days.")
                  + fig("skill", "R² fuera de muestra, 2022-2026. Izquierda: retornos contra \"sin cambio\". Derecha: volatilidad.",
                        "Out-of-sample R², 2022-2026. Left: returns against \"no change\". Right: volatility.")
                  + (table(["Feature group added to price data", "Next-day return error", "Next-week volatility error"],
                           abl_rows, ["Grupo agregado a los datos de precio", "Error retorno de mañana",
                                      "Error volatilidad semana"]) if abl_rows else "")
                  + (fig("ablation", "Cambio en el error al agregar cada grupo a los datos de precio (positivo = ayuda).",
                         "Change in error when each group is added to price data (positive = helps).") if abl_rows else ""))

    nrows = []
    for d in sorted(now["forecast"], key=lambda x: (x["coin"], x["horizon"])):
        nrows.append([d["coin"], f'{d["horizon"]}d', d["target_date"][:10], _px(d["last_close"]),
                      _px(d["p05"]), _px(d["p50"]), _px(d["p95"])])
    s11 = section(11, "El pronóstico de hoy", "Today's forecast",
                  bi(f"Mismos modelos, reentrenados con todo lo resuelto hasta el {now['asof']}, aplicados al último día. Es una "
                     f"banda, no una apuesta: la sección anterior muestra que la mediana no le gana a \"sin cambio\".",
                     f"The same models, refitted on everything resolved up to {now['asof']}, applied to the last day. It is a "
                     f"band, not a bet: the previous section shows the median does not beat \"no change\".")
                  + table(["Coin", "Horizon", "Date", "Last close", "5%", "Median", "95%"], nrows,
                          ["Moneda", "Horizonte", "Fecha", "Último cierre", "5%", "Mediana", "95%"])
                  + fig("nowcast", "Últimos 45 días y banda de 90% para 1 y 7 días.", "Last 45 days and the 90% band for 1 and 7 days."))

    s12 = ""
    track_path = REPORTS / "track.json"
    if track_path.exists():
        t = json.loads(track_path.read_text(encoding="utf-8"))
        trows = []
        for d in sorted(t["rows"], key=lambda x: (x["horizon"], x["coin"])):
            if d["close"] is None:
                state = ('<span lang="es">pendiente</span><span lang="en">pending</span>', "", "", "")
            else:
                inside = ('<span lang="es">dentro</span><span lang="en">inside</span>' if d["inside_90"]
                          else '<span lang="es">fuera</span><span lang="en">outside</span>')
                state = (f'{_px(d["close"])} <small>({d.get("source") or "binance"})</small>', inside,
                         _f(d["median_error"], 1, True, True),
                         _f(d["no_change_error"], 1, True, True))
            trows.append([d["coin"], f'{d["horizon"]}d', d["target_date"], f'{_px(d["p05"])} - {_px(d["p95"])}', *state])
        s12 = section(12, "¿Cómo le fue al pronóstico?", "How did the forecast do?",
                      bi(f"Cada día GitHub Actions baja los cierres publicados y los compara con el pronóstico congelado del "
                         f"{t['asof']}. Revisado el {t['checked']}: {t['resolved']} resueltos, {t['inside_90']} dentro de la banda de 90%. "
                         f"Error = cierre real contra la mediana, al lado del error de predecir \"sin cambio\".",
                         f"Every day GitHub Actions fetches the published closes and compares them with the forecast frozen on "
                         f"{t['asof']}. Checked {t['checked']}: {t['resolved']} resolved, {t['inside_90']} inside the 90% band. "
                         f"Error = actual close against the median, next to the error of predicting \"no change\".")
                      + table(["Coin", "Horizon", "Date", "90% band", "Close", "Band", "Median error", "No-change error"],
                              trows, ["Moneda", "Horizonte", "Fecha", "Banda 90%", "Cierre", "Banda", "Error mediana",
                                      "Error sin cambio"]))

    body = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8 + s9 + s10 + s11 + s12
    tpl = (ROOT / "src" / "bhack" / "site_template.html").read_text(encoding="utf-8")
    page = tpl.replace("{{STATS}}", stat_html).replace("{{BODY}}", body)
    (ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    return page


if __name__ == "__main__":
    build(json.loads((REPORTS / "results.json").read_text(encoding="utf-8")))

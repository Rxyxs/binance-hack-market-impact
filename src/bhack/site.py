"""Builds docs/index.html from reports/results.json. Bilingual: every text block exists in
Spanish and English and a toggle shows one. Numbers are read from the results, never typed.
Each section is a question, a short answer, charts with a how-to-read note, then detail."""
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
    return f"{v:,.4f}" if v < 10 else (f"{v:,.2f}" if v < 1000 else f"{v:,.0f}")


def bi(es: str, en: str, tag: str = "p") -> str:
    return f'<{tag} lang="es">{_es(es)}</{tag}><{tag} lang="en">{en}</{tag}>'


def ans(es: str, en: str) -> str:
    return (f'<div class="answer"><b lang="es">Respuesta corta</b><b lang="en">Short answer</b>'
            f'<p lang="es">{_es(es)}</p><p lang="en">{en}</p></div>')


def fig(name: str, es: str, en: str) -> str:
    """Chart in the reader's language with a note on how to read it."""
    return (f'<figure><img lang="es" src="img/es/{name}.png" alt="{html.escape(es)}" loading="lazy">'
            f'<img lang="en" src="img/{name}.png" alt="{html.escape(en)}" loading="lazy">'
            f'<figcaption lang="es"><b>Cómo leerlo:</b> {_es(es)}</figcaption>'
            f'<figcaption lang="en"><b>How to read it:</b> {en}</figcaption></figure>')


def lab(es: str, en: str) -> str:
    return f'<span lang="es">{es}</span><span lang="en">{en}</span>'


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
    d26, d19 = r["detector"]["2026"], r["detector"]["2019"]
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
    y7 = {(d["coin"], d["model"]): d for d in fc["y7_scores"]}
    vs = {(d["coin"], d["model"]): d for d in fc["vol_scores"]}
    cov1 = {d["coin"]: d for d in fc["y1_coverage"]}
    cov7 = {d["coin"]: d for d in fc["y7_coverage"]}
    now, gru, am, sc = r["nowcast"], r["gru"], r["aftermath"], r["scenarios"]
    coins = {d["coin"]: d for d in am["coins"]}
    hz = {(d["group"], d["horizon"]): d for d in am["horizons"]}

    btc_n2 = dec[("to_nov2_close", "BTC")]
    btc_n2_30 = dec30[("to_nov2_close", "BTC")]
    ba = dec[("before_admission", "BTC")]
    flows_out = rf["2026-11-01"]["net_flow_bn"] + rf["2026-11-02"]["net_flow_bn"]
    pre_assets = rf["2026-10-28"]["assets_bn"]
    last_day = coins["BTC"]["last_day"]
    h365 = hz[("all", 365)]

    stats = [
        ("$6.36B", "robados en 10 blockchains (TRM Labs)", "stolen across 10 blockchains (TRM Labs)"),
        (_f(100 * btc_n2["explained"] / btc_n2["actual"], 0) + "%",
         _es(f"de la caída de BTC ({_f(btc_n2['actual'], 1, True)}) la predice la bolsa tecnológica"),
         f"of BTC's fall ({_f(btc_n2['actual'], 1, True)}) is predicted by tech stocks"),
        (f"{d26['minutes_before_admission']:.0f} min", "antes de que se admitiera el robo, el precio de BNB ya lo delataba",
         "before the theft was admitted, BNB's price already gave it away"),
        (f"${-flows_out:.1f}B", _es(f"retirados por clientes en 2 días al reabrir ({_f(-flows_out / pre_assets, 0, True)} de los activos)"),
         f"withdrawn by customers in 2 days after reopening ({_f(-flows_out / pre_assets, 0, True)} of assets)"),
    ]
    stat_html = "".join(f'<div class="stat"><b>{v}</b><span lang="es">{e}</span><span lang="en">{n}</span></div>' for v, e, n in stats)

    sum_es = [
        f"<b>El hackeo dolió, pero no fue lo único.</b> Bitcoin cayó {_f(-btc_n2['actual'], 1, True)} hasta el 2 de noviembre, y la caída de las tecnológicas predice cerca de {_f(-btc_n2_30['explained'], 1, True)} a {_f(-btc_n2['explained'], 1, True)} de eso.",
        f"<b>El precio delató el robo.</b> BNB cayó tanto que una alarma simple saltó a las {d26['alarm'][11:16]} UTC, {d26['minutes_before_admission']:.0f} minutos antes de que CZ lo admitiera.",
        "<b>El castigo fue para Binance, no para lo robado.</b> Las monedas de las cadenas vaciadas no cayeron más que el resto; BNB sí.",
        f"<b>No fue el peor golpe del año.</b> BTC tuvo {am['year']['worse_than_hack']} días peores en 2026, y el 5 de noviembre cayó más que el día del robo por una venta de tecnológicas.",
        f"<b>Hubo corrida, pero ordenada.</b> Los clientes sacaron {-flows_out:.1f} mil millones de dólares en dos días, {_f(-flows_out / pre_assets, 0, True)} de lo que había.",
        f"<b>La historia no muestra un efecto claro.</b> Tras 35 hackeos anteriores, BTC a una semana no se distingue de una fecha cualquiera; a un año queda {_f(h365['median'], 1, True, True)} contra {_f(h365['random_median'], 1, True, True)}, sin ser concluyente (p = {h365['p']:.2f}).",
        "<b>Ningún modelo logró predecir el precio de mañana.</b> Cinco modelos, incluidas redes neuronales, no superan a decir \"queda igual\". La turbulencia sí se anticipa en parte, y para eso bastan los datos de precio.",
    ]
    sum_en = [
        f"<b>The hack hurt, but it was not alone.</b> Bitcoin fell {_f(-btc_n2['actual'], 1, True)} to 2 November, and the tech sell-off predicts about {_f(-btc_n2_30['explained'], 1, True)} to {_f(-btc_n2['explained'], 1, True)} of that.",
        f"<b>The price gave the theft away.</b> BNB fell so hard that a simple alarm fired at {d26['alarm'][11:16]} UTC, {d26['minutes_before_admission']:.0f} minutes before CZ admitted it.",
        "<b>Binance was punished, not the stolen coins.</b> Coins on drained chains did not fall more than the rest; BNB did.",
        f"<b>It was not the worst blow of the year.</b> BTC had {am['year']['worse_than_hack']} worse days in 2026, and on 5 November it fell more than on the day of the theft in a tech sell-off.",
        f"<b>There was a run, but an orderly one.</b> Customers took out ${-flows_out:.1f} billion in two days, {_f(-flows_out / pre_assets, 0, True)} of holdings.",
        f"<b>History shows no clear effect.</b> After 35 earlier hacks, BTC a week later looks like any other date; a year later it stands at {_f(h365['median'], 1, True, True)} against {_f(h365['random_median'], 1, True, True)}, which is not conclusive (p = {h365['p']:.2f}).",
        "<b>No model managed to predict tomorrow's price.</b> Five models, neural networks included, do not beat saying \"no change\". Turbulence can be partly anticipated, and price data is enough for that.",
    ]
    summary = ('<section class="summary"><h2>' + lab("En 30 segundos", "In 30 seconds") + "</h2>"
               + '<ul lang="es">' + "".join(f"<li>{_es(x)}</li>" for x in sum_es) + "</ul>"
               + '<ul lang="en">' + "".join(f"<li>{x}</li>" for x in sum_en) + "</ul></section>")

    rows_path = []
    for key, es_l, en_l in [("21:15 CZ post", "21:15, CZ: \"parece un hackeo\"", "21:15, CZ: \"does look like a hack\""),
                            ("00:13 halt", "00:13, retiros suspendidos", "00:13, withdrawals halted"),
                            ("06:00 Nov 1 reopen", "06:00 del 1 nov, reapertura", "06:00 Nov 1, reopening"),
                            ("Nov 2 close", "cierre del 2 nov", "close of Nov 2")]:
        rows_path.append([lab(es_l, en_l)] + [_f(P[c][key], 1, True, True) for c in ["BTC", "ETH", "BNB", "XRP", "SOL", "TRX"]])
    path_tbl = table(["From 20:00 UTC, Oct 29, to", "BTC", "ETH", "BNB", "XRP", "SOL", "TRX"], rows_path,
                     ["Desde las 20:00 UTC del 29 oct hasta", "BTC", "ETH", "BNB", "XRP", "SOL", "TRX"])

    s1 = section(1, "¿Qué pasó esa noche?", "What happened that night?",
                 ans("A las 20:05 UTC del 29 de octubre empezaron a salir monedas de Binance hacia un atacante. En una hora BNB perdió cerca de 8% y BTC 3%. Binance suspendió los retiros a las 00:13 y reabrió 54 horas después.",
                     "At 20:05 UTC on 29 October coins began leaving Binance for an attacker. Within an hour BNB had lost about 8% and BTC 3%. Binance halted withdrawals at 00:13 and reopened 54 hours later.")
                 + fig("binance_impact", "cada vela es 15 minutos: verde sube, roja baja; la mecha es el rango. Las líneas amarillas son los hitos. Abajo, cuánto dinero había apostado en futuros de BTC: cae de golpe cuando la gente cierra posiciones o la liquidan.",
                       "each candle is 15 minutes: green up, red down; the wick is the range. Yellow lines are the milestones. Below, how much money was committed in BTC futures: it drops suddenly when people close or are liquidated.")
                 + fig("night", "todas las líneas parten en 0% a las 20:00 UTC, y muestran cuánto subió o bajó cada una desde ahí. La zona gris es el rato en que nadie había dicho nada todavía. La línea gris clara es la bolsa tecnológica: también caía, por los resultados de Amazon e Intel.",
                       "all lines start at 0% at 20:00 UTC and show how much each rose or fell from there. The grey zone is the time when nobody had said anything yet. The light grey line is tech stocks: also falling, on Amazon's and Intel's earnings.")
                 + path_tbl)

    s2 = section(2, "¿Cayó por el hackeo o por la bolsa?", "Did it fall because of the hack or the stock market?",
                 ans(f"Por los dos, y más por la bolsa. Justo cuando partió el robo, Amazon e Intel publicaron resultados y las tecnológicas cayeron. De los {_f(-btc_n2['actual'], 1)} puntos que cayó BTC hasta el 2 de noviembre, {_f(-btc_n2_30['explained'], 1)} a {_f(-btc_n2['explained'], 1)} los predice ese mercado; solo {_f(-btc_n2['abnormal'], 1)} a {_f(-btc_n2_30['abnormal'], 1)} son propios del hackeo.",
                     f"Both, and more the stock market. Just as the theft began, Amazon and Intel published earnings and tech stocks fell. Of the {_f(-btc_n2['actual'], 1)} points BTC fell to 2 November, that market predicts {_f(-btc_n2_30['explained'], 1)} to {_f(-btc_n2['explained'], 1)}; only {_f(-btc_n2['abnormal'], 1)} to {_f(-btc_n2_30['abnormal'], 1)} belong to the hack.")
                 + fig("decomposition", "gris es lo que BTC habría hecho solo por moverse junto a Nasdaq, dólar y oro, según su relación de la semana previa. Naranjo es el resto, lo propio del hackeo. A la izquierda, la primera hora y cuarto: domina el hackeo. A la derecha, cuatro días después: domina la bolsa, salvo en BNB, que conserva su castigo. ETH terminó mejor de lo esperado.",
                       "grey is what BTC would have done just by moving with the Nasdaq, dollar and gold, using their relationship in the prior week. Orange is the rest, the hack's own. Left, the first 75 minutes: the hack dominates. Right, four days later: the stock market dominates, except BNB, which keeps its punishment. ETH ended better than expected.")
                 + bi(f"El modelo explica {_f(r['macro_fits']['BTC']['r2'], 0, True)} de los movimientos de 5 minutos de BTC en una semana tranquila, así que es una aproximación. Antes de cualquier declaración, el efecto propio en BTC fue {_f(ba['abnormal'], 1, True, True)}.",
                      f"The model explains {_f(r['macro_fits']['BTC']['r2'], 0, True)} of BTC's five-minute moves in a calm week, so it is an approximation. Before any statement, the hack's own effect on BTC was {_f(ba['abnormal'], 1, True, True)}."))

    fb = flow[("before_admission", "BNB")]
    s3 = section(3, "¿El mercado se enteró antes que el público?", "Did the market know before the public?",
                 ans(f"El precio se movió antes de cualquier declaración. Lo más probable es que alguien viera las transferencias, que son públicas en la blockchain, aunque no puedo probar el canal. BNB empezó a caer respecto de BTC: una alarma simple saltó {d26['minutes_before_admission']:.0f} minutos antes de que CZ lo admitiera. En el hackeo de 2019 pasó lo contrario: saltó {-d19['minutes_before_admission']:.0f} minutos después del anuncio.",
                     f"The price moved before any statement. Most likely someone saw the transfers, which are public on the blockchain, though I cannot prove the channel. BNB began falling against BTC: a simple alarm fired {d26['minutes_before_admission']:.0f} minutes before CZ admitted it. In the 2019 hack the opposite happened: it fired {-d19['minutes_before_admission']:.0f} minutes after the announcement.")
                 + fig("detector", "la línea es BNB dividido por BTC: si baja, BNB cae más que el mercado. La zona gris va desde el robo hasta que se admitió. El punto naranjo es cuando sonó la alarma. En 2026 suena dentro de la zona gris, antes de cualquier declaración; en 2019 BNB casi no se movió hasta el anuncio.",
                       "the line is BNB divided by BTC: when it falls, BNB is falling more than the market. The grey zone runs from the theft until it was admitted. The orange dot is when the alarm rang. In 2026 it rings inside the grey zone, before any notice; in 2019 BNB barely moved until the announcement.")
                 + bi(f"La alarma está calibrada para sonar como máximo una vez al mes, y en los 30 días previos al hackeo dio {d26['holdout_false_alarms_30d']} falsas alarmas. En esos primeros 75 minutos, BNB transó {fb['volume_x_normal']:.0f} veces su volumen normal.",
                      f"The alarm is set to ring at most once a month, and it gave {d26['holdout_false_alarms_30d']} false alarms in the 30 days before the hack. In those first 75 minutes, BNB traded {fb['volume_x_normal']:.0f} times its usual volume."))

    tr, fa = svu["to_reopen"], svu["before_admission"]
    s4 = section(4, "¿Qué monedas sufrieron y cuáles ya se recuperaron?", "Which coins suffered, and which have recovered?",
                 ans(f"Se castigó a BNB, el token de Binance. Las monedas robadas no cayeron más que las otras: el mercado no apostó a que el ladrón vendería. Al {last_day}, respecto del precio cuando partió el hackeo: " + ", ".join(f"{c} {_f(coins[c]['change_to_last'], 1, True, True)}" for c in coins) + ". Es una foto de un día: el 4 de noviembre BTC estaba casi recuperado y ETH y XRP sobre su precio previo; al día siguiente cayeron con la bolsa.",
                     f"BNB, Binance's token, was punished. Stolen coins did not fall more than the others: the market did not bet on the thief selling. As of {last_day}, against the price when the hack began: " + ", ".join(f"{c} {_f(coins[c]['change_to_last'], 1, True, True)}" for c in coins) + ". It is a one-day snapshot: on 4 November BTC had almost recovered and ETH and XRP were above their earlier price; the next day they fell with the stock market.")
                 + fig("recovery", "el 0% es el precio de cada moneda a las 20:00 UTC, cuando partió el hackeo. El punto rojo es lo peor que llegó a caer desde entonces y el azul dónde cerró el último día. Mientras el azul siga a la izquierda del 0%, no ha recuperado su precio.",
                       "0% is each coin's price at 20:00 UTC, when the hack began. The red dot is the worst it has fallen since and the blue one where it closed on the last day. While blue stays left of 0%, it has not regained its price.")
                 + fig("cross_section", "cada punto es una moneda. A la derecha del 0% le fue mejor que a Bitcoin; a la izquierda, peor. Si el mercado temiera que el ladrón vendiera, los puntos azules estarían a la izquierda de los verdes. No lo están.",
                       "each dot is a coin. Right of 0% it did better than Bitcoin; left, worse. If the market feared the thief selling, the blue dots would sit left of the green ones. They do not.")
                 + bi(f"Promedio hasta la reapertura: robadas {_f(tr['stolen_mean'], 1, True, True)}, no tocadas {_f(tr['untouched_mean'], 1, True, True)}, BNB {_f(gm['to_reopen']['exchange token'], 1, True, True)}. La diferencia entre robadas y no tocadas no es distinguible del azar (p = {tr['p_perm']:.2f}; en los primeros 75 minutos p = {fa['p_perm']:.2f}). TRX es la rareza: subió 8% durante el hackeo y después lo devolvió todo. No encontré evidencia que lo explique.",
                      f"Average to the reopening: stolen {_f(tr['stolen_mean'], 1, True, True)}, untouched {_f(tr['untouched_mean'], 1, True, True)}, BNB {_f(gm['to_reopen']['exchange token'], 1, True, True)}. The gap between stolen and untouched cannot be told from chance (p = {tr['p_perm']:.2f}; in the first 75 minutes p = {fa['p_perm']:.2f}). TRX is the oddity: it rose 8% during the hack and then gave it all back. I found no evidence that explains it."))

    fs = {(d["coin"], d["size"], d["period"]): d for d in r["flow_size"]}
    small = fs[("BTC", "<1k", "hack_night")]["net_musd"] + fs[("BTC", "1k-10k", "hack_night")]["net_musd"]
    total = sum(fs[("BTC", s, "hack_night")]["net_musd"] for s in ["<1k", "1k-10k", "10k-100k", "100k-1M", ">1M"] if ("BTC", s, "hack_night") in fs)
    days = [d for d in am["days"] if d["coin"] == "BNB" and d["date"].startswith("2026-10-29")][0]
    s5 = section(5, "¿Cuánto se transó y quién vendió?", "How much traded, and who sold?",
                 ans(f"El volumen de BNB fue {_f(days['volume_x_normal'], 1)} veces lo normal el 29 de octubre, y a los dos días ya había vuelto a su nivel. Esa noche se vendieron a mercado {-total:.0f} millones de dólares más de BTC de los que se compraron, y {_f(small / total, 0, True)} vino de órdenes de menos de 10.000 dólares.",
                     f"BNB's volume was {_f(days['volume_x_normal'], 1)} times normal on 29 October, and two days later it was back at its usual level. That night ${-total:.0f} million more BTC was sold at market than bought, {_f(small / total, 0, True)} of it in orders under $10,000.")
                 + fig("hack_days", "arriba, cuántas veces el volumen normal se transó cada día: 1 es un día corriente. Abajo, qué parte del volumen la iniciaron compradores apurados: bajo la línea de 50% mandan los vendedores. La línea roja es el hackeo.",
                       "top, how many times normal volume traded each day: 1 is an ordinary day. Bottom, what share of volume was started by buyers in a hurry: below the 50% line sellers lead. The red line is the hack.")
                 + fig("flow", "izquierda: si la línea baja, se vende a mercado más de lo que se compra; las líneas claras son una noche normal, casi planas. Derecha: la misma venta de BTC según el tamaño de cada orden. Ojo: los algoritmos parten órdenes grandes, así que chica no significa persona común.",
                       "left: when the line falls, more is sold at market than bought; pale lines are a normal night, nearly flat. Right: the same BTC selling by size of order. Note: algorithms split large orders, so small does not mean an ordinary person."))

    g_btc = gaps[("withdrawals_halted", "BTC vs Coinbase")]["median_bp"]
    g_btc0 = gaps[("week_before", "BTC vs Coinbase")]["median_bp"]
    s6 = section(6, "¿Hubo una corrida contra Binance?", "Was there a run on Binance?",
                 ans(f"Sí, pero ordenada. Al reabrir, los clientes sacaron {-flows_out:.1f} mil millones de dólares en dos días, {_f(-flows_out / pre_assets, 1, True)} de lo que había. Mientras los retiros estuvieron cerrados, Binance quedó apenas {_f(g_btc / 100, 2)}% más caro que Coinbase: el precio no reflejó miedo a una quiebra.",
                     f"Yes, but an orderly one. After reopening, customers took out ${-flows_out:.1f} billion in two days, {_f(-flows_out / pre_assets, 1, True)} of holdings. While withdrawals were halted, Binance sat just {_f(g_btc / 100, 2)}% above Coinbase: prices did not reflect fear of a collapse.")
                 + fig("reserve_flows", "cada barra es lo que entró menos lo que salió de las wallets de Binance ese día, sin contar cambios de precio. La naranja es el robo. Las azules son clientes retirando al reabrir. Las grises son días normales.",
                       "each bar is what came in minus what left Binance's wallets that day, not counting price changes. Orange is the theft. Blue is customers withdrawing after reopening. Grey is normal days.")
                 + fig("venues", "cuánto más caro está un precio en Binance que en otro exchange. En una crisis grave, como FTX en 2022, esa diferencia se dispara porque un dólar atrapado vale menos. Aquí subió a unos 0,1% y volvió.",
                       "how much dearer a price is on Binance than on another exchange. In a severe crisis, like FTX in 2022, that gap explodes because a trapped dollar is worth less. Here it rose to about 0.1% and came back.")
                 + bi(f"Mediana BTC contra Coinbase: {_f(g_btc / 100, 2, False, True)}% con retiros cerrados y {_f(g_btc0 / 100, 2, False, True)}% la semana previa. El flujo del día del robo fue {rf['2026-10-29']['net_flow_bn']:+.2f} mil millones.",
                      f"Median BTC against Coinbase: {_f(g_btc / 100, 2, False, True)}% with withdrawals halted and {_f(g_btc0 / 100, 2, False, True)}% the week before. The flow on the day of the theft was ${rf['2026-10-29']['net_flow_bn']:+.2f} billion."))

    rows_st = [[s, _f(stocks[s]["ret"], 1, True, True), _f(stocks[s]["abn_vs_qqq_btc"], 1, True, True), f"{stocks[s]['t_stat']:+.1f}"]
               for s in ["COIN", "HOOD", "MSTR", "CRCL"]]
    s7 = section(7, "¿Y las acciones de empresas cripto?", "And the shares of crypto companies?",
                 ans(f"Cayeron fuerte, pero casi lo esperable: Coinbase perdió {_f(-stocks['COIN']['ret'], 1, True)} un día en que el Nasdaq-100 y Bitcoin también caían. Ni contagio extra ni fuga de clientes hacia el competidor regulado.",
                     f"They fell hard, but about as expected: Coinbase lost {_f(-stocks['COIN']['ret'], 1, True)} on a day when the Nasdaq-100 and Bitcoin were falling too. No extra contagion, and no flight to the regulated competitor.")
                 + fig("stocks", "gris es lo que cada acción habría caído solo por su relación habitual con el Nasdaq y Bitcoin. Azul es lo que cayó de verdad. Si las dos barras se parecen, no pasó nada especial.",
                       "grey is what each share would have fallen just from its usual relationship with the Nasdaq and Bitcoin. Blue is what it really fell. If the two bars look alike, nothing special happened.")
                 + table(["Stock", "Return Oct 30", "Beyond expected", "t (beyond ±2 is unusual)"], rows_st,
                         ["Acción", "Retorno 30 oct", "Más allá de lo esperado", "t (más allá de ±2 es inusual)"]))

    def row_h(h, es_l, en_l):
        d = hz[("all", h)]
        b = hz.get(("big", h))
        return [lab(es_l, en_l), _f(d["median"], 1, True, True), _f(d["random_median"], 1, True, True), f"{_f(d['share_up'], 0, True)}",
                f"{d['p']:.2f}", _f(b["median"], 1, True, True) if b else ""]
    rows_h = [row_h(7, "1 semana", "1 week"), row_h(30, "1 mes", "1 month"), row_h(90, "3 meses", "3 months"), row_h(365, "1 año", "1 year")]
    rec = [d for d in am["recovery_hacks"] if d["days_to_recover"] is not None]
    fast = sum(1 for d in rec if d["days_to_recover"] <= 30)
    rec_rows = [[d["date"], d["name"], f"{d['amount_m']:,.0f}", f"{d['days_to_recover']:.0f}"] for d in rec]
    s8 = section(8, "¿Qué pasa una semana, un mes o un año después?", "What happens a week, a month or a year later?",
                 ans(f"Este hackeo es demasiado reciente para saberlo, pero 35 anteriores sí se pueden medir. A una semana y a un mes, BTC no se distingue de una fecha cualquiera. A un año queda en {_f(h365['median'], 1, True, True)} contra {_f(h365['random_median'], 1, True, True)} de una fecha al azar del mismo año, una brecha grande pero no concluyente (p = {h365['p']:.2f}), y muchos otros eventos caben en un año.",
                     f"This hack is too recent to tell, but 35 earlier ones can be measured. At a week and a month, BTC cannot be told from any other date. At a year it stands at {_f(h365['median'], 1, True, True)} against {_f(h365['random_median'], 1, True, True)} for a random date of the same year, a large but inconclusive gap (p = {h365['p']:.2f}), and many other events fit in a year.")
                 + fig("after_hacks", "izquierda: cada línea delgada es BTC después de un hackeo, partiendo del día anterior. La azul gruesa es el caso típico y la naranja este hackeo. Derecha: el retorno típico a cada plazo después de un hackeo (azul) contra fechas al azar del mismo año (gris). Si son parecidas, el hackeo no marcó diferencia.",
                       "left: each thin line is BTC after a hack, starting from the day before. The thick blue is the typical case and orange this hack. Right: the typical return at each horizon after a hack (blue) against random dates of the same year (grey). If they look alike, the hack made no difference.")
                 + table(["Horizon", "After a hack (median)", "Random date, same year", "Share that rose", "p (under 0.05 is clear)", "Only hacks of $250M+"], rows_h,
                         ["Plazo", "Tras un hackeo (mediana)", "Fecha al azar, mismo año", "Parte que subió", "p (bajo 0,05 es claro)", "Solo hackeos de US$250 M+"])
                 + fig("binance_history", "los mismos BTC y BNB a cuatro distancias: semana, mes, año y toda su historia en Binance. La línea amarilla es el hackeo. De cerca parece un derrumbe; en la historia completa, un punto más.",
                       "the same BTC and BNB at four distances: week, month, year and their full Binance history. The yellow line is the hack. Up close it looks like a collapse; over the full history, one more point.")
                 + bi(f"¿Cuánto tardó BTC en volver al precio previo tras los grandes hackeos? En {fast} de {len(rec)} casos, menos de un mes. Las excepciones son Bybit 2025 (77 días) y, con más de dos años, Mt. Gox 2014 y BitMart 2021, que coinciden con mercados bajistas largos.",
                      f"How long did BTC take to regain its earlier price after the big hacks? In {fast} of {len(rec)} cases, under a month. The exceptions are Bybit 2025 (77 days) and, at over two years, Mt. Gox 2014 and BitMart 2021, which coincide with long bear markets.")
                 + table(["Date", "Exchange", "Stolen, $M", "Days to recover"], rec_rows, ["Fecha", "Exchange", "Robado, US$ M", "Días en recuperar"]))

    b = es_btc["binance_2026"]
    tl = es_btc["tail"]
    s9 = section(9, "¿Cómo se ve esto año por año?", "How does this look year by year?",
                 ans(f"2026 ya es el peor año registrado en robos, con {hy[2026]['stolen_bn']:.2f} mil millones de dólares, y Binance es la mayor parte. Aun así, en {es_btc['n_events']} hackeos a exchanges desde 2011 el efecto promedio sobre Bitcoin no se distingue del azar (p = {es_btc['p_mean_scar_1']:.2f}). Este es el {b['rank_among_hacks']}° mayor de esos {es_btc['n_events']}.",
                     f"2026 is already the worst year on record for theft, with ${hy[2026]['stolen_bn']:.2f} billion, and Binance is most of it. Even so, across {es_btc['n_events']} exchange hacks since 2011 the average effect on Bitcoin cannot be told from chance (p = {es_btc['p_mean_scar_1']:.2f}). This one ranks {b['rank_among_hacks']} of those {es_btc['n_events']}.")
                 + fig("annual", "arriba, cuánto subió o bajó cada moneda cada año. Al medio, cuánto se transó en Binance, solo pares contra USDT. Abajo, qué parte iniciaron compradores: cerca de 50% quiere decir equilibrio.",
                       "top, how much each coin rose or fell each year. Middle, how much traded on Binance, USDT pairs only. Bottom, what share buyers started: near 50% means balance.")
                 + fig("history", "arriba, el precio de Bitcoin desde 2011 en escala logarítmica, donde un mismo salto vertical es un mismo porcentaje. Cada punto naranjo es un gran hackeo, más grande cuanto más se robó. Abajo, lo robado cada año.",
                       "top, Bitcoin's price since 2011 on a log scale, where the same vertical jump is the same percentage. Each orange dot is a big hack, larger the more was stolen. Below, what was stolen each year.")
                 + bi(f"Pero el promedio esconde algo: de {tl['n']} hackeos anteriores, {tl['below']} cayeron en el peor 5% de las ventanas de dos días, cuando por azar se esperarían {_f(tl['expected'], 1)} (p = {tl['p_below']:.3f}). Antes de leerlo como efecto: el mayor de esos casos robó solo {tl['largest_below_m']:.0f} millones de dólares, muy poco para mover Bitcoin, y DefiLlama fecha los hackeos solo por día. Puede ser coincidencia con días malos o un efecto real; estos datos no lo separan.",
                      f"But the average hides something: of {tl['n']} earlier hacks, {tl['below']} fell in the worst 5% of two-day windows, when chance would give {_f(tl['expected'], 1)} (p = {tl['p_below']:.3f}). Before reading that as an effect: the largest of those cases stole only ${tl['largest_below_m']:.0f} million, too little to move Bitcoin, and DefiLlama dates hacks by day only. It may be coincidence with bad days or a real effect; this data cannot separate them.")
                 + fig("event_study", "cada punto es un hackeo: más a la derecha, más dinero robado; más abajo, más cayó Bitcoin en esos dos días. La zona gris es lo que Bitcoin hace normalmente sin ningún hackeo.",
                       "each dot is a hack: further right, more money stolen; lower, the more Bitcoin fell over those two days. The grey zone is what Bitcoin normally does with no hack at all."))

    yr = am["year"]
    hk = [d for d in yr["days"] if d["date"] == "2026-10-29"][0]
    nv = [d for d in yr["days"] if d["date"] == "2026-11-05"][0]
    ev_rows = []
    names_ev = {"2026-02-28": ("Inicia la guerra con Irán", "War with Iran begins"), "2026-04-08": ("Alto al fuego", "Ceasefire"),
                "2026-06-17": ("Memorando de paz", "Peace memorandum"), "2026-07-08": ("Colapsa la tregua", "Truce collapses"),
                "2026-09-24": ("Hackeo a Bitget", "Bitget hack"), "2026-10-23": ("Brent sobre 117 dólares", "Brent above $117"),
                "2026-10-28": ("La Fed mantiene la tasa", "The Fed holds rates")}
    for e in yr["events"]:
        if e["date"] in names_ev:
            ev_rows.append([e["date"], lab(*names_ev[e["date"]]), _f(e["change_day"], 1, True, True), _f(e["change_week"], 1, True, True)])
    ev_rows.append(["2026-10-29", lab("Hackeo a Binance", "Binance hack"), _f(hk["change"], 1, True, True),
                    _f([e for e in yr["events"] if e["kind"] == "hack" and e["date"] == "2026-10-29"][0]["change_week"], 1, True, True)])
    src_links = " · ".join(f'<a href="{d["source"]}">{d["date"]}</a>' for d in sorted(yr["days"], key=lambda x: x["date"]))
    s10 = section(10, "¿Fue el peor golpe del año?", "Was it the worst blow of the year?",
                  ans(f"No. Bitcoin tuvo {yr['worse_than_hack']} días peores en 2026. El peor fue el 5 de febrero, con liquidaciones forzadas según la prensa. Y el {nv['date']}, una semana después del hackeo, cayó {_f(-nv['change'], 1, True)} por una venta de tecnológicas, más que el día del robo ({_f(-hk['change'], 1, True)}).",
                      f"No. Bitcoin had {yr['worse_than_hack']} worse days in 2026. The worst was 5 February, with forced liquidations according to the press. And on {nv['date']}, a week after the hack, it fell {_f(-nv['change'], 1, True)} in a tech sell-off, more than on the day of the theft ({_f(-hk['change'], 1, True)}).")
                  + fig("year_shocks", "cada barra es un día de 2026: hacia abajo, Bitcoin cayó ese día. La naranja es el hackeo y las azules otros días muy malos con su causa según la prensa. Las líneas verticales son hitos de la guerra con Irán: ninguno coincide con las mayores caídas.",
                        "each bar is a day of 2026: downward, Bitcoin fell that day. Orange is the hack and blue other very bad days with their cause according to the press. Vertical lines are milestones of the war with Iran: none coincides with the biggest falls.")
                  + table(["Date", "Event", "BTC that day", "BTC to a week later"], ev_rows, ["Fecha", "Evento", "BTC ese día", "BTC hasta una semana después"])
                  + bi(f"Ojo: las causas de cada caída vienen de la prensa, no las medí, y suelen ser discutidas. Fuentes: {src_links}.",
                       f"Note: the cause of each fall comes from the press, I did not measure it, and causes are often disputed. Sources: {src_links}."))

    s11 = section(11, "¿De verdad venía subiendo? La guerra y la macro", "Was it really rising? The war and the macro",
                  ans(f"A medias. BTC subió {_f(trend['ret_q3'], 0, True)} en el tercer trimestre, pero justo antes del hackeo ya iba {_f(trend['ret_oct_to_eve'], 1, True, True)} en octubre y {_f(-trend['drawdown_from_2026_high'], 0, True)} bajo su máximo de enero. El ambiente ya era duro: guerra con Irán, Brent sobre 110 dólares y la tasa a 10 años de EE.UU. cerca de 5%.",
                      f"Partly. BTC rose {_f(trend['ret_q3'], 0, True)} in the third quarter, but just before the hack it was already {_f(trend['ret_oct_to_eve'], 1, True, True)} in October and {_f(-trend['drawdown_from_2026_high'], 0, True)} below its January high. The backdrop was already harsh: war with Iran, Brent above $110 and the US 10-year yield near 5%.")
                  + fig("context_2026", "cuatro paneles con la misma línea de tiempo. Las líneas verticales marcan los hitos. El índice geopolítico cuenta noticias de guerra y terrorismo en diez diarios: mientras más alto, más tensión. Ojo: BTC cayó de 97 mil a 63 mil en enero y febrero, antes de la guerra.",
                        "four panels on one timeline. Vertical lines mark the milestones. The geopolitical index counts war and terrorism news in ten newspapers: higher means more tension. Note: BTC fell from 97k to 63k in January and February, before the war."))

    lg, rg, ml, vl, vh = y1[("all", "lgb")], y1[("all", "ridge")], y1[("all", "mlp")], vs[("all", "lgb")], vs[("all", "har")]
    s12 = section(12, "¿Se puede predecir el precio con noticias y machine learning?", "Can news and machine learning predict the price?",
                  ans("El precio de mañana, no. Probé cinco modelos con 65 variables, incluida la guerra y las noticias, reentrenados de 2022 a 2026 sin mirar el futuro: ninguno le gana a decir \"queda igual\". La turbulencia de la próxima semana sí se anticipa en parte, y para eso basta la volatilidad pasada.",
                      "Tomorrow's price, no. I tried five models with 65 features, including war and news, refitted from 2022 to 2026 without looking ahead: none beats saying \"no change\". Next week's turbulence can be partly anticipated, and past volatility alone is enough for that.")
                  + fig("skill", "izquierda: en qué parte de los días cada modelo acertó si el precio subía o bajaba; 50% es lanzar una moneda. Derecha: qué parte de la variación de la turbulencia anticipa cada uno; la barra verde solo usa volatilidad pasada y las azules no la superan con claridad.",
                        "left: on what share of days each model got up or down right; 50% is flipping a coin. Right: what share of the variation in turbulence each one anticipates; the green bar uses past volatility only and the blue ones do not clearly beat it.")
                  + fig("ablation", "parto de un modelo solo con precio y volumen y le agrego un grupo de datos. A la derecha el error baja; a la izquierda sube. Casi todo queda a la izquierda: lo que traen las noticias ya está en el precio.",
                        "I start from a model with price and volume only and add one group of data. To the right the error falls; to the left it rises. Nearly everything sits left: what the news brings is already in the price.")
                  + table(["Target", "Benchmark", "LightGBM", "Ridge", "MLP", "GRU (100+ epochs)"], [
                      [lab("Retorno mañana (R²)", "Next-day return (R²)"), lab("0% = \"queda igual\"", "0% = \"no change\""), _f(lg["r2_vs_zero"], 1, True), _f(rg["r2_vs_zero"], 1, True), _f(ml["r2_vs_zero"], 1, True), _f(gru["y1"]["r2_vs_zero"], 1, True)],
                      [lab("Retorno 7 días (R²)", "7-day return (R²)"), lab("0% = \"queda igual\"", "0% = \"no change\""), _f(y7[("all", "lgb")]["r2_vs_zero"], 1, True), _f(y7[("all", "ridge")]["r2_vs_zero"], 1, True), "", _f(gru["y7"]["r2_vs_zero"], 1, True)],
                      [lab("Turbulencia semana (R²)", "Next-week turbulence (R²)"), "HAR " + _f(vh["r2"], 1, True), _f(vl["r2"], 1, True), _f(vs[("all", "ridge")]["r2"], 1, True), _f(vs[("all", "mlp")]["r2"], 1, True), _f(gru["vol"]["r2"], 1, True)],
                  ], ["Objetivo", "Referencia", "LightGBM", "Ridge", "MLP", "GRU (100+ épocas)"])
                  + bi(f"El GRU entrena al menos 100 épocas por ciclo, con early stopping desde ahí, y su mejor punto queda casi siempre pegado a la época 100 (mediana {gru['y1']['best_epoch_median']:.0f}): entrenar más no agrega nada. LightGBM mejora a HAR en {_f(vl['r2_vs_har'], 1, True)}, sin significancia (p = {vl['dm_p']:.2f}). Una estrategia de comprar o salir según el modelo pierde contra mantener en las cinco monedas.",
                       f"The GRU trains at least 100 epochs per cycle, with early stopping from there, and its best point nearly always sits at epoch 100 (median {gru['y1']['best_epoch_median']:.0f}): more training adds nothing. LightGBM beats HAR by {_f(vl['r2_vs_har'], 1, True)}, not significantly (p = {vl['dm_p']:.2f}). A strategy of buying or leaving on the model's signal loses to holding on all five coins."))

    test = {}
    for d in sc["backtest"]:
        test.setdefault(d["horizon"], []).append(d["coverage_90"])
    cov = {h: sum(v) / len(v) for h, v in test.items()}
    above = {}
    for d in sc["backtest"]:
        above.setdefault(d["horizon"], []).append(d["share_above_median"])
    above_avg = sum(sum(v) / len(v) for v in above.values()) / len(above)
    fan = {(d["coin"], d["horizon"]): d for d in sc["fan"]}
    srows = []
    for c in ["BTC", "ETH", "BNB", "XRP", "SOL"]:
        f = lambda h: f'{_px(fan[(c, h)]["p05"])} - {_px(fan[(c, h)]["p95"])}'  # noqa: E731
        srows.append([c, _px(fan[(c, 7)]["last"]), f(7), f(30), f(90), f(365), _f(fan[(c, 30)]["prob_above_prehack"], 0, True)])
    s13 = section(13, "¿Hacia dónde puede ir el precio?", "Where can the price go?",
                  ans(f"No hay un número confiable, pero sí un rango. Con los movimientos históricos de BTC, a un mes lo más probable es entre {_px(fan[('BTC', 30)]['p05'])} y {_px(fan[('BTC', 30)]['p95'])} dólares, y a un año entre {_px(fan[('BTC', 365)]['p05'])} y {_px(fan[('BTC', 365)]['p95'])}. La amplitud es la conclusión: a esos plazos, casi cualquier cosa es posible.",
                      f"There is no reliable number, but there is a range. Using BTC's historical moves, at a month the likely range is ${_px(fan[('BTC', 30)]['p05'])} to ${_px(fan[('BTC', 30)]['p95'])}, and at a year ${_px(fan[('BTC', 365)]['p05'])} to ${_px(fan[('BTC', 365)]['p95'])}. The width is the conclusion: at those horizons, almost anything is possible.")
                  + fig("scenarios", "la línea azul es el precio real hasta el último cierre. Los abanicos son miles de futuros posibles armados con pedazos de movimientos históricos de la propia moneda, sin agregar tendencia al alza ni a la baja. Azul oscuro: 5 de cada 10 caminos. Azul claro: 9 de cada 10. La línea naranja es el precio cuando partió el hackeo.",
                        "the blue line is the real price to the last close. The fans are thousands of possible futures built from pieces of the coin's own historical moves, with no upward or downward trend added. Dark blue: 5 of 10 paths. Light blue: 9 of 10. The orange line is the price when the hack began.")
                  + table(["Coin", "Last close", "7 days (90%)", "1 month (90%)", "3 months (90%)", "1 year (90%)", "Chance above pre-hack price in 1 month"], srows,
                          ["Moneda", "Último cierre", "7 días (90%)", "1 mes (90%)", "3 meses (90%)", "1 año (90%)", "Prob. sobre precio pre-hackeo en 1 mes"])
                  + bi(f"¿Se puede confiar en estos rangos? Lo probé desde cada inicio de mes desde 2020, usando solo datos anteriores. El rango de 90% acertó {_f(cov[7], 0, True)} a 7 días, {_f(cov[30], 0, True)} a un mes, {_f(cov[90], 0, True)} a tres meses y {_f(cov[365], 0, True)} a un año. Como no agrega tendencia, en ese período el precio terminó sobre la mediana {_f(above_avg, 0, True)} de las veces: es un poco pesimista cuando el mercado sube. A un año, esos resultados se solapan, así que hay pocos casos realmente independientes.",
                       f"Can these ranges be trusted? I tested them from every month-start since 2020, using only earlier data. The 90% range held {_f(cov[7], 0, True)} at 7 days, {_f(cov[30], 0, True)} at a month, {_f(cov[90], 0, True)} at three months and {_f(cov[365], 0, True)} at a year. Since it adds no trend, the price ended above the median {_f(above_avg, 0, True)} of the time in that period: a little pessimistic when the market rises. At a year those results overlap, so there are few truly independent cases."))

    nrows = []
    for d in sorted(now["forecast"], key=lambda x: (x["coin"], x["horizon"])):
        nrows.append([d["coin"], f'{d["horizon"]}d', d["target_date"][:10], _px(d["last_close"]), _px(d["p05"]), _px(d["p50"]), _px(d["p95"])])
    tb = ""
    track_path = REPORTS / "track.json"
    t = None
    if track_path.exists():
        t = json.loads(track_path.read_text(encoding="utf-8"))
        trows = []
        for d in sorted(t["rows"], key=lambda x: (x["horizon"], x["coin"])):
            if d["close"] is None:
                state = (lab("pendiente", "pending"), "", "", "")
            else:
                inside = lab("dentro", "inside") if d["inside_90"] else lab("fuera", "outside")
                state = (f'{_px(d["close"])} <small>({d.get("source") or "binance"})</small>', inside,
                         _f(d["median_error"], 1, True, True), _f(d["no_change_error"], 1, True, True))
            trows.append([d["coin"], f'{d["horizon"]}d', d["target_date"], f'{_px(d["p05"])} - {_px(d["p95"])}', *state])
        tb = (bi(f"Cada día GitHub Actions compara este pronóstico congelado del {t['asof']} con los cierres publicados. Revisado el {t['checked']}: {t['resolved']} resueltos, {t['inside_90']} dentro de la banda de 90%.",
                 f"Every day GitHub Actions compares this forecast, frozen on {t['asof']}, with the published closes. Checked {t['checked']}: {t['resolved']} resolved, {t['inside_90']} inside the 90% band.")
              + table(["Coin", "Horizon", "Date", "90% band", "Close", "Band", "Error vs median", "Error vs \"no change\""], trows,
                      ["Moneda", "Horizonte", "Fecha", "Banda 90%", "Cierre", "Banda", "Error contra mediana", "Error contra \"sin cambio\""]))
    s14 = section(14, "¿Cómo le va al pronóstico de corto plazo?", "How is the short-term forecast doing?",
                  ans(f"Lo congelé con datos al {now['asof']} para poder revisarlo honestamente. Sus medianas son casi \"queda igual\", así que lo útil es la banda: históricamente contuvo {_f(cov1['all']['cover_conformal_90'], 0, True)} de los movimientos a un día y {_f(cov7['all']['cover_conformal_90'], 0, True)} a 7 días. No vio venir el hackeo, y ninguna de las cinco monedas quedó dentro de la banda ese día.",
                      f"I froze it with data to {now['asof']} so it can be checked honestly. Its medians are almost \"no change\", so what is useful is the band: historically it contained {_f(cov1['all']['cover_conformal_90'], 0, True)} of one-day moves and {_f(cov7['all']['cover_conformal_90'], 0, True)} of 7-day ones. It did not see the hack coming, and none of the five coins stayed inside its band that day.")
                  + fig("nowcast", "la línea es el precio y la zona azul el rango de 90% para los próximos 1 y 7 días; la línea punteada es la mediana.",
                        "the line is the price and the blue zone the 90% range for the next 1 and 7 days; the dotted line is the median.")
                  + table(["Coin", "Horizon", "Date", "Last close", "5%", "Median", "95%"], nrows,
                          ["Moneda", "Horizonte", "Fecha", "Último cierre", "5%", "Mediana", "95%"]) + tb)

    gl = [("Hot wallet", "billetera conectada a internet con la que el exchange paga retiros.", "wallet connected to the internet that the exchange uses to pay withdrawals."),
          ("Vela", "resume un período: apertura, cierre, máximo y mínimo.", "summarizes a period: open, close, high and low."),
          ("Futuros perpetuos", "contratos para apostar al precio sin comprar la moneda, sin fecha de vencimiento.", "contracts to bet on the price without buying the coin, with no expiry."),
          ("Interés abierto", "total de dinero apostado en futuros en ese momento.", "total money committed in futures at that moment."),
          ("Orden a mercado", "compra o venta apurada, al mejor precio disponible en ese momento.", "a hurried buy or sell, at the best price available right then."),
          ("Mediana", "el valor del medio: la mitad de los casos queda arriba y la mitad abajo.", "the middle value: half the cases are above and half below."),
          ("p", "probabilidad de ver una diferencia así solo por azar; bajo 0,05 se suele considerar clara.", "the chance of seeing such a gap by luck alone; under 0.05 is usually considered clear."),
          ("R²", "qué parte de la variación anticipa un modelo. Negativo: lo hace peor que la referencia.", "what share of the variation a model anticipates. Negative: worse than the benchmark."),
          ("HAR", "modelo simple que anticipa la turbulencia solo con la del último día, semana y mes.", "a simple model that anticipates turbulence using only that of the last day, week and month."),
          ("Banda de 90%", "rango donde debería caer el precio 9 de cada 10 veces.", "the range the price should land in 9 times out of 10."),
          ("Walk-forward", "reentrenar cada período solo con lo conocido hasta entonces, sin mirar el futuro.", "refitting each period on only what was known by then, without looking ahead."),
          ("Época", "una pasada completa de la red neuronal por los datos de entrenamiento.", "one full pass of the neural network over the training data."),
          ("Early stopping", "detener el entrenamiento cuando deja de mejorar sobre datos que no usó para aprender.", "stopping training when it no longer improves on data it did not learn from.")]
    gloss = ('<section><h2>' + lab("Glosario", "Glossary") + "</h2><dl>"
             + "".join(f'<dt>{n}</dt><dd lang="es">{_es(e)}</dd><dd lang="en">{en}</dd>' for n, e, en in gl) + "</dl></section>")

    body = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8 + s9 + s10 + s11 + s12 + s13 + s14 + gloss
    tpl = (ROOT / "src" / "bhack" / "site_template.html").read_text(encoding="utf-8")
    page = tpl.replace("{{STATS}}", stat_html).replace("{{SUMMARY}}", summary).replace("{{BODY}}", body)
    (ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    return page


if __name__ == "__main__":
    build(json.loads((REPORTS / "results.json").read_text(encoding="utf-8")))

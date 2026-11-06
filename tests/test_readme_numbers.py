"""Every headline number in both READMEs must match reports/results.json."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
EN = (ROOT / "README.md").read_text(encoding="utf-8")
ES = (ROOT / "README.es.md").read_text(encoding="utf-8")


def num(x, d=1):
    return f"{x:.{d}f}"


def es(s):
    return s.replace(".", ",")


def rows(key, **match):
    return [r for r in R[key] if all(r[k] == v for k, v in match.items())]


def headline_numbers():
    dec = {(d["window"], d["coin"]): d for d in R["decomposition"]}
    d30 = {(d["window"], d["coin"]): d for d in R["decomposition_30min"]}
    btc = dec[("to_nov2_close", "BTC")]
    det = R["detector"]["2026"]
    svu = {d["window"]: d for d in R["stolen_vs_untouched"]}
    es_btc = R["event_study"]["BTC"]
    stocks = {d["stock"]: d for d in R["stocks"] if d["day"] == "2026-10-30"}
    rf = R["reserve_flows"]
    f = R["forecast"]
    y1 = {d["model"]: d for d in f["y1_scores"] if d["coin"] == "all"}
    vol = {d["model"]: d for d in f["vol_scores"] if d["coin"] == "all"}
    fan = {(d["coin"], d["horizon"]): d for d in R["scenarios"]["fan"]}
    return [
        num(-100 * btc["actual"]) + "%",
        num(-100 * btc["explained"]),
        num(100 * btc["abnormal"]),
        num(-100 * d30[("to_nov2_close", "BTC")]["explained"]),
        num(100 * dec[("before_admission", "BTC")]["abnormal"]),
        det["alarm"][11:16],
        f"{det['minutes_before_admission']:.0f}",
        R["detector"]["2019"]["alarm"][11:16],
        num(100 * svu["to_reopen"]["stolen_mean"]),
        num(100 * svu["to_reopen"]["untouched_mean"]),
        num(svu["to_reopen"]["p_perm"], 2),
        num(svu["before_admission"]["p_perm"], 2),
        num(es_btc["mean_scar_1"], 2),
        num(es_btc["p_mean_scar_1"], 2),
        num(100 * es_btc["binance_2026"]["car_1"]),
        *[("$" + num(-rf[d]["net_flow_bn"], 2) + " billion",
           f"{1000 * round(-rf[d]['net_flow_bn'], 2):,.0f}".replace(",", ".") + " millones")
          for d in ["2026-10-29", "2026-11-01", "2026-11-02"]],
        num(100 * stocks["COIN"]["abn_vs_qqq_btc"]),
        num(stocks["COIN"]["t_stat"]),
        num(100 * y1["lgb"]["r2_vs_zero"]),
        num(100 * y1["ridge"]["r2_vs_zero"]),
        num(100 * y1["mlp"]["r2_vs_zero"]),
        num(100 * vol["har"]["r2"]),
        num(100 * vol["lgb"]["r2"]),
        num(vol["lgb"]["dm_p"], 2),
        str(R["aftermath"]["year"]["worse_than_hack"]),
        num(es_btc["tail"]["p_below"], 3),
        *[(f"{fan[('BTC', h)]['p05']:,.0f} - {fan[('BTC', h)]['p95']:,.0f}",
           f"{fan[('BTC', h)]['p05']:,.0f} - {fan[('BTC', h)]['p95']:,.0f}".replace(",", "."))
          for h in (30, 365)],
    ]


@pytest.mark.parametrize("value", headline_numbers())
def test_number_in_both_readmes(value):
    en, sp = value if isinstance(value, tuple) else (value, es(value))
    assert en in EN, f"{en} missing from README.md"
    assert sp in ES, f"{sp} missing from README.es.md"

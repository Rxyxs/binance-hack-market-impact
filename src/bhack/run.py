"""End-to-end pipeline: data, analyses, models, figures, results file and the page.

    python -m bhack.run            # everything
    python -m bhack.run --no-nn    # skip the MLP (about 20 minutes faster)
"""
from __future__ import annotations

import argparse
import datetime
import json

import numpy as np
import pandas as pd

from . import (aftermath, annual, datasets, deep, detector, eventstudy, figures, forecast, intraday, nowcast,
               scenarios, snapshot)
from .config import REPORTS


def _clean(o):
    """JSON-safe: numpy scalars to Python, NaN to None, rounded floats."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, (pd.Timestamp, datetime.date)):
        return str(o)
    return o


def _records(df: pd.DataFrame) -> list[dict]:
    return _clean(df.to_dict(orient="records"))


def aftermath_results() -> dict:
    a = aftermath.run()
    return _clean({k: _records(a[k].assign(date=a[k]["date"].astype(str))) if k == "days" else _records(a[k])
                   for k in ["horizons", "recovery_hacks", "coins", "volatility", "days"]})


def scenario_results() -> dict:
    a = scenarios.run()
    return {k: _records(a[k]) for k in ["fan", "backtest"]}


def main(with_nn: bool = True) -> dict:
    datasets.build_all()

    ann = annual.run()
    es = eventstudy.run()
    intr = intraday.run()
    det = detector.run()
    fc = forecast.run(with_nn=with_nn)
    now = nowcast.run()

    w = intraday.closes()
    flows = intraday.reserve_flows()
    results = {
        "trend_before_hack": ann["trend"],
        "coin_years": _records(ann["coin_years"]),
        "hacks_by_year": _records(ann["hacks_by_year"]),
        "event_study": {c: {k: v for k, v in d.items() if k != "table"} | {"table": _records(d["table"])}
                        for c, d in es.items()},
        "paths": _clean((intr["paths"]).to_dict(orient="index")),
        "abnormal_vs_btc": _records(intr["abnormal"]),
        "abnormal_group_means": _clean(intr["abnormal"].query("coin != 'BTC'")
                                       .groupby(["window", "group"])["abn"].mean()
                                       .unstack().to_dict(orient="index")),
        "stolen_vs_untouched": _records(intraday.stolen_vs_untouched(intr["abnormal"])),
        "overhang": _clean(intr["overhang"].to_dict(orient="index")),
        "macro_fits": _clean(intr["macro"]["fits"]),
        "decomposition": _records(intr["macro"]["decomposition"]),
        "decomposition_30min": _records(intraday.btc_vs_futures(w, "30min")["decomposition"]),
        "flow": _records(intr["flow"]),
        "flow_size": _records(intr["flow_size"]),
        "open_interest": _records(intr["oi"]),
        "venue_gaps": _records(intr["gaps"]),
        "stocks": _records(intr["stocks"]),
        "reserves": _clean({str(k.date()): v for k, v in intr["reserves"]["binance_assets_usd"].items()}),
        "reserve_flows": _clean({str((k - pd.Timedelta(days=1)).date()): v
                                 for k, v in flows.to_dict(orient="index").items()}),
        "detector": {k: {kk: vv for kk, vv in v.items() if kk != "z_trace"} for k, v in det.items()},
        "forecast": {k: _records(fc[k]) for k in ["y1_scores", "y7_scores", "vol_scores", "y1_coverage",
                                                  "y7_coverage", "strategy", "ablation"] if k in fc},
        "mlp_best_epochs": _clean(fc["y1"]["mlp_best_epoch"].describe().to_dict()) if "mlp_best_epoch" in fc["y1"] else None,
        "hack_week_forecasts": _records(fc["y1"][(fc["y1"].date >= "2026-10-26")]
                                        [["date", "coin", "y", "lgb", "q05", "q50", "q95", "cq05", "cq95"]]
                                        .assign(date=lambda d: d.date.astype(str))),
        "nowcast": {"asof": now["asof"], "trained_through": now["trained_through"],
                    "forecast": _records(now["forecast"].assign(target_date=lambda d: d.target_date.astype(str))),
                    "vol": _records(now["vol"]),
                    "vol_drivers": _clean(now["vol_drivers"].to_dict(orient="index"))},
    }
    results["gru"] = deep.summary()
    results["aftermath"] = aftermath_results()
    results["scenarios"] = scenario_results()
    results = _clean(results)
    (REPORTS / "results.json").write_text(json.dumps(results, indent=1, allow_nan=False), encoding="utf-8")

    figures.render_all(results)

    from . import site
    site.build(results)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-nn", action="store_true")
    args = p.parse_args()
    snapshot.yahoo_minutes()
    main(with_nn=not args.no_nn)

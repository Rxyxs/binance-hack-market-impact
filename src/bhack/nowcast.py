"""Today's forecast: the same models, refitted on every resolved row, applied to the last day.

Prices come out as a median and a 90% band (quantile LightGBM widened by split conformal
on the validation slice, exactly as in the walk-forward that measured its coverage).
The volatility model's prediction is split into feature-group contributions (TreeSHAP),
which says what is pushing expected turbulence up or down right now.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import features
from .features import FEATURES, GROUPS, TARGET_COINS
from .forecast import design, fit_lgb, target


def _fit_band(panel, name, X_all, y_all, last_date):
    known = panel["date"] + pd.Timedelta(days=1 if name == "y1" else 7) <= last_date
    tr = panel[known & y_all.notna()]
    cut = tr["date"].quantile(0.85)
    a, b = tr[tr.date <= cut].index, tr[tr.date > cut].index
    models, early = {}, {}
    for q in (0.05, 0.5, 0.95):
        models[q], early[q] = fit_lgb(X_all.loc[a], y_all.loc[a], X_all.loc[b], y_all.loc[b],
                                      "quantile", q, return_early=True)
    yb = y_all.loc[b]
    score = np.maximum(early[0.05].predict(X_all.loc[b]) - yb, yb - early[0.95].predict(X_all.loc[b]))
    adj = np.quantile(score, min(np.ceil((len(score) + 1) * 0.9) / len(score), 1.0))
    return models, adj, tr["date"].max()


def run() -> dict:
    panel = features.build()
    last_date = panel["date"].max()
    X_all = design(panel, FEATURES)
    now = panel[panel.date == last_date]
    rows = []
    trained_through = {}
    for name, h in [("y1", 1), ("y7", 7)]:
        y_all = target(panel, name)
        models, adj, through = _fit_band(panel, name, X_all, y_all, last_date)
        trained_through[name] = str(through.date())
        Xn = X_all.loc[now.index]
        q05 = models[0.05].predict(Xn) - adj
        q50 = models[0.5].predict(Xn)
        q95 = models[0.95].predict(Xn) + adj
        for i, (_, r) in enumerate(now.iterrows()):
            p = r["close"]
            rows.append({"coin": r["coin"], "horizon": h, "asof": str(last_date.date()),
                         "target_date": last_date + pd.Timedelta(days=h), "last_close": p,
                         "p05": p * np.exp(q05[i]), "p50": p * np.exp(q50[i]), "p95": p * np.exp(q95[i]),
                         "ret_p05": np.exp(q05[i]) - 1, "ret_p50": np.exp(q50[i]) - 1,
                         "ret_p95": np.exp(q95[i]) - 1})
    fc = pd.DataFrame(rows)

    # expected volatility and what drives it
    y_all = target(panel, "rv7_fwd")
    known = panel["date"] + pd.Timedelta(days=7) <= last_date
    tr = panel[known & y_all.notna()]
    cut = tr["date"].quantile(0.85)
    a, b = tr[tr.date <= cut].index, tr[tr.date > cut].index
    vm = fit_lgb(X_all.loc[a], y_all.loc[a], X_all.loc[b], y_all.loc[b])
    Xn = X_all.loc[now.index]
    contrib = pd.DataFrame(vm.predict(Xn, pred_contrib=True), index=now["coin"].values,
                           columns=list(Xn.columns) + ["bias"])
    by_group = pd.DataFrame({g: contrib[[c for c in cols if c in contrib]].sum(axis=1)
                             for g, cols in GROUPS.items()})
    by_group["coin_dummies"] = contrib[[c for c in contrib if c.startswith("is_")]].sum(axis=1)
    pred = vm.predict(Xn)
    vol = pd.DataFrame({"coin": now["coin"].values,
                        "daily_vol_next7": np.exp(pred),
                        "annualized": np.exp(pred) * np.sqrt(365),
                        "trailing_30d_daily_vol": now["rv30"].values})
    hist = {c: panel[panel.coin == c].set_index("date")["close"] for c in TARGET_COINS}
    return {"forecast": fc, "vol": vol, "vol_drivers": by_group, "asof": str(last_date.date()),
            "trained_through": trained_through, "history": hist}


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    r = run()
    print(r["asof"], r["trained_through"])
    print(r["forecast"].round(4).to_string())
    print(r["vol"].round(4).to_string())
    print(r["vol_drivers"].round(4).to_string())

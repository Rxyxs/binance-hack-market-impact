"""Walk-forward forecasts of next-day return, 7-day return and 7-day volatility.

Every month from 2022 on, each model is refitted on everything that was known at the
start of that month and predicts that month. Rows whose target overlaps the test month
are dropped from training (a 7-day target needs 7 days to resolve). Early stopping and
the ridge penalty are chosen on the last 15% of the training window, never on the test.
"""
from __future__ import annotations

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import features
from .config import WORK
from .features import FEATURES, GROUPS, TARGET_COINS

warnings.filterwarnings("ignore", category=UserWarning)
TEST_START = pd.Timestamp("2022-01-01")
HORIZON = {"y1": 1, "y7": 7, "rv7_fwd": 7}
QUANTILES = (0.05, 0.5, 0.95)
LGB_PARAMS = dict(n_estimators=3000, learning_rate=0.02, num_leaves=15, min_child_samples=100,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0,
                  verbose=-1, n_jobs=4)


def design(panel: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    X = panel[cols].copy()
    for c in TARGET_COINS[1:]:
        X[f"is_{c}"] = (panel["coin"] == c).astype(float)
    return X


def target(panel: pd.DataFrame, name: str) -> pd.Series:
    if name == "rv7_fwd":  # volatility is modelled in logs; its errors are multiplicative
        return np.log(panel[name].clip(lower=1e-4))
    return panel[name]


def split(panel: pd.DataFrame, name: str, month: pd.Timestamp):
    h = HORIZON[name]
    known = panel["date"] + pd.Timedelta(days=h) < month
    tr = panel[known & target(panel, name).notna()]
    cut = tr["date"].quantile(0.85)
    return tr[tr.date <= cut], tr[tr.date > cut]


def fit_lgb(Xtr, ytr, Xva, yva, objective="regression", alpha=None, return_early=False):
    """Pick the number of trees on the validation slice, then refit on train + validation."""
    params = dict(LGB_PARAMS, objective=objective)
    if alpha is not None:
        params["alpha"] = alpha
    m = lgb.LGBMRegressor(**params)
    m.fit(Xtr, ytr, eval_set=[(Xva, yva)], callbacks=[lgb.early_stopping(100, verbose=False)])
    best = max(m.best_iteration_ or 50, 50)
    final = lgb.LGBMRegressor(**dict(params, n_estimators=best))
    final.fit(pd.concat([Xtr, Xva]), pd.concat([ytr, yva]))
    return (final, m) if return_early else final


def fit_ridge(Xtr, ytr, Xva, yva):
    best, best_loss = None, np.inf
    for a in (1, 10, 100, 1000, 10000):
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=a))
        m.fit(Xtr, ytr)
        loss = np.mean((yva - m.predict(Xva)) ** 2)
        if loss < best_loss:
            best, best_loss = a, loss
    m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=best))
    return m.fit(pd.concat([Xtr, Xva]), pd.concat([ytr, yva]))


def _har_x(rows: pd.DataFrame) -> np.ndarray:
    return np.column_stack([np.ones(len(rows)),
                            np.log(rows["r1"].abs().clip(lower=1e-4)),
                            np.log(rows["rv7"].clip(lower=1e-4)),
                            np.log(rows["rv30"].clip(lower=1e-4))])


def fit_har(panel: pd.DataFrame, y: pd.Series, te: pd.DataFrame) -> np.ndarray:
    """HAR benchmark for volatility: log of daily, weekly and monthly realized volatility."""
    tr = panel.loc[y.index]
    ok = tr[["r1", "rv7", "rv30"]].notna().all(axis=1).values
    coef, *_ = np.linalg.lstsq(_har_x(tr)[ok], y.values[ok], rcond=None)
    xt = _har_x(te.fillna({"r1": 0.0}))
    return xt @ coef


def walk_forward(panel: pd.DataFrame, name: str, cols: list[str] = FEATURES,
                 models=("lgb", "ridge"), quantiles: bool = False, step: str = "MS",
                 nn: bool = False) -> pd.DataFrame:
    months = pd.date_range(TEST_START, panel["date"].max(), freq=step)
    out, mlp = [], None
    X_all = design(panel, cols)
    y_all = target(panel, name)
    for i, month in enumerate(months):
        nxt = months[i + 1] if i + 1 < len(months) else panel["date"].max() + pd.Timedelta(days=1)
        te = panel[(panel.date >= month) & (panel.date < nxt)]
        if te.empty:
            continue
        tr, va = split(panel, name, month)
        Xtr, Xva, Xte = X_all.loc[tr.index], X_all.loc[va.index], X_all.loc[te.index]
        ytr, yva = y_all.loc[tr.index], y_all.loc[va.index]
        res = te[["date", "coin"]].copy()
        res["y"] = y_all.loc[te.index]
        if name == "rv7_fwd":
            res["base_persist"] = np.log(panel.loc[te.index, "rv30"].clip(lower=1e-4))
            res["base_mean"] = ytr.mean()
            res["har"] = fit_har(panel, pd.concat([ytr, yva]), te)
        else:
            res["base_zero"] = 0.0
            res["base_mean"] = pd.concat([ytr, yva]).mean()
        if "lgb" in models:
            res["lgb"] = fit_lgb(Xtr, ytr, Xva, yva).predict(Xte)
        if "ridge" in models:
            res["ridge"] = fit_ridge(Xtr, ytr, Xva, yva).predict(Xte)
        if quantiles:
            early = {}
            for q in QUANTILES:
                final, early[q] = fit_lgb(Xtr, ytr, Xva, yva, "quantile", q, return_early=True)
                res[f"q{int(q * 100):02d}"] = final.predict(Xte)
            # split-conformal widening of the 5-95 band: scores from the models that did not
            # train on the validation slice
            score = np.maximum(early[0.05].predict(Xva) - yva, yva - early[0.95].predict(Xva))
            k = np.ceil((len(score) + 1) * 0.9) / len(score)
            adj = np.quantile(score, min(k, 1.0))
            res["cq05"], res["cq95"] = res["q05"] - adj, res["q95"] + adj
        if nn:  # the network is refitted every quarter; it is the slowest model by far
            from .nn import fit_mlp
            if mlp is None or month.month % 3 == 1:
                mlp = fit_mlp(Xtr, ytr, Xva, yva)
            res["mlp"] = mlp.predict(Xte)
            res["mlp_best_epoch"] = mlp.best_epoch
        out.append(res)
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------------- scoring

def dm_test(e1: np.ndarray, e2: np.ndarray, h: int = 1) -> tuple[float, float]:
    """Diebold-Mariano on squared errors with a Newey-West variance (lag h-1)."""
    d = e1 ** 2 - e2 ** 2
    n = len(d)
    dbar = d.mean()
    gamma = [np.mean((d[k:] - dbar) * (d[:n - k] - dbar)) for k in range(h)]
    var = gamma[0] + 2 * sum((1 - k / h) * g for k, g in enumerate(gamma[1:], start=1))
    stat = dbar / np.sqrt(var / n)
    return float(stat), float(2 * (1 - stats.norm.cdf(abs(stat))))


def score_returns(res: pd.DataFrame, h: int, models=("lgb", "ridge", "mlp")) -> pd.DataFrame:
    rows = []
    r = res.dropna(subset=["y"])
    for coin, g in [("all", r)] + list(r.groupby("coin")):
        y = g["y"].values
        for m in ("base_mean",) + tuple(x for x in models if x in g):
            p = g[m].values
            dm, pv = dm_test(y - p, y - 0.0, h)
            hit = np.mean(np.sign(p) == np.sign(y))
            up = np.mean(y > 0)
            rows.append({"coin": coin, "model": m, "n": len(y),
                         "r2_vs_zero": 1 - np.sum((y - p) ** 2) / np.sum(y ** 2),
                         "hit_rate": hit, "share_up_days": up,
                         "dm_stat_vs_zero": dm, "dm_p": pv})
    return pd.DataFrame(rows)


def score_vol(res: pd.DataFrame, models=("lgb", "ridge", "mlp")) -> pd.DataFrame:
    rows = []
    r = res.dropna(subset=["y"])
    for coin, g in [("all", r)] + list(r.groupby("coin")):
        y = g["y"].values
        base = g["har"].values
        for m in ("base_persist", "base_mean", "har") + tuple(x for x in models if x in g):
            p = g[m].values
            dm, pv = dm_test(y - p, y - base, 7)
            # QLIKE on variances: robust to noise in the realized proxy
            v, vh = np.exp(2 * y), np.exp(2 * p)
            rows.append({"coin": coin, "model": m, "n": len(y),
                         "r2": 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2),
                         "r2_vs_har": 1 - np.sum((y - p) ** 2) / np.sum((y - base) ** 2),
                         "qlike": float(np.mean(v / vh - np.log(v / vh) - 1)),
                         "dm_stat_vs_har": dm, "dm_p": pv})
    return pd.DataFrame(rows)


def coverage(res: pd.DataFrame) -> pd.DataFrame:
    r = res.dropna(subset=["y"])
    rows = []
    for coin, g in [("all", r)] + list(r.groupby("coin")):
        rows.append({"coin": coin,
                     "cover_raw_90": np.mean((g.y >= g.q05) & (g.y <= g.q95)),
                     "cover_conformal_90": np.mean((g.y >= g.cq05) & (g.y <= g.cq95)),
                     "width_conformal": np.mean(g.cq95 - g.cq05),
                     "pinball_50": np.mean(np.maximum(0.5 * (g.y - g.q50), -0.5 * (g.y - g.q50)))})
    return pd.DataFrame(rows)


def strategy(res: pd.DataFrame, model: str = "lgb", cost_bp: float = 10) -> pd.DataFrame:
    """Long when the next-day forecast is positive, flat otherwise; cost on every switch."""
    rows = []
    for coin, g in res.dropna(subset=["y"]).groupby("coin"):
        g = g.sort_values("date")
        pos = (g[model] > 0).astype(float).values
        cost = np.abs(np.diff(np.r_[0, pos])) * cost_bp / 1e4
        strat = pos * g["y"].values - cost
        bh = g["y"].values

        def sharpe(x):
            return float(np.mean(x) / np.std(x) * np.sqrt(365)) if np.std(x) > 0 else 0.0

        rows.append({"coin": coin, "days": len(g), "time_in_market": pos.mean(),
                     "strategy_total": float(np.exp(strat.sum()) - 1), "hold_total": float(np.exp(bh.sum()) - 1),
                     "strategy_sharpe": sharpe(strat), "hold_sharpe": sharpe(bh)})
    return pd.DataFrame(rows)


def ablation(panel: pd.DataFrame, name: str) -> pd.DataFrame:
    """Refit quarterly without each feature group and with price alone plus each group."""
    def loss(res):
        r = res.dropna(subset=["y"])
        return float(np.mean((r.y - r.lgb) ** 2))

    full = loss(walk_forward(panel, name, FEATURES, models=("lgb",), step="QS"))
    base_cols = GROUPS["price_volume"] + GROUPS["calendar"]
    base = loss(walk_forward(panel, name, base_cols, models=("lgb",), step="QS"))
    rows = [{"group": "all", "drop_group_mse_change": 0.0, "add_to_price_mse_change": full / base - 1}]
    for g, cols in GROUPS.items():
        if g in ("price_volume", "calendar"):
            continue
        keep = [c for c in FEATURES if c not in cols]
        dropped = loss(walk_forward(panel, name, keep, models=("lgb",), step="QS"))
        added = loss(walk_forward(panel, name, base_cols + cols, models=("lgb",), step="QS"))
        rows.append({"group": g, "drop_group_mse_change": dropped / full - 1,
                     "add_to_price_mse_change": added / base - 1})
    return pd.DataFrame(rows).assign(target=name, mse_full=full, mse_price_only=base)


def cached(name: str, fn):
    path = WORK / f"wf_{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = fn()
    df.to_parquet(path, index=False)
    return df


def run(with_nn: bool = True, with_ablation: bool = True) -> dict:
    panel = features.build()
    y1 = cached("y1", lambda: walk_forward(panel, "y1", quantiles=True, nn=with_nn))
    y7 = cached("y7", lambda: walk_forward(panel, "y7", quantiles=True))
    vol = cached("vol", lambda: walk_forward(panel, "rv7_fwd", nn=with_nn))
    out = {
        "y1_scores": score_returns(y1, 1), "y7_scores": score_returns(y7, 7),
        "vol_scores": score_vol(vol), "y1_coverage": coverage(y1), "y7_coverage": coverage(y7),
        "strategy": strategy(y1), "y1": y1, "y7": y7, "vol": vol,
    }
    if with_ablation:
        out["ablation"] = cached("ablation", lambda: pd.concat(
            [ablation(panel, "y1"), ablation(panel, "rv7_fwd")], ignore_index=True))
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    res = run()
    for k in ["y1_scores", "y7_scores", "vol_scores", "y1_coverage", "y7_coverage", "strategy",
              "ablation"]:
        if k in res:
            print("=" * 10, k)
            print(res[k].round(4).to_string())

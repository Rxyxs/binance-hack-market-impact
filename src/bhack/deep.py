"""Sequence model for the same walk-forward: a GRU over the last 20 days.

Every refit trains at least 100 epochs. From epoch 100 on, early stopping watches the
validation slice and the weights kept are the best validation checkpoint among those
epochs. For volatility the network learns a correction to the HAR benchmark.

    python -m bhack.deep y1|y7|rv7_fwd
"""
from __future__ import annotations

import copy
import sys

import numpy as np
import pandas as pd
import torch
from torch import nn

from . import features
from .config import WORK
from .features import GROUPS, TARGET_COINS
from .forecast import TEST_START, dm_test, fit_har, split, target

MIN_EPOCHS, MAX_EPOCHS, PATIENCE = 100, 300, 20
WINDOW = 20
CLIP = 10.0
COLS = GROUPS["price_volume"] + GROUPS["derivatives"]


class GRUNet(nn.Module):
    def __init__(self, n_in: int, hidden: int = 32, dropout: float = 0.3):
        super().__init__()
        self.gru = nn.GRU(n_in, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden, 1))

    def forward(self, x):
        return self.head(self.gru(x)[0][:, -1])


def _matrix(panel: pd.DataFrame, cols: list[str]) -> np.ndarray:
    X = panel[cols].astype(float).copy()
    for c in TARGET_COINS[1:]:
        X[f"is_{c}"] = (panel["coin"] == c).astype(float)
    return X.values.astype(np.float32)


def _windows(panel: pd.DataFrame, a: np.ndarray, rows: pd.Index, med, mu, sd) -> torch.Tensor:
    """Tensor (rows, WINDOW, features). Only each row and its own coin's past enter it."""
    z = np.clip((np.where(np.isnan(a), med, a) - mu) / sd, -CLIP, CLIP).astype(np.float32)
    out = np.zeros((len(rows), WINDOW, z.shape[1]), dtype=np.float32)
    by_coin = {c: g.sort_values("date").index.values for c, g in panel.groupby("coin")}
    pos = {c: {r: i for i, r in enumerate(v)} for c, v in by_coin.items()}
    coins = panel.loc[rows, "coin"].values
    for k, (r, c) in enumerate(zip(rows, coins)):
        i = pos[c][r]
        idx = by_coin[c][max(0, i - WINDOW + 1): i + 1]
        out[k, -len(idx):] = z[idx]
    return torch.from_numpy(out)


def fit_gru(xt, yt, xv, yv, huber: bool, seed: int = 0):
    """Returns (net, best_epoch, epochs_run); the checkpoint is chosen from epoch 100 on."""
    torch.manual_seed(seed)
    net = GRUNet(xt.shape[2])
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=10, min_lr=2e-5)
    loss_fn = nn.HuberLoss() if huber else nn.MSELoss()
    best, state, best_epoch, wait, epoch = np.inf, None, 0, 0, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        net.train()
        perm = torch.randperm(len(xt))
        for i in range(0, len(xt), 512):
            b = perm[i:i + 512]
            opt.zero_grad()
            loss_fn(net(xt[b]), yt[b]).backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        net.eval()
        with torch.no_grad():
            v = loss_fn(net(xv), yv).item()
        sched.step(v)
        if epoch < MIN_EPOCHS:
            continue
        if v < best:
            best, state, best_epoch, wait = v, copy.deepcopy(net.state_dict()), epoch, 0
        else:
            wait += 1
            if wait >= PATIENCE:
                break
    net.load_state_dict(state)
    net.eval()
    return net, best_epoch, epoch


def walk_forward(panel: pd.DataFrame, name: str, start=TEST_START) -> pd.DataFrame:
    a = _matrix(panel, COLS)
    y_all = target(panel, name)
    quarters = pd.date_range(start.to_period("Q").start_time, panel["date"].max(), freq="QS")
    out = []
    for i, q in enumerate(quarters):
        nxt = quarters[i + 1] if i + 1 < len(quarters) else panel["date"].max() + pd.Timedelta(days=1)
        te = panel[(panel.date >= max(q, start)) & (panel.date < nxt)]
        tr, va = split(panel, name, q)
        ytr, yva = y_all.loc[tr.index], y_all.loc[va.index]
        base_te = np.zeros(len(te))
        base_tr, base_va = np.zeros(len(tr)), np.zeros(len(va))
        if name == "rv7_fwd":  # learn the correction to HAR, fitted on training rows only
            base_tr = fit_har(panel, ytr, tr.fillna({"r1": 0.0}))
            base_va = fit_har(panel, ytr, va.fillna({"r1": 0.0}))
            base_te = fit_har(panel, ytr, te.fillna({"r1": 0.0}))
        rtr, rva = ytr.values - base_tr, yva.values - base_va
        ok = np.isfinite(rtr)
        rmu, rsd = float(rtr[ok].mean()), float(rtr[ok].std())
        at = a[panel.index.get_indexer(tr.index)]
        med = np.nan_to_num(np.nanmedian(at, axis=0))
        filled = np.where(np.isnan(at), med, at)
        mu, sd = filled.mean(0), filled.std(0)
        sd = np.where(sd < 1e-8, 1.0, sd)
        xt = _windows(panel, a, tr.index[ok], med, mu, sd)
        okv = np.isfinite(rva)
        xv = _windows(panel, a, va.index[okv], med, mu, sd)
        yt = torch.tensor((rtr[ok] - rmu) / rsd, dtype=torch.float32).unsqueeze(1)
        yv = torch.tensor((rva[okv] - rmu) / rsd, dtype=torch.float32).unsqueeze(1)
        net, best_epoch, run = fit_gru(xt, yt, xv, yv, huber=name != "rv7_fwd")
        with torch.no_grad():
            p = net(_windows(panel, a, te.index, med, mu, sd)).numpy().ravel() * rsd + rmu
        res = te[["date", "coin"]].copy()
        res["y"] = y_all.loc[te.index]
        res["gru"] = p + base_te
        res["best_epoch"], res["epochs_run"] = best_epoch, run
        out.append(res)
        print(q.date(), "best", best_epoch, "ran", run, flush=True)
    return pd.concat(out, ignore_index=True)


def cached(panel: pd.DataFrame, name: str) -> pd.DataFrame:
    path = WORK / f"wf_gru_{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = walk_forward(panel, name)
    df.to_parquet(path, index=False)
    return df


def summary() -> dict:
    """Scores on the rows shared with the monthly walk-forward of forecast.py."""
    panel = features.build()
    out = {}
    for name, base in [("y1", "wf_y1"), ("y7", "wf_y7")]:
        m = pd.read_parquet(WORK / f"{base}.parquet").merge(
            cached(panel, name)[["date", "coin", "gru", "best_epoch", "epochs_run"]],
            on=["date", "coin"]).dropna(subset=["y"])
        y = m["y"].values
        out[name] = {"n": len(m),
                     "r2_vs_zero": float(1 - ((y - m["gru"]) ** 2).sum() / (y ** 2).sum()),
                     "r2_lgb": float(1 - ((y - m["lgb"]) ** 2).sum() / (y ** 2).sum()),
                     "hit_rate": float((np.sign(m["gru"]) == np.sign(y)).mean()),
                     "best_epoch_min": int(m["best_epoch"].min()),
                     "best_epoch_median": float(m["best_epoch"].median()),
                     "best_epoch_max": int(m["best_epoch"].max())}
    m = pd.read_parquet(WORK / "wf_vol.parquet").merge(
        cached(panel, "rv7_fwd")[["date", "coin", "gru", "best_epoch"]],
        on=["date", "coin"]).dropna(subset=["y"]).sort_values(["date", "coin"])
    y = m["y"].values
    stat, pv = dm_test(y - m["gru"].values, y - m["har"].values, 7)
    out["vol"] = {"n": len(m), "r2": float(1 - ((y - m["gru"]) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
                  "r2_har": float(1 - ((y - m["har"]) ** 2).sum() / ((y - y.mean()) ** 2).sum()),
                  "r2_vs_har": float(1 - ((y - m["gru"]) ** 2).sum() / ((y - m["har"]) ** 2).sum()),
                  "dm_p": pv, "best_epoch_median": float(m["best_epoch"].median()),
                  "best_epoch_max": int(m["best_epoch"].max())}
    return out


if __name__ == "__main__":
    tgt = sys.argv[1]
    torch.set_num_threads(5)
    panel = features.build()
    if len(sys.argv) > 2:  # smoke run from a given date, not cached
        print(walk_forward(panel, tgt, pd.Timestamp(sys.argv[2])).tail(3))
    else:
        walk_forward(panel, tgt).to_parquet(WORK / f"wf_gru_{tgt}.parquet", index=False)

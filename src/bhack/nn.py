"""Small MLP for the same walk-forward. At least 100 epochs, then early stopping on the
validation slice; the weights kept are the best validation checkpoint, not the last epoch."""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import torch
from torch import nn

MIN_EPOCHS, MAX_EPOCHS, PATIENCE = 100, 400, 30
CLIP = 10.0  # standardized inputs beyond +-10 sd are clipped


class MLPModel:
    def __init__(self, net, med, mu, sd, ymu, ysd, best_epoch, epochs_run):
        self.net, self.med, self.mu, self.sd = net, med, mu, sd
        self.ymu, self.ysd = ymu, ysd
        self.best_epoch, self.epochs_run = best_epoch, epochs_run

    def _x(self, X: pd.DataFrame) -> torch.Tensor:
        a = X.fillna(self.med).values.astype(np.float32)
        return torch.from_numpy(np.clip((a - self.mu) / self.sd, -CLIP, CLIP).astype(np.float32))

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            return self.net(self._x(X)).numpy().ravel() * self.ysd + self.ymu


def fit_mlp(Xtr, ytr, Xva, yva, seed: int = 0, hidden=(64, 32), dropout=0.2) -> MLPModel:
    torch.manual_seed(seed)
    np.random.seed(seed)
    med = Xtr.median().fillna(0.0)  # a column with no history at all (e.g. a 3-year FRED series)
    a = Xtr.fillna(med).values.astype(np.float32)
    mu, sd = a.mean(0), a.std(0)
    # a column that is constant in training (no history yet) would be divided by ~0 and
    # explode once it starts moving in the test month; give it unit scale instead
    sd = np.where(sd < 1e-8, 1.0, sd).astype(np.float32)
    ymu, ysd = float(ytr.mean()), float(ytr.std())

    def scale(df):
        z = (df.fillna(med).values.astype(np.float32) - mu) / sd
        return torch.from_numpy(np.clip(z, -CLIP, CLIP).astype(np.float32))

    xt = scale(Xtr)
    yt = torch.from_numpy(((ytr.values - ymu) / ysd).astype(np.float32)).unsqueeze(1)
    xv = scale(Xva)
    yv = torch.from_numpy(((yva.values - ymu) / ysd).astype(np.float32)).unsqueeze(1)

    layers, d = [], xt.shape[1]
    for h in hidden:
        layers += [nn.Linear(d, h), nn.GELU(), nn.Dropout(dropout)]
        d = h
    net = nn.Sequential(*layers, nn.Linear(d, 1))
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-3)
    loss_fn = nn.MSELoss()

    best, best_state, best_epoch, wait, epoch = np.inf, None, 0, 0, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        net.train()
        perm = torch.randperm(len(xt))
        for i in range(0, len(xt), 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss_fn(net(xt[idx]), yt[idx]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            v = loss_fn(net(xv), yv).item()
        if v < best:
            best, best_state, best_epoch, wait = v, copy.deepcopy(net.state_dict()), epoch, 0
        else:
            wait += 1
        if epoch >= MIN_EPOCHS and wait >= PATIENCE:
            break
    net.load_state_dict(best_state)
    return MLPModel(net, med, mu, sd, ymu, ysd, best_epoch, epoch)

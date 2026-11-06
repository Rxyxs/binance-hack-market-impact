"""Offline tests of the logic every result depends on. No network, no downloaded data."""
import numpy as np
import pandas as pd
import pytest

from bhack import detector, eventstudy, features, forecast, sources
from bhack.annual import _max_drawdown


def test_binance_timestamps_ms_and_us():
    # Binance spot files switched from milliseconds to microseconds on 2025-01-01
    ms = pd.Series([1704067200000])          # 2024-01-01 00:00 UTC
    us = pd.Series([1793232000000000])       # 2026-10-29 00:00 UTC
    assert sources._to_utc(ms).iloc[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert sources._to_utc(us).iloc[0] == pd.Timestamp("2026-10-29", tz="UTC")


def test_months_iterates_calendar_months():
    from datetime import date
    got = list(sources._months(date(2025, 11, 15), date(2026, 2, 1)))
    assert got == [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1)]


def _series(n=400, seed=0, shock_at=300, shock=0.0):
    rng = np.random.default_rng(seed)
    r = pd.Series(rng.normal(0.001, 0.02, n), index=pd.date_range("2020-01-01", periods=n))
    r.iloc[shock_at] += shock
    return r


def test_standardized_car_recovers_a_planted_shock():
    r = _series(shock=-0.20)
    s = eventstudy.standardized(r, r.index[300])
    assert s["car_0"] == pytest.approx(r.iloc[300] - r.iloc[205:295].mean())
    assert s["scar_0"] < -6  # a 10-sigma drop stands out over that day's own noise


def test_standardized_leaves_unavailable_horizons_nan():
    r = _series()
    s = eventstudy.standardized(r, r.index[-3])  # only days 0, +1, +2 exist
    assert np.isfinite(s["car_1"]) and np.isnan(s["car_5"]) and np.isnan(s["car_10"])


def test_detector_merges_hits_into_episodes():
    idx = pd.date_range("2026-01-01", periods=300, freq="min", tz="UTC")
    z = pd.Series(0.0, index=idx)
    z.iloc[[10, 11, 12, 40, 200]] = -9  # 10-40 are one episode (gap < 60 min); 200 is another
    assert detector.episodes(z, 5) == [idx[10], idx[200]]


def test_detector_threshold_respects_alarm_budget():
    idx = pd.date_range("2026-01-01", periods=60 * 24 * 60, freq="min", tz="UTC")  # 60 days
    rng = np.random.default_rng(1)
    z = pd.Series(rng.standard_t(3, len(idx)), index=idx)
    k = detector.calibrate(z)
    assert len(detector.episodes(z, k)) <= 2


def test_dm_test_sign():
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, 2000)
    good, bad = y - (y + rng.normal(0, 0.1, 2000)), y - (y + rng.normal(0, 1.0, 2000))
    stat, p = forecast.dm_test(good, bad)
    assert stat < 0 and p < 0.01


def test_walk_forward_split_never_trains_on_unresolved_targets():
    dates = pd.date_range("2021-06-01", "2022-03-31")
    panel = pd.DataFrame({"date": dates.repeat(2), "coin": ["BTC", "ETH"] * len(dates)})
    panel["y7"] = 0.0
    month = pd.Timestamp("2022-02-01")
    tr, va = forecast.split(panel, "y7", month)
    last = pd.concat([tr, va])["date"].max()
    assert last + pd.Timedelta(days=7) < month


def test_hack_block_is_lagged_one_day(monkeypatch):
    fake = pd.DataFrame({"date": pd.to_datetime(["2026-09-24", "2026-10-29"]),
                         "amount": [387.5e6, 6.36e9], "targetType": ["CEX", "CEX"]})
    monkeypatch.setattr(features.datasets, "hacks", lambda: fake)
    idx = pd.date_range("2026-10-25", "2026-11-02")
    blk = features.hack_block(idx)
    # the $6.36B hack is dated 2026-10-29; it may only appear from the 30th
    assert blk.loc["2026-10-29", "hack_usd_7"] < np.log1p(6e9)
    assert blk.loc["2026-10-30", "hack_usd_7"] > np.log1p(6e9)


def test_lag_carries_weekend_values_and_shifts():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-10-30", "2026-11-02"]))  # Fri, Mon
    idx = pd.date_range("2026-10-30", "2026-11-03")
    out = features._lag(s, idx, 1)
    assert np.isnan(out.iloc[0])
    assert list(out.iloc[1:]) == [1.0, 1.0, 1.0, 2.0]


def test_max_drawdown():
    assert _max_drawdown(pd.Series([1, 2, 1, 3, 1.5])) == pytest.approx(-0.5)


def test_mlp_trains_at_least_100_epochs_and_keeps_best_checkpoint():
    from bhack.nn import MIN_EPOCHS, fit_mlp
    rng = np.random.default_rng(3)
    X = pd.DataFrame(rng.normal(size=(600, 4)), columns=list("abcd"))
    X.loc[::7, "c"] = np.nan  # imputation path
    X["empty"] = np.nan       # a feature with no history at all
    y = pd.Series(2 * X["a"].fillna(0) - X["b"] + rng.normal(0, 0.1, 600))
    m = fit_mlp(X[:450], y[:450], X[450:], y[450:])
    assert m.epochs_run >= MIN_EPOCHS and 1 <= m.best_epoch <= m.epochs_run
    pred = m.predict(X[450:])
    assert np.isfinite(pred).all() and np.corrcoef(pred, y[450:])[0, 1] > 0.9


def test_mlp_survives_a_feature_that_is_constant_in_training():
    # Binance reserve growth is a constant 0 before DefiLlama tracks Binance, then moves
    from bhack.nn import fit_mlp
    rng = np.random.default_rng(4)
    X = pd.DataFrame({"a": rng.normal(size=500), "late": 0.0})
    y = pd.Series(X["a"] + rng.normal(0, 0.1, 500))
    m = fit_mlp(X[:300], y[:300], X[300:400], y[300:400])
    Xt = X[400:].assign(late=rng.normal(0, 0.05, 100))
    assert np.abs(m.predict(Xt)).max() < 50


def test_track_scores_only_resolved_days(tmp_path, monkeypatch):
    import json
    from bhack import track
    res = {"nowcast": {"asof": "2026-11-02", "forecast": [
        {"coin": "BTC", "horizon": 1, "target_date": "2026-11-03", "last_close": 100.0,
         "p05": 95.0, "p50": 100.0, "p95": 105.0},
        {"coin": "BTC", "horizon": 7, "target_date": "2026-11-09", "last_close": 100.0,
         "p05": 85.0, "p50": 100.0, "p95": 115.0}]}}
    (tmp_path / "results.json").write_text(json.dumps(res))
    monkeypatch.setattr(track, "REPORTS", tmp_path)
    monkeypatch.setattr(track, "realized", lambda c, a, b: pd.Series({pd.Timestamp("2026-11-03"): 94.0}))
    out = track.run(today=pd.Timestamp("2026-11-05"), build_site=False)
    assert out["resolved"] == 1 and out["inside_90"] == 0
    one = [r for r in out["rows"] if r["horizon"] == 1][0]
    assert one["no_change_error"] == pytest.approx(-0.06)
    assert [r for r in out["rows"] if r["horizon"] == 7][0]["close"] is None


def test_forward_return_and_days_to_recover():
    from bhack import aftermath
    idx = pd.date_range("2024-01-01", periods=10)
    c = pd.Series([100, 100, 100, 90, 92, 95, 99, 101, 103, 105.0], index=idx)
    day0 = idx[3]
    assert aftermath.forward_return(c, day0, 4) == pytest.approx(101 / 100 - 1)
    assert np.isnan(aftermath.forward_return(c, day0, 50))
    assert aftermath.days_to_recover(c, day0) == 5  # from the close of the 3rd to the 8th
    assert aftermath.days_to_recover(pd.Series([100, 101, 102.0], index=idx[:3]), idx[1]) == 0


def test_scenarios_have_no_trend_and_widen_with_horizon():
    from bhack import scenarios
    rng = np.random.default_rng(6)
    r = rng.normal(0.01, 0.03, 1500)  # a strong upward drift must not reach the median path
    short, long = scenarios.simulate(r, 7, sims=3000), scenarios.simulate(r, 180, sims=3000)
    assert abs(np.median(long)) < 0.1
    assert np.subtract(*np.quantile(long, [0.95, 0.05])) > 2 * np.subtract(*np.quantile(short, [0.95, 0.05]))


def test_scenario_backtest_is_calibrated_on_a_random_walk():
    from bhack import scenarios
    rng = np.random.default_rng(7)
    idx = pd.date_range("2018-01-01", "2026-01-01")
    close = pd.Series(100 * np.exp(np.cumsum(rng.standard_t(4, len(idx)) * 0.02)), index=idx)
    t = scenarios.backtest(close, 30)
    assert 0.78 <= t["inside"].mean() <= 1.0


def test_tail_excess_counts_only_earlier_hacks():
    allvals = np.linspace(-3, 3, 1001)
    tab = pd.DataFrame({"date": ["2020-01-01", "2021-01-01", "2022-01-01", "2026-10-29"],
                        "name": ["a", "b", "c", "Binance"], "amount_m": [40.0, 50.0, 60.0, 6000.0],
                        "scar_1": [-2.9, -2.8, 0.1, -2.9]})
    out = eventstudy.tail_excess(tab, allvals)
    assert out["n"] == 3 and out["below"] == 2 and out["above"] == 0
    assert out["largest_below_m"] == 50.0 and out["p_below"] < 0.01


def test_coin_recovery_low_is_never_above_the_last_close():
    # the minute data ends before the last close, so the low must also look at daily lows
    import json
    from pathlib import Path
    res = json.loads((Path(__file__).resolve().parents[1] / "reports" / "results.json").read_text(encoding="utf-8"))
    for c in res["aftermath"]["coins"]:
        assert c["low"] <= c["last_close"]

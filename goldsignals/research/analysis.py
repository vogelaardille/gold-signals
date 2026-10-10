"""Berekeningen voor onderzoeksvragen V1-V6 (zie research/PLAN.md).

Alleen de RESEARCH-periode wordt geladen (Market met until = begin hold-out). De
hold-out-candles bestaan in deze berekening dus niet eens.
"""
import numpy as np
import pandas as pd

from goldsignals.market import period_bounds
from goldsignals.research.events import (Arrays, detect_events, measure_outcomes, null_shifts,
                                         repeated_flag, simulate_trades, zone_setup, zone_table)
from goldsignals.research.stats import bootstrap_mean, vs_null, week_id

METRICS = {"bounce": "bounce", "r": "r"}     # primaire meetwaarden
SPLITS = ["timeframe", "conf_bin", "repeat", "age_bin", "side_name", "trend_rel", "session", "vol_regime"]
SPLIT_LABEL = {
    "timeframe": "Timeframe", "conf_bin": "Confluence", "repeat": "Eerste/herhaalde test",
    "age_bin": "Leeftijd zone", "side_name": "Support/resistance", "trend_rel": "T.o.v. daily-trend",
    "session": "Sessie", "vol_regime": "Volatiliteit",
}
FILTERS = {"f_rsi": "RSI <= 40 / >= 60", "f_reject": "Afwijzingscandle", "f_ema": "EMA50/200-trend mee"}


def round_trip_cost(cfg: dict, mult: float = 1.0) -> float:
    c = cfg["costs"]
    return mult * (c["spread_usd"] + 2 * c["slippage_usd"])


class Context:
    """Alles wat elke berekening nodig heeft, een keer klaargezet."""

    def __init__(self, market, cfg, method):
        self.cfg, self.rcfg, self.method = cfg, cfg["research"], method
        self.a = Arrays.from_candles(market.candles)
        self.f = market.features
        self.zt = zone_table(market, method)
        start, end = period_bounds(cfg, "research")
        close_time = market.close_time
        self.min_i = int(np.searchsorted(close_time, start, side="right"))
        # Laatste candle-index waarvan het hele uitkomstvenster nog in de research-periode past
        n = self.a.n
        need = max(self.rcfg["horizon_bars"], self.rcfg["setup_max_bars"]) + 1
        self.max_i = n - 1 - need
        self.zt = self.zt[self.zt["i"] >= self.min_i].reset_index(drop=True)
        self.cost = round_trip_cost(cfg)
        assert close_time[-1] <= end, "hold-out-data in de research-berekening!"

    def events(self, shift=None, with_repeat=True) -> pd.DataFrame:
        ev = detect_events(self.zt, self.a, shift, self.max_i)
        ev = measure_outcomes(ev, self.a, self.rcfg)
        ev = zone_setup(ev, self.a, self.rcfg, self.cost)
        return annotate(ev, self, with_repeat)


def annotate(ev: pd.DataFrame, ctx: Context, with_repeat=True) -> pd.DataFrame:
    """Extra kolommen voor de opsplitsingen (V2, V5, V6)."""
    r = ctx.rcfg
    a, f = ctx.a, ctx.f
    i = ev["i"].to_numpy()
    side = ev["side"].to_numpy()
    prev = f.iloc[i - 1]        # bekend op het moment van de test (sluiting i-1)
    now = f.iloc[i]             # bekend op de slotkoers van de test-candle (voor V6)
    ev["week"] = week_id(ev["time"])
    ev["year"] = ev["time"].dt.year
    ev["side_name"] = np.where(side == 1, "support", "resistance")
    tr = side * prev["d_trend"].to_numpy()
    ev["trend_rel"] = np.where(tr > 0, "mee", np.where(tr < 0, "tegen", "geen"))
    ev["vol_regime"] = prev["vol_regime"].to_numpy()
    h = ev["time"].dt.hour
    s = r["sessions_utc"]
    ev["session"] = np.where((h >= s["london"][0]) & (h < s["london"][1]), "londen",
                             np.where((h >= s["newyork"][0]) & (h < s["newyork"][1]), "newyork", "azie"))
    age = (pd.to_datetime(ev["as_of"]) - pd.to_datetime(ev["first_touch"])).dt.total_seconds() / 86400
    ev["age_bin"] = pd.cut(age, [-1, 30, 180, 1e9], labels=["<30d", "30-180d", ">180d"]).astype(str)
    ev["conf_bin"] = pd.cut(ev["confluence"], [0, 2, 4, 6], labels=["laag (1-2)", "midden (3-4)", "hoog (5-6)"]).astype(str)
    if with_repeat:
        ev["repeat"] = np.where(repeated_flag(ev, r["repeat_window_bars"]), "herhaald", "eerste")
    # Bevestigingsfilters (V6), bekend op de slotkoers van candle i
    rsi = now["rsi"].to_numpy()
    ev["f_rsi"] = np.where(side == 1, rsi <= r["rsi_long_max"], rsi >= r["rsi_short_min"])
    o, hi, lo, c = a.open[i], a.high[i], a.low[i], a.close[i]
    rng_ = np.maximum(hi - lo, 1e-9)
    wick_low = (np.minimum(o, c) - lo) / rng_
    wick_high = (hi - np.maximum(o, c)) / rng_
    ev["f_reject"] = np.where(side == 1, (c > ev["zhigh"]) & (wick_low >= r["rejection_wick_frac"]),
                              (c < ev["zlow"]) & (wick_high >= r["rejection_wick_frac"]))
    ema_up = now["ema_fast"].to_numpy() > now["ema_slow"].to_numpy()
    ev["f_ema"] = np.where(side == 1, ema_up, ~ema_up)
    # Walk-forward testvenster (kwartaal vanaf 2022-10-01), voor V5
    wf0 = pd.Timestamp("2022-10-01", tz="UTC")
    q = ((ev["time"].dt.year - wf0.year) * 12 + ev["time"].dt.month - wf0.month) // 3
    ev["wf_window"] = np.where(ev["time"] >= wf0, q + 1, 0)
    return ev


# ---------------------------------------------------------------------------
# Samenvattingen
# ---------------------------------------------------------------------------

def group_means(ev: pd.DataFrame, col: str = None) -> dict:
    """{groep: {'bounce': .., 'r': .., 'n': ..}}; groep '_all' zonder col."""
    groups = {"_all": ev} if col is None else dict(tuple(ev.groupby(col)))
    return {g: {"bounce": float(d["bounce"].mean()) if len(d) else np.nan,
                "r": float(d["r"].mean()) if d["r"].notna().any() else np.nan,
                "n": int(len(d)), "n_r": int(d["r"].notna().sum())}
            for g, d in groups.items()}


def compare(real: pd.DataFrame, null_groups: list, col: str, rng, n_boot: int) -> list:
    """Per groep: echte waarde (met interval), nulmodel en verschil."""
    rows = []
    groups = ["_all"] if col is None else sorted(real[col].dropna().unique())
    for g in groups:
        d = real if col is None else real[real[col] == g]
        row = {"split": col or "_all", "group": g, "n": int(len(d)), "n_r": int(d["r"].notna().sum())}
        for m in METRICS:
            b = bootstrap_mean(d[m], d["week"], n_boot, rng)
            nulls = [ng.get(g, {}).get(m, np.nan) for ng in null_groups]
            vn = vs_null(b["est"], nulls)
            row.update({f"{m}": b["est"], f"{m}_lo": b["lo"], f"{m}_hi": b["hi"],
                        f"{m}_null": vn["null_mean"], f"{m}_null_lo": vn["null_lo"],
                        f"{m}_null_hi": vn["null_hi"], f"{m}_pct": vn["pct"], f"{m}_share_ge": vn["share_ge"],
                        f"{m}_edge": b["est"] - vn["null_mean"], f"{m}_edge_lo": b["lo"] - vn["null_mean"],
                        f"{m}_edge_hi": b["hi"] - vn["null_mean"]})
        rows.append(row)
    return rows


def run_null(ctx: Context, n_rep: int, rng, group_cols=(), with_repeat=False, collect=None):
    """Draai n_rep nulreplicaties. Geeft per groepkolom een lijst met group_means per replicatie.
    collect: optionele functie(ev) -> waarde, per replicatie verzameld (voor V4/V6)."""
    out = {c: [] for c in (None,) + tuple(group_cols)}
    extra = []
    for k in range(n_rep):
        ev = ctx.events(null_shifts(ctx.zt, ctx.rcfg, rng), with_repeat=with_repeat)
        for c in out:
            out[c].append(group_means(ev, c))
        if collect is not None:
            extra.append(collect(ev))
    return out, extra


# ---------------------------------------------------------------------------
# V4: breakout en retest
# ---------------------------------------------------------------------------

def breakout_retest(ev: pd.DataFrame, ctx: Context) -> pd.DataFrame:
    """Per break-event: retest binnen W candles? En R van de retest- en doorzet-setup."""
    r, a = ctx.rcfg, ctx.a
    W, M = r["retest_window_bars"], r["setup_max_bars"]
    b = ev[ev["outcome"] == "break"].copy()
    j = (b["i"] + b["t_break"]).to_numpy()            # de candle die de break bevestigt
    ok = j + W + M + 1 < a.n
    b, j = b[ok].copy(), j[ok]
    if b.empty:
        return b
    side = -b["side"].to_numpy()                       # breakout-richting: tegengesteld aan de test
    atr = b["atr_1h"].to_numpy()
    zl, zh = b["zlow"].to_numpy(), b["zhigh"].to_numpy()
    # Doorzetten direct na de break: entry open[j+1], stop aan de andere kant van de zone
    stop_c = np.where(side == 1, zl, zh) - side * r["setup_stop_atr"] * atr
    entry_c = a.open[j + 1]
    ok_c = side * (entry_c - stop_c) >= r["setup_min_risk_atr"] * atr
    b["r_cont"] = np.nan
    if ok_c.any():
        b.loc[ok_c, "r_cont"] = simulate_trades(a, j[ok_c], side[ok_c], stop_c[ok_c], r["setup_rr"], M, ctx.cost)["r"]
    # Retest: koers raakt de zone weer, nu vanaf de breakout-kant
    H, L, C = (a.high[(j + 1)[:, None] + np.arange(W)], a.low[(j + 1)[:, None] + np.arange(W)],
               a.close[(j + 1)[:, None] + np.arange(W)])
    touch = np.where(side[:, None] == 1, L <= zh[:, None], H >= zl[:, None])
    t_rt = np.where(touch.any(axis=1), touch.argmax(axis=1), W)
    b["retest"] = (t_rt < W).astype(float)
    k = j + 1 + np.minimum(t_rt, W - 1)                # retest-candle
    held = np.where(side == 1, a.close[k] > zh, a.close[k] < zl) & (t_rt < W)
    stop_r = np.where(side == 1, zl, zh) - side * r["setup_stop_atr"] * atr
    ok_r = held & (side * (a.open[k + 1] - stop_r) >= r["setup_min_risk_atr"] * atr)
    b["retest_held"] = np.where(t_rt < W, held.astype(float), np.nan)
    b["r_retest"] = np.nan
    if ok_r.any():
        b.loc[ok_r, "r_retest"] = simulate_trades(a, k[ok_r], side[ok_r], stop_r[ok_r], r["setup_rr"], M, ctx.cost)["r"]
    return b


def q4_summary(b: pd.DataFrame) -> dict:
    return {"retest": float(b["retest"].mean()), "retest_held": float(b["retest_held"].mean()),
            "r_retest": float(b["r_retest"].mean()), "r_cont": float(b["r_cont"].mean()),
            "n_break": int(len(b)), "n_retest_trades": int(b["r_retest"].notna().sum()),
            "n_cont_trades": int(b["r_cont"].notna().sum())}


# ---------------------------------------------------------------------------
# V5: buy-and-hold en willekeurige entries
# ---------------------------------------------------------------------------

def buy_and_hold_per_year(ctx: Context) -> dict:
    c = pd.Series(ctx.a.close, index=ctx.a.time)
    c = c.iloc[ctx.min_i:]
    out = {}
    for y, s in c.groupby(c.index.year):
        out[int(y)] = float(s.iloc[-1] / s.iloc[0] - 1) * 100
    out["totaal"] = float(c.iloc[-1] / c.iloc[0] - 1) * 100
    return out


def random_entries(ctx: Context, risk_atr: np.ndarray, rng, n: int = 30000) -> pd.DataFrame:
    """Willekeurige entries: willekeurig uur en richting, stopafstand getrokken uit de
    verdeling van de echte zone-setups (in ATR), zelfde 1:2 en kosten."""
    r, a = ctx.rcfg, ctx.a
    i = rng.integers(ctx.min_i, ctx.max_i, n)
    side = rng.choice([-1, 1], n)
    atr = ctx.f["atr"].to_numpy()[i]
    risk = rng.choice(risk_atr[~np.isnan(risk_atr)], n) * atr
    stop = a.open[i + 1] - side * risk
    sim = simulate_trades(a, i, side, stop, r["setup_rr"], r["setup_max_bars"], ctx.cost)
    t = a.time[i]
    return pd.DataFrame({"time": t, "year": t.year, "side": side, "r": sim["r"], "week": week_id(t)})

"""Onzekerheid: block-bootstrap per week en vergelijking met het nulmodel.

Waarom per week? Events die dicht op elkaar liggen hangen samen (dezelfde marktbeweging
raakt meerdere zones). Als je losse events zou trekken, doe je alsof je veel meer
onafhankelijke informatie hebt dan echt zo is, en worden de intervallen te smal.
Door hele weken te trekken blijft die samenhang binnen een week intact.
"""
import numpy as np
import pandas as pd

WEEK = pd.Timedelta(days=7)
EPOCH = pd.Timestamp("2020-01-06", tz="UTC")   # een maandag


def week_id(times) -> np.ndarray:
    return np.asarray((pd.DatetimeIndex(times) - EPOCH) // WEEK)


def _week_sums(values, weeks, all_weeks):
    """Som en aantal per week, uitgelijnd op all_weeks."""
    v = np.asarray(values, float)
    ok = ~np.isnan(v)
    pos = np.searchsorted(all_weeks, np.asarray(weeks)[ok])
    sums = np.bincount(pos, weights=v[ok], minlength=len(all_weeks))
    cnts = np.bincount(pos, minlength=len(all_weeks)).astype(float)
    return sums, cnts


def bootstrap_mean(values, weeks, n_boot: int, rng, extra=None) -> dict:
    """Gemiddelde met 95%-interval (week-blocks). extra: optioneel (values2, weeks2) om het
    verschil mean(values) - mean(values2) te bootstrappen met dezelfde getrokken weken."""
    all_weeks = np.unique(np.concatenate([np.asarray(weeks)] + ([np.asarray(extra[1])] if extra else [])))
    s1, c1 = _week_sums(values, weeks, all_weeks)
    draws = rng.multinomial(len(all_weeks), np.full(len(all_weeks), 1 / len(all_weeks)), size=n_boot)
    with np.errstate(invalid="ignore", divide="ignore"):
        est = s1.sum() / c1.sum() if c1.sum() else np.nan
        boot = (draws @ s1) / (draws @ c1)
        if extra is not None:
            s2, c2 = _week_sums(extra[0], extra[1], all_weeks)
            est = est - (s2.sum() / c2.sum() if c2.sum() else np.nan)
            boot = boot - (draws @ s2) / (draws @ c2)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5]) if np.isfinite(boot).any() else (np.nan, np.nan)
    return {"est": float(est), "lo": float(lo), "hi": float(hi), "n": int(c1.sum())}


def vs_null(real: float, null_values) -> dict:
    """Plaats de echte waarde in de verdeling van het nulmodel."""
    nv = np.asarray(null_values, float)
    nv = nv[~np.isnan(nv)]
    if len(nv) == 0 or np.isnan(real):
        return {"null_mean": np.nan, "null_lo": np.nan, "null_hi": np.nan, "pct": np.nan, "share_ge": np.nan}
    return {
        "null_mean": float(nv.mean()),
        "null_lo": float(np.percentile(nv, 2.5)),
        "null_hi": float(np.percentile(nv, 97.5)),
        # percentiel van de echte waarde in de nulverdeling (100 = beter dan alle nul-replicaties)
        "pct": float((nv < real).mean() * 100),
        # aandeel nul-replicaties dat minstens zo goed is (permutatietoets, +1-correctie)
        "share_ge": float(((nv >= real).sum() + 1) / (len(nv) + 1)),
    }

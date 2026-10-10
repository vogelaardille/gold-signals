"""Figuren voor het ronde-3-rapport (donker, leesbaar op een telefoon). Zelfde palet als ronde 1/2."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from goldsignals.research.figures import AQUA, BLUE, GRID, INK, INK2, MUTED, ORANGE, SURFACE, _style  # noqa: E402

PURPLE = "#9b6dd6"
# Vaste kleur per reeks (kleur volgt de reeks, nooit de rangorde)
SERIES = {"EW": (MUTED, "-", "gelijk gewicht (EW)"), "60/40": (MUTED, "-", "60/40 SPY/IEF"),
          "F1_N10": (BLUE, "-", "F1 trendfilter (N=10)"), "F2_k3_L12": (ORANGE, "-", "F2 dual momentum (k=3, L=12)"),
          "F3_equal_weight_v10_w20": (AQUA, "-", "F3 vol-target op EW (10%, 20d)"),
          "F3_sixty_forty_v10_w20": (AQUA, "-", "F3 vol-target op 60/40 (10%, 20d)"),
          "F3_sixty_forty_v10_w20|matched": (INK2, "--", "60/40 met dezelfde tijd in de markt")}
DIVERGING = LinearSegmentedColormap.from_list("div", [ORANGE, "#3a3a37", BLUE])


def _equity(r: pd.Series) -> pd.Series:
    eq = (1 + r).cumprod()
    return pd.concat([pd.Series([1.0], index=[r.index[0] - pd.offsets.MonthBegin(1)]), eq])


def equity_and_drawdown(m: pd.DataFrame, cols, path, title):
    _style()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.4, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for c in cols:
        col, ls, lab = SERIES[c]
        eq = _equity(m[c])
        a1.plot(eq.index, eq, color=col, ls=ls, lw=2 if c in ("EW", "60/40") else 1.8, label=lab)
        a2.plot(eq.index, (eq / eq.cummax() - 1) * 100, color=col, ls=ls, lw=1.5)
    a1.set_yscale("log")
    a1.set_yticks([1, 1.5, 2, 3, 4])
    a1.set_yticklabels(["1,0", "1,5", "2,0", "3,0", "4,0"])
    a1.set_ylabel("waarde van 1 (log)")
    a1.set_title(title, loc="left")
    a1.legend(fontsize=8, loc="upper left")
    a2.set_ylabel("daling vanaf top (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def grid_heatmaps(grid: pd.DataFrame, primary: list, path):
    """Hele grid: Sharpe-verschil (links) en MDD-verschil (rechts), kosten 0,10%."""
    _style()
    g = grid[grid["cost"] == 0.001]
    blocks = [("F1 trendfilter", g[g["family"] == "F1"], "n", None),
              ("F2 dual momentum", g[g["family"] == "F2"], "L", "k"),
              ("F3 vol-target op EW", g[(g["family"] == "F3") & (g["base"] == "equal_weight")], "window", "target"),
              ("F3 vol-target op 60/40", g[(g["family"] == "F3") & (g["base"] == "sixty_forty")], "window", "target")]
    fig, axes = plt.subplots(4, 2, figsize=(6.4, 9.2), gridspec_kw={"height_ratios": [1, 3, 3, 3]})
    for row, (name, d, xcol, ycol) in enumerate(blocks):
        for col, (metric, lim, fmt, lab) in enumerate((("sharpe_diff", 0.3, "{:+.2f}", "Sharpe-verschil"),
                                                       ("mdd_diff", 15, "{:+.1f}", "MDD-verschil (pp)"))):
            ax = axes[row, col]
            xs = sorted(d[xcol].unique())
            ys = sorted(d[ycol].unique()) if ycol else [None]
            z = np.array([[d[(d[xcol] == x) & ((d[ycol] == y) if ycol else True)][metric].iloc[0] for x in xs] for y in ys])
            ax.imshow(z, cmap=DIVERGING, vmin=-lim, vmax=lim, aspect="auto")
            for i, y in enumerate(ys):
                for j, x in enumerate(xs):
                    ax.text(j, i, fmt.format(z[i, j]), ha="center", va="center", color=INK, fontsize=8)
                    rid = d[(d[xcol] == x) & ((d[ycol] == y) if ycol else True)]["id"].iloc[0]
                    if rid in primary:
                        ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec=INK, lw=2))
            ax.set_xticks(range(len(xs)))
            xl = {"n": "N={}", "L": "L={}", "window": "{}d"}[xcol]
            ax.set_xticklabels([xl.format(int(x)) for x in xs], fontsize=8)
            ax.set_yticks(range(len(ys)))
            if ycol == "k":
                ax.set_yticklabels([f"k={int(y)}" for y in ys], fontsize=8)
            elif ycol == "target":
                ax.set_yticklabels([f"{round(y * 100)}%" for y in ys], fontsize=8)
            else:
                ax.set_yticklabels([""])
            ax.grid(False)
            if row == 0:
                ax.set_title(lab, loc="left", fontsize=10)
            if col == 0:
                ax.set_ylabel(name, fontsize=8, color=INK2)
    fig.text(0.01, 0.005, "Wit kader = vooraf gekozen primaire configuratie. Blauw = beter dan de baseline, oranje = slechter.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def rolling(rolls: dict, path):
    _style()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.4, 5.6), sharex=True)
    for pid, df in rolls.items():
        col, _, lab = SERIES[pid]
        ls = "--" if pid == "F3_equal_weight_v10_w20" else "-"
        a1.plot(pd.to_datetime(df["end"]), df["sharpe"], color=col, ls=ls, lw=1.8, label=lab)
        a2.plot(pd.to_datetime(df["end"]), df["mdd"], color=col, ls=ls, lw=1.8)
    for a in (a1, a2):
        a.axhline(0, color=INK2, lw=1)
    a1.set_ylabel("Sharpe-verschil")
    a2.set_ylabel("MDD-verschil (pp)")
    a2.set_xlabel("einde van het 10-jaarsvenster")
    a1.set_title("Rolling 10 jaar: voordeel van de regel (boven 0 = beter)", loc="left")
    a1.legend(fontsize=7.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def random_timing(results: dict, path):
    _style()
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 5.0))
    items = list(results.items())
    y = np.arange(len(items))[::-1]
    for ax, key, lab in ((axes[0], "sharpe", "Sharpe"), (axes[1], "mdd", "maximale daling (%)")):
        for yy, (pid, p) in zip(y, items):
            rt = p["random_timing"]
            lo, hi = rt[f"{key}_random_p5_p95"]
            ax.plot([lo, hi], [yy, yy], color=MUTED, lw=4, solid_capstyle="round",
                    label="willekeurige timing, 5–95%" if yy == y[0] else None)
            ax.plot(p["summary"]["strat"][key], yy, "o", color=SERIES[pid][0], ms=8, mec=SURFACE, mew=1.5,
                    label="de regel zelf" if yy == y[0] else None)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{SERIES[pid][2].split(' (')[0]}\n{p['random_timing'][key + '_pct']:.0f}e percentiel"
                            for pid, p in items], fontsize=8)
        ax.set_title(lab, loc="left")
        ax.grid(axis="y", visible=False)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def per_asset(per_f1: dict, per_f3: dict, path):
    """Sharpe-verschil per asset t.o.v. buy-and-hold van die asset (F1 en F3 apart toegepast)."""
    _style()
    assets = list(per_f1)
    f1 = [per_f1[a]["trend"]["sharpe"] - per_f1[a]["buy_hold"]["sharpe"] for a in assets]
    f3 = [per_f3[a]["sharpe"] for a in assets]
    f1m = [abs(per_f1[a]["buy_hold"]["mdd"]) - abs(per_f1[a]["trend"]["mdd"]) for a in assets]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.4, 4.2), sharey=True)
    yy = np.arange(len(assets))[::-1]
    a1.barh(yy + 0.2, f1, height=0.38, color=BLUE, label="F1 trendfilter (N=10)")
    a1.barh(yy - 0.2, f3, height=0.38, color=AQUA, label="F3 vol-target (10%, 20d)")
    a1.set_yticks(yy)
    a1.set_yticklabels(assets)
    a1.axvline(0, color=INK2, lw=1)
    a1.set_title("Sharpe-verschil", loc="left")

    a2.barh(yy, f1m, height=0.5, color=BLUE)
    a2.axvline(0, color=INK2, lw=1)
    a2.set_title("F1: kleinere MDD (pp)", loc="left")
    for a in (a1, a2):
        a.grid(axis="y", visible=False)
    fig.legend(*a1.get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def exposure_timeline(series: dict, path):
    """Blootstelling van F3-60/40 in P, research en H3."""
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    colors = {"P (fondsen)": PURPLE, "research": AQUA, "H3": BLUE}
    for name, s in series.items():
        ax.fill_between(s.index, 0, s.to_numpy() * 100, step="post", color=colors[name], alpha=0.85, lw=0, label=name)
    ax.set_ylim(0, 105)
    ax.set_ylabel("belegd (%)")
    ax.set_title("F3-60/40: deel belegd per maand (rest in cash)", loc="left")
    ax.legend(fontsize=8, loc="lower left", ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def f1_onoff(w: pd.DataFrame, avail: pd.DataFrame, start, end, path):
    """Welke assets de trendregel aanhield, per maand (gehouden in de maand ná het signaal)."""
    _style()
    w = w.loc[start:end]
    av = avail.reindex(w.index)
    held = w.index + pd.offsets.MonthBegin(1)
    z = np.where(av.to_numpy(), (w.to_numpy() > 0).astype(float), np.nan).T
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    cmap = LinearSegmentedColormap.from_list("onoff", ["#2c2c2a", BLUE])
    cmap.set_bad(SURFACE)
    ax.imshow(np.ma.masked_invalid(z), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(w.columns)))
    ax.set_yticklabels(w.columns, fontsize=8)
    ticks = [i for i, d in enumerate(held) if d.month in (1, 4, 7, 10)]
    ax.set_xticks(ticks)
    mnd = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    ax.set_xticklabels([f"{mnd[held[i].month - 1]} '{held[i].strftime('%y')}" for i in ticks], fontsize=7.5)
    ax.grid(False)
    ax.set_title("F1 trendfilter: blauw = belegd in die maand, grijs = cash", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

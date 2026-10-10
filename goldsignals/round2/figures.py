"""Figuren voor het ronde-2-rapport (donker, leesbaar op een telefoon)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from goldsignals.research.figures import BLUE, INK, INK2, MUTED, ORANGE, SURFACE, _style  # noqa: E402

GRIDC = "#3a3a37"

FAM_NAME = {"F1": "F1 daily trend", "F2": "F2 vol-compressie", "F3": "F3 mean reversion", "F4": "F4 macrofilter"}


def families_forest(fams: dict, path):
    """Per familie: gem. R (walk-forward OOS) met 95%-interval, naast het 95e percentiel van random."""
    _style()
    items = list(fams.items())
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    y = np.arange(len(items))[::-1]
    for yy, (f, s) in zip(y, items):
        ci = s["ci"]
        ax.plot([ci["lo"], ci["hi"]], [yy + 0.1, yy + 0.1], color=BLUE, lw=2.5)
        ax.plot(ci["est"], yy + 0.1, "o", color=BLUE, ms=7, mec=SURFACE, mew=1.5, label="strategie" if yy == y[0] else None)
        ax.plot(s["random_p95"], yy - 0.15, "|", color=ORANGE, ms=14, mew=2.5, label="random, 95e pctl" if yy == y[0] else None)
        ax.plot(s["random_mean"], yy - 0.15, "s", color=MUTED, ms=6, label="random, gemiddeld" if yy == y[0] else None)
        ax.text(0.99, yy, f"n={s['n']}", transform=ax.get_yaxis_transform(),
                ha="right", va="center", color=INK2, fontsize=8)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([FAM_NAME[f] for f, _ in items], color=INK2)
    ax.set_xlabel("gemiddelde R per trade na kosten (walk-forward 2010-2018)")
    ax.grid(axis="y", visible=False)
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def entry_vs_random(df: pd.DataFrame, path):
    """Elke variant (F1, F2, F4): eigen gem. R tegen random met dezelfde exits."""
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    styles = {"F1": (BLUE, "o", "F1 daily trend"), "F4": (MUTED, "s", "F4 macrofilter (long)"),
              "F2": (ORANGE, "D", "F2 vol-compressie")}
    for f, (col, mk, lab) in styles.items():
        d = df[df["family"] == f]
        ax.scatter(d["random_mean"], d["avg_r_1x"], s=np.clip(d["n"], 10, 250) * 0.6 + 15, color=col, marker=mk,
                   edgecolor=SURFACE, linewidth=1, label=lab, alpha=0.9, zorder=3)
    lo = min(df["random_mean"].min(), df["avg_r_1x"].min()) - 0.05
    hi = max(df["random_mean"].max(), df["avg_r_1x"].max()) + 0.05
    ax.plot([lo, hi], [lo, hi], color=INK2, lw=1, ls="--")
    ax.text(hi, hi, " even goed als random", color=INK2, fontsize=8, ha="right", va="bottom")
    ax.axhline(0, color=GRIDC, lw=0.8)
    ax.axvline(0, color=GRIDC, lw=0.8)
    ax.set_xlabel("random entries met dezelfde exits (gem. R)")
    ax.set_ylabel("variant zelf (gem. R)")
    ax.set_title("Zit de winst in het instapmoment of in de exit?", loc="left")
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def equity_vs_bh(curves: dict, path):
    """Equity (geïndexeerd op 100) van een paar varianten naast buy-and-hold; één as."""
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    colors = [BLUE, ORANGE, "#199e70", "#c98500"]
    for (lab, s), col in zip(curves.items(), colors):
        ax.plot(s.index, s.values, color=col if lab != "buy-and-hold" else MUTED, lw=2, label=lab)
    ax.set_ylabel("index (start = 100)")
    ax.set_title("Groei van 100 (1% risico per trade) vs. buy-and-hold, 2010-2018", loc="left", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def zone15_null(z: dict, path):
    _style()
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 5.0))
    for ax, key, title, fmt in ((axes[0], "bounce", "Bounce-rate (15m)", "{:.1%}"),
                                (axes[1], "r", "Gemiddelde R 1:2-setup na kosten (15m)", "{:+.3f}")):
        vals = np.array([v for v in z[f"null_{key}_values"] if v is not None], float)
        ax.hist(vals, bins=30, color=MUTED, alpha=0.85, label="willekeurige niveaus")
        est = z[key]["est"]
        ax.axvline(est, color=BLUE, lw=2.5, label="echte zones")
        ax.set_title(title, loc="left")
        ax.set_yticks([])
        ax.legend(loc="upper right", fontsize=8)
        ax.text(est, ax.get_ylim()[1] * 0.9, " " + fmt.format(est), color=INK, va="top")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


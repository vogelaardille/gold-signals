"""Figuren voor het onderzoeksrapport (matplotlib, donker thema, leesbaar op een telefoon)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Donker palet (zelfde kleuren als het dashboard)
SURFACE, INK, INK2, MUTED, GRID = "#1a1a19", "#f0efec", "#c3c2b7", "#898781", "#2c2c2a"
BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"
TF_COLORS = {"1d": "#3987e5", "4h": "#d95926", "1h": "#199e70"}


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
        "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
    })


def null_hist(q1: dict, path):
    _style()
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 5.6))
    for ax, key, title, fmt in ((axes[0], "bounce", "Bounce-rate", "{:.1%}"),
                                (axes[1], "r", "Gemiddelde R (1:2-setup, na kosten)", "{:+.3f}")):
        vals = np.array([v for v in q1[f"null_{key}_values"] if v is not None], float)
        ax.hist(vals, bins=30, color=MUTED, alpha=0.8, label="willekeurige zones (nulmodel)")
        ax.axvline(q1[key], color=BLUE, lw=2.5, label="echte zones")
        ax.set_title(title, loc="left")
        ax.text(q1[key], ax.get_ylim()[1] * 0.92, " echt " + fmt.format(q1[key]), color=INK, va="top")
        ax.set_yticks([])
        ax.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def forest(q2: dict, labels: dict, path):
    """Per groep: verschil echt - nulmodel in gemiddelde R, met 95%-interval."""
    _style()
    rows = []
    for split, items in q2.items():
        for it in items:
            rows.append((f"{labels[split]}: {it['group']}", it["r_edge"], it["r_edge_lo"], it["r_edge_hi"], it["n_r"]))
    fig, ax = plt.subplots(figsize=(6.4, 0.32 * len(rows) + 1.2))
    y = np.arange(len(rows))[::-1]
    for yy, (lab, e, lo, hi, n) in zip(y, rows):
        ax.plot([lo, hi], [yy, yy], color=BLUE, lw=2, solid_capstyle="round")
        ax.plot(e, yy, "o", color=BLUE, ms=6, mec=SURFACE, mew=1.5)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r[0]}  (n={r[4]})" for r in rows], fontsize=8.5, color=INK2)
    ax.set_xlabel("verschil gemiddelde R: echte zones min nulmodel")
    fig.suptitle("Voordeel van echte zones per eigenschap", x=0.02, ha="left", fontweight="bold", fontsize=11)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def per_year(q5: dict, path):
    _style()
    df = pd.DataFrame(q5["by_year"])
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.6), sharey=True)
    for ax, side, title in ((axes[0], "support", "Long bij support"), (axes[1], "resistance", "Short bij resistance")):
        d = df[df["side"] == side].sort_values("year")
        x = np.arange(len(d))
        est = [v["est"] for v in d["r"]]
        lo = [v["lo"] for v in d["r"]]
        hi = [v["hi"] for v in d["r"]]
        nul = [v["null_mean"] for v in d["r_null"]]
        for xx, a, b in zip(x, lo, hi):
            ax.plot([xx, xx], [a, b], color=BLUE, lw=2)
        ax.plot(x, est, "o", color=BLUE, ms=7, mec=SURFACE, mew=1.5, label="echte zones")
        ax.plot(x + 0.18, nul, "s", color=MUTED, ms=6, label="nulmodel")
        ax.plot(x - 0.18, d["r_random"], "D", color=ORANGE, ms=5, label="willekeurige entry")
        ax.axhline(0, color=INK2, lw=1)
        ax.set_xticks(x)
        ax.set_xticklabels(d["year"].astype(str))
        ax.set_title(title, loc="left")
    axes[0].set_ylabel("gemiddelde R na kosten")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def filters(q6: dict, path):
    _style()
    items = list(q6.values())
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    y = np.arange(len(items))[::-1]
    for yy, it in zip(y, items):
        d = it["diff"]
        ax.plot([d["lo"], d["hi"]], [yy + 0.12, yy + 0.12], color=BLUE, lw=2)
        ax.plot(d["est"], yy + 0.12, "o", color=BLUE, ms=6, mec=SURFACE, mew=1.5,
                label="echte zones" if yy == y[0] else None)
        ax.plot(it["diff_null"]["null_mean"], yy - 0.12, "s", color=MUTED, ms=6,
                label="nulmodel" if yy == y[0] else None)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([it["label"] for it in items], color=INK2)
    ax.set_xlabel("gemiddelde R met filter min zonder filter")
    ax.set_title("Wat voegt een bevestiging toe?", loc="left")
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def example_chart(market, ev, cfg, path):
    """Candles rond een voorbeeld-event, met de zone als band."""
    _style()
    i = int(ev["i"])
    c = market.candles.iloc[i - 30:i + 26]
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    x = np.arange(len(c))
    up = c["close"] >= c["open"]
    ax.vlines(x, c["low"], c["high"], color=MUTED, lw=1)
    ax.bar(x[up], (c["close"] - c["open"])[up], bottom=c["open"][up], color=INK2, width=0.6)
    ax.bar(x[~up], (c["open"] - c["close"])[~up], bottom=c["close"][~up], color="#5a5955", width=0.6)
    ax.axhspan(ev["zlow"], ev["zhigh"], color=TF_COLORS.get(ev["timeframe"], BLUE), alpha=0.3, lw=0)
    atr, zl, zh = ev["atr_1h"], ev["zlow"], ev["zhigh"]
    entry = market.candles["open"].iloc[i + 1]
    stop = zl - 0.25 * atr
    levels = [(zh + atr, "bounce-niveau", INK2, ":", "bottom"), (zl - 0.5 * atr, "break-niveau", INK2, ":", "top"),
              (stop, "stop", "#e66767", "--", "bottom"), (entry + 2 * (entry - stop), "target 1:2", "#0ca30c", "--", "bottom")]
    for y, lab, col, ls, va in levels:
        ax.axhline(y, color=col, lw=1, ls=ls)
        ax.text(len(c) + 0.5, y, lab, color=col, va=va, fontsize=7.5)
    ax.set_xlim(-1, len(c) + 9)
    k = 30
    ax.annotate("test", (k, c["low"].iloc[k]), xytext=(k - 8, c["low"].iloc[k] - 0.4 * (c["high"].max() - c["low"].min()) / 3),
                color=INK, arrowprops=dict(arrowstyle="->", color=INK))
    ticks = x[::12]
    ax.set_xticks(ticks)
    ax.set_xticklabels([t.strftime("%d-%m %H:%M") for t in c.index[::12]], fontsize=8)
    ax.set_title(f"Voorbeeld: support-test op {ev['time']:%d-%m-%Y %H:%M} UTC (zone in kleur)", loc="left", fontsize=10)
    ax.set_ylabel("USD")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)

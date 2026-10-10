"""PNG-chart voor een SIGNAAL-melding: 1h-candles, zones, entry/stop/target (mplfinance)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402

TF_COLORS = {"1d": "#3987e5", "4h": "#d95926", "1h": "#199e70"}
STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(up="#c3c2b7", down="#5a5955", edge="inherit", wick="#898781"),
    facecolor="#1a1a19", figcolor="#1a1a19", gridcolor="#2c2c2a", gridstyle="-",
    rc={"axes.labelcolor": "#c3c2b7", "xtick.color": "#898781", "ytick.color": "#898781", "text.color": "#f0efec"})


def signal_chart(candles, zones, sig, entry_est: float, path, bars: int = 96, max_zones: int = 6):
    c = candles.iloc[-bars:][["open", "high", "low", "close", "volume"]].copy()
    c.index = c.index.tz_convert("Europe/Amsterdam").tz_localize(None)
    lo = min(c["low"].min(), sig.stop, sig.target)
    hi = max(c["high"].max(), sig.stop, sig.target)
    pad = (hi - lo) * 0.05
    lines = dict(hlines=[entry_est, sig.stop, sig.target], colors=["#f0efec", "#e66767", "#0ca30c"],
                 linestyle="--", linewidths=1.2)
    fig, axes = mpf.plot(c, type="candle", style=STYLE, hlines=lines, returnfig=True, figsize=(7.5, 4.4),
                         ylim=(lo - pad, hi + pad), ylabel="", datetime_format="%d-%m",
                         xrotation=0, scale_padding=dict(left=0.3, right=1.4, top=1.2, bottom=0.6))
    ax = axes[0]
    vis = zones[(zones["high"] >= lo - pad) & (zones["low"] <= hi + pad)]
    for _, z in vis.sort_values("score", ascending=False).head(max_zones).iterrows():
        ax.axhspan(z["low"], z["high"], color=TF_COLORS.get(z["timeframe"], "#3987e5"), alpha=0.13, lw=0)
    # Labels binnen de grafiek, links, zodat ze nooit buiten beeld vallen
    for y, txt, col in ((entry_est, "entry", "#f0efec"), (sig.stop, "stop", "#e66767"), (sig.target, "target", "#0ca30c")):
        ax.text(1, y, f"{txt} {y:.2f}", color=col, va="bottom", fontsize=8.5, fontweight="bold")
    side = "LONG" if sig.direction == 1 else "SHORT"
    fig.suptitle(f"XAUUSD 1h · {sig.strategy} · {side}", color="#f0efec", fontsize=11, x=0.03, ha="left")
    fig.text(0.03, 0.915, "zones: blauw = daily, oranje = 4h, groen = 1h (tijden Amsterdam)",
             color="#898781", fontsize=8, ha="left")
    fig.savefig(path, dpi=130, facecolor="#1a1a19", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return path

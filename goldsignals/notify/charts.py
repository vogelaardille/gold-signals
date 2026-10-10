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


def signal_chart(candles, zones, sig, entry_est: float, path, bars: int = 96, max_zones: int = 8):
    c = candles.iloc[-bars:][["open", "high", "low", "close", "volume"]].copy()
    c.index = c.index.tz_convert("Europe/Amsterdam").tz_localize(None)
    lo = min(c["low"].min(), sig.stop, sig.target)
    hi = max(c["high"].max(), sig.stop, sig.target)
    pad = (hi - lo) * 0.05
    lines = dict(hlines=[entry_est, sig.stop, sig.target], colors=["#f0efec", "#e66767", "#0ca30c"],
                 linestyle="--", linewidths=1.2)
    fig, axes = mpf.plot(c, type="candle", style=STYLE, hlines=lines, returnfig=True, figsize=(7, 4.2),
                         ylim=(lo - pad, hi + pad), ylabel="USD", datetime_format="%d-%m %H:%M",
                         xrotation=0, tight_layout=True)
    ax = axes[0]
    vis = zones[(zones["high"] >= lo - pad) & (zones["low"] <= hi + pad)]
    for _, z in vis.sort_values("score", ascending=False).head(max_zones).iterrows():
        ax.axhspan(z["low"], z["high"], color=TF_COLORS.get(z["timeframe"], "#3987e5"), alpha=0.22, lw=0)
    x_end = len(c) - 1
    for y, txt, col in ((entry_est, "entry", "#f0efec"), (sig.stop, "stop", "#e66767"), (sig.target, "target", "#0ca30c")):
        ax.text(x_end + 0.5, y, f" {txt} {y:.2f}", color=col, va="center", fontsize=8)
    side = "LONG" if sig.direction == 1 else "SHORT"
    ax.set_title(f"XAUUSD 1h · {sig.strategy} · {side}  (zones: blauw=daily, oranje=4h, groen=1h)",
                 color="#f0efec", fontsize=9, loc="left")
    fig.savefig(path, dpi=130, facecolor="#1a1a19")
    plt.close(fig)
    return path

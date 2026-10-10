"""Teksten van de vier soorten meldingen. Tijden in Europe/Amsterdam (intern alles UTC).

Elke melding eindigt met de link naar het dashboard. Opmaak: Telegram-HTML (<b>, <i>).
"""
from html import escape

import pandas as pd

DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
LABEL_NL = {"candidate": "CANDIDATE (nog niet bevestigd op hold-out)", "validated": "VALIDATED"}


def local(t, cfg) -> str:
    t = pd.Timestamp(t).tz_convert(cfg["notify"]["timezone"])
    return f"{DAYS[t.weekday()]} {t:%d-%m %H:%M}"


def footer(cfg) -> str:
    url = cfg["notify"].get("dashboard_url")
    return f"\n\n📊 <a href=\"{url}\">Dashboard</a>" if url else ""


def side_nl(d: int) -> str:
    return "LONG (kopen)" if d == 1 else "SHORT (verkopen)"


def zone_alert(z, price: float, dist_atr: float, t, cfg) -> str:
    kind = "support" if z["mid"] < price else "resistance"
    return (f"🟡 <b>ZONE-ALERT</b> · XAUUSD {price:.2f}\n"
            f"Koers is {dist_atr:.1f} ATR van een {kind}-zone "
            f"<b>{z['low']:.2f} – {z['high']:.2f}</b> ({z['timeframes']}, score {z['score']:.1f}, "
            f"{int(z['touches'])} aanrakingen).\n"
            f"<i>Alleen een heads-up, geen entry-advies.</i>\n"
            f"{local(t, cfg)}" + footer(cfg))


def signal(sig, info: dict, entry_est: float, units: float, risk_eur: float, cfg, late: bool = False) -> str:
    d = sig.direction
    risk = d * (entry_est - sig.stop)
    rr = d * (sig.target - entry_est) / risk if risk > 0 else float("nan")
    bt = info.get("backtest", {})
    bt_line = (f"Backtest (walk-forward, na kosten): {bt.get('n', 0)} trades, winrate {bt.get('winrate', 0):.0f}%, "
               f"gem. {bt.get('avg_r', 0):+.2f}R, max DD {bt.get('max_dd_pct', 0):.1f}%") if bt else ""
    return (("⏰ <i>Vertraagd verwerkt</i>\n" if late else "") +
            f"🔔 <b>SIGNAAL</b> · {escape(info.get('title', sig.strategy))}\n"
            f"Label: <b>{LABEL_NL.get(info.get('status'), info.get('status', '?'))}</b>\n\n"
            f"Richting: <b>{side_nl(d)}</b>\n"
            f"Entry: ≈ {entry_est:.2f} (open van de volgende candle)\n"
            f"Stoploss: {sig.stop:.2f}\nTarget: {sig.target:.2f}\nR:R ≈ 1:{rr:.1f}\n"
            f"Virtuele positie: {units:.2f} oz, risico € {risk_eur:.0f} (1% van paper-account)\n\n"
            f"<b>Waarom:</b> {escape(sig.reason)}\n\n{bt_line}\n"
            f"Signaal op candle-slot {local(sig.time, cfg)}" + footer(cfg))


def trade_update(tr: dict, cfg) -> str:
    icon = {"tp": "✅", "sl": "❌", "tijd": "⏱️"}.get(tr["result"], "ℹ️")
    what = {"tp": "TARGET geraakt", "sl": "STOPLOSS geraakt", "tijd": "gesloten (max. duur)",
            "niet_gevuld": "signaal niet gevuld (koers al voorbij stop/target)"}.get(tr["result"], tr["result"])
    if tr["result"] == "niet_gevuld":
        return f"{icon} <b>TRADE-UPDATE</b> · {escape(tr['strategy'])}\n{what}." + footer(cfg)
    return (f"{icon} <b>TRADE-UPDATE</b> · {escape(tr['strategy'])}\n"
            f"{side_nl(int(tr['direction']))} {what}.\n"
            f"Entry {tr['entry']:.2f} → exit {tr['exit']:.2f}\n"
            f"Resultaat: <b>{tr['r']:+.2f}R</b> = € {tr['pnl_eur']:+.0f} (paper)\n"
            f"Paper-equity strategie: € {tr['equity_after']:,.0f}\n"
            f"{local(tr['exit_time'], cfg)}" + footer(cfg))


def system(text: str, cfg) -> str:
    return f"⚠️ <b>SYSTEEM</b>\n{escape(text)}" + footer(cfg)


def weekly(summary: dict, cfg) -> str:
    lines = [f"📅 <b>WEEKOVERZICHT</b> · week {summary['week']}",
             f"Gesloten paper trades: {summary['n_closed']}, totaal {summary['total_r']:+.2f}R "
             f"(€ {summary['pnl_eur']:+.0f})",
             f"Open trades: {summary['n_open']}"]
    for s in summary["per_strategy"]:
        lines.append(f"• {escape(s['strategy'])} ({s['status']}): {s['n']} trades totaal, "
                     f"gem. {s['avg_r']:+.2f}R" + (f" ⚠️ {escape(s['warning'])}" if s.get("warning") else ""))
    if not summary["per_strategy"]:
        lines.append("Geen strategieën actief (geen candidate/validated).")
    lines.append(f"\nKoers: {summary['price']:.2f}. Belangrijkste zones:")
    for z in summary["zones"]:
        lines.append(f"• {z['low']:.2f} – {z['high']:.2f} ({z['timeframes']}, score {z['score']:.1f})")
    return "\n".join(lines) + footer(cfg)

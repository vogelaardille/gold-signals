"""Ronde 2: data ophalen en de kwaliteit controleren.

Draaien: .venv/bin/python -m goldsignals.round2.fetch
Schrijft research/round2/data_quality.md.
"""
import pandas as pd

from goldsignals.config import project_path
from goldsignals.round2 import data


def main():
    end = pd.Timestamp.now(tz="UTC")
    c1 = data.download("1h", 2004, end)
    # 15m is alleen nodig voor familie 3 en 5; tot het einde van de nog ongeopende hold-out
    c15 = data.download("15m", 2005, pd.Timestamp("2020-10-01", tz="UTC"))
    out = ["# Ronde 2 – datakwaliteit", "",
           f"- 1h: {len(c1)} candles, {c1.index[0]} t/m {c1.index[-1]} (UTC, Dukascopy bid)",
           f"- 15m: {len(c15)} candles, {c15.index[0]} t/m {c15.index[-1]}", ""]
    for tf, c in (("1h", c1), ("15m", c15)):
        q = data.quality_report(c, tf)
        out += [f"## {tf}", "", q.to_markdown(index=False), ""]
    for s in ("DFII10", "DTWEXBGS"):
        f = data.fred(s)
        out.append(f"- FRED {s}: {len(f)} waarnemingen, {f.index[0].date()} t/m {f.index[-1].date()}")
    p = project_path("research/round2/data_quality.md")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()

"""Resamplen van 1h-candles naar 4h en daily.

Waarom zelf resamplen in plaats van 4h/daily apart downloaden? Dan zijn alle
timeframes gegarandeerd consistent: de high van een daily candle is precies de
hoogste high van zijn 1h-candles.

Conventies (ook in README):
- Alle tijden in UTC. De index van een candle is zijn (nominale) OPENINGSTIJD.
- Elke candle heeft een kolom 'close_time': het moment waarop hij gesloten is.
  Een candle mag pas gebruikt worden als close_time <= het huidige moment.
- Daily candle: van 17:00 tot 17:00 New York-tijd (goud-conventie). Omdat New
  York zomer- en wintertijd heeft, is dat in UTC 21:00 (zomer) of 22:00 (winter).
  Een daily candle krijgt als datum de dag waarop hij sluit: de handel van
  zondagavond telt dus mee voor de maandag-candle.
- 4h-candles starten op dezelfde sessiegrens: 17, 21, 01, 05, 09, 13 uur NY-tijd.
  Zo passen er precies zes in een daily candle.
"""
import pandas as pd

TF_DURATION = {
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}


def _with_close_time_1h(df_1h: pd.DataFrame) -> pd.DataFrame:
    out = df_1h.copy()
    out["close_time"] = out.index + TF_DURATION["1h"]
    return _same_time_unit(out)


def _same_time_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Alle tijden in nanoseconden. Anders kan de ene bron ms en de andere us geven,
    en dan worden tijdkolommen bij samenvoegen een onhandig 'object'-type."""
    df.index = df.index.as_unit("ns")
    df["close_time"] = df["close_time"].dt.as_unit("ns")
    return df


def _localize(naive: pd.DatetimeIndex, tz: str) -> pd.DatetimeIndex:
    """Lokale NY-kloktijd terug naar UTC. De markt is dicht tijdens de zomertijd-
    wissel (zondagnacht), dus ambiguous/nonexistent komt in de praktijk niet voor."""
    return naive.tz_localize(tz, ambiguous=True, nonexistent="shift_forward").tz_convert("UTC")


def resample(df_1h: pd.DataFrame, tf: str, session_tz: str = "America/New_York",
             session_close_hour: int = 17) -> pd.DataFrame:
    """Zet 1h-candles om naar timeframe tf ("1h", "4h" of "1d").

    Truc: we rekenen in New York-kloktijd en schuiven die zo op dat 17:00 NY
    middernacht wordt. Dan is een daily candle gewoon een kalenderdag en een 4h-candle
    een blok van 4 uur vanaf middernacht.
    """
    if tf == "1h":
        return _with_close_time_1h(df_1h)
    if tf not in TF_DURATION:
        raise ValueError(f"Onbekende timeframe: {tf}")

    shift = pd.Timedelta(hours=24 - session_close_hour)  # 17:00 -> 00:00
    local = df_1h.index.tz_convert(session_tz).tz_localize(None)
    shifted = local + shift
    bucket = shifted.floor("D") if tf == "1d" else shifted.floor("4h")

    open_local = bucket - shift
    open_utc = _localize(pd.DatetimeIndex(open_local), session_tz)
    close_utc = _localize(pd.DatetimeIndex(open_local + TF_DURATION[tf]), session_tz)

    grouped = df_1h.assign(close_time=close_utc).groupby(open_utc)
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        close_time=("close_time", "max"),
    )
    out.index.name = "time"
    return _same_time_unit(out)


def build_timeframes(df_1h: pd.DataFrame, cfg: dict, as_of: pd.Timestamp = None) -> dict:
    """Maak alle timeframes uit config, met ALLEEN candles die op as_of gesloten waren.

    Dit is de kern van 'geen lookahead':
    1. eerst gooien we alle 1h-candles weg die na as_of sluiten;
    2. daarna resamplen we, en gooien we 4h/daily-candles weg die nog lopen
       (close_time > as_of). Een half gevormde daily candle telt dus niet mee.
    Zonder as_of nemen we het sluitmoment van de laatste 1h-candle.
    """
    closes_1h = df_1h.index + TF_DURATION["1h"]
    if as_of is None:
        as_of = closes_1h[-1]
    df_1h = df_1h[closes_1h <= as_of]

    d = cfg["data"]
    frames = {}
    for tf in cfg["timeframes"]:
        f = resample(df_1h, tf, d["session_tz"], d["session_close_hour"])
        frames[tf] = f[f["close_time"] <= as_of]
    return frames

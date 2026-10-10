"""Telegram Bot API: berichten en foto's versturen.

Het token en chat-id komen ALLEEN uit omgevingsvariabelen (lokaal uit .env, in GitHub
Actions uit GitHub Secrets). Ze worden nooit gelogd of geprint: foutmeldingen worden
gefilterd met `redact`.
"""
import os
import time
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def load_dotenv(path: Path = None):
    """Minimale .env-lezer (KEY=waarde per regel). Bestaande omgevingsvariabelen winnen."""
    from goldsignals.config import PROJECT_ROOT
    path = path or PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def credentials():
    load_dotenv()
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def redact(text: str) -> str:
    """Haal het token uit een tekst (bijv. een foutmelding met de URL erin)."""
    token, chat = credentials()
    for secret in (token, chat):
        if secret:
            text = str(text).replace(secret, "***")
    return text


class TelegramError(RuntimeError):
    pass


def _call(method: str, data: dict, files: dict = None, retries: int = 3) -> dict:
    token, _ = credentials()
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN ontbreekt (.env of GitHub Secret)")
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=30)
            body = r.json()
            if body.get("ok"):
                return body
            if r.status_code == 429:                 # te veel berichten: even wachten
                time.sleep(body.get("parameters", {}).get("retry_after", 5))
                continue
            last = f"{r.status_code}: {body.get('description')}"
            if 400 <= r.status_code < 500:
                break                                 # fout in het verzoek; opnieuw proberen helpt niet
        except (requests.RequestException, ValueError) as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (attempt + 1))
    raise TelegramError(redact(f"Telegram {method} mislukt: {last}"))


def send_message(text: str) -> dict:
    _, chat = credentials()
    if not chat:
        raise TelegramError("TELEGRAM_CHAT_ID ontbreekt (.env of GitHub Secret)")
    return _call("sendMessage", {"chat_id": chat, "text": text, "parse_mode": "HTML",
                                 "disable_web_page_preview": "true"})


def send_photo(png_path: str, caption: str) -> dict:
    _, chat = credentials()
    if not chat:
        raise TelegramError("TELEGRAM_CHAT_ID ontbreekt (.env of GitHub Secret)")
    # Telegram staat max 1024 tekens in een foto-bijschrift toe
    with open(png_path, "rb") as f:
        return _call("sendPhoto", {"chat_id": chat, "caption": caption[:1024], "parse_mode": "HTML"},
                     files={"photo": f})


def get_updates() -> list:
    """Voor het ophalen van het chat-id nadat je de bot een bericht stuurde."""
    return _call("getUpdates", {}).get("result", [])

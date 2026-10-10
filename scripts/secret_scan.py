"""Secret-scan: draait voor elke publicatie (dashboard, state, push naar het openbare repo).

Zoekt naar:
- Telegram-bottokens (patroon en de echte waarde uit de omgeving/.env), chat-id;
- GitHub-tokens, private keys, AWS-sleutels;
- e-mailadressen (behalve GitHub-noreply en voorbeeld-adressen);
- lokale paden (thuismappen op Mac/Linux/Windows) en .env-bestanden.

Gebruik:
  python scripts/secret_scan.py            # alle bestanden die git zou committen
  python scripts/secret_scan.py site state # alleen deze mappen
Exitcode 1 als er iets gevonden is. Gevonden waarden worden NIET geprint (alleen
bestand, regel en soort), zodat de scan zelf niets lekt.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PATTERNS = {
    "telegram-token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "lokaal-pad": re.compile(r"(/Users/[A-Za-z0-9._-]+|/home/(?!runner\b)[A-Za-z0-9._-]+|C:\\\\Users\\\\)"),
}
EMAIL_OK = re.compile(r"(@users\.noreply\.github\.com|noreply@anthropic\.com|@example\.(com|org))$")
SKIP_SUFFIX = {".parquet", ".png", ".jpg", ".pyc", ".ico"}


def secret_values() -> dict:
    from goldsignals.notify.telegram import load_dotenv
    load_dotenv()
    vals = {}
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        v = os.environ.get(k)
        if v and len(v) >= 5:
            vals[k] = v
    return vals


def files_to_scan(args) -> list:
    if args:
        out = []
        for a in args:
            p = Path(a)
            out += [f for f in p.rglob("*") if f.is_file() and ".git" not in f.parts] if p.is_dir() else [p]
        return out
    # Alles wat git zou committen: gevolgde + nieuwe, niet-genegeerde bestanden
    res = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / f for f in res.stdout.splitlines() if f]


def scan(files) -> list:
    secrets = secret_values()
    findings = []
    for f in files:
        if f.suffix in SKIP_SUFFIX:
            continue
        if f.name == ".env":
            findings.append((f, 0, ".env-bestand hoort niet gepubliceerd te worden"))
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for name, value in secrets.items():
                if value in line:
                    findings.append((f, n, f"echte waarde van {name}"))
            for kind, pat in PATTERNS.items():
                for m in pat.finditer(line):
                    if kind == "email" and EMAIL_OK.search(m.group(0)):
                        continue
                    findings.append((f, n, kind))
    return findings


def main(args) -> int:
    files = files_to_scan(args)
    found = scan(files)
    print(f"Secret-scan: {len(files)} bestanden gescand.")
    for f, n, kind in found:
        try:
            rel = f.resolve().relative_to(ROOT)
        except ValueError:
            rel = f.name
        print(f"  GEVONDEN: {rel}:{n}  ({kind})")
    print("Resultaat:", "SCHOON" if not found else f"{len(found)} probleem/problemen")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

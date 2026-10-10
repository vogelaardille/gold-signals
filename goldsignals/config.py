"""Inlezen van config.yaml.

We houden de config bewust als een gewone dict: makkelijk te lezen en aan te passen,
zonder extra classes.
"""
from pathlib import Path

import yaml

# Projectroot = de map boven goldsignals/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config(path=DEFAULT_CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(relative: str) -> Path:
    """Maak een pad uit de config absoluut t.o.v. de projectroot."""
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p

"""Config loading. Everything tunable lives in config.toml next to the db."""
from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HOME = Path(__file__).resolve().parent.parent
CONFIG_NAME = "config.toml"


@dataclass
class Config:
    home: Path
    raw: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.home / self.raw.get("storage", {}).get("db", "radar.db")

    @property
    def out_dir(self) -> Path:
        d = self.home / self.raw.get("storage", {}).get("out_dir", "out")
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def cache_dir(self) -> Path:
        d = self.home / ".cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def section(self, name: str) -> dict:
        return self.raw.get(name, {}) or {}

    def get(self, path: str, default=None):
        cur = self.raw
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    # -- profile ---------------------------------------------------------
    @property
    def interests(self) -> dict[str, float]:
        """Weighted keywords describing what you actually want to work on."""
        return {k.lower(): float(v) for k, v in self.section("interests").items()}

    @property
    def watchlist(self) -> list[str]:
        users = self.get("sources.github_starred.users", []) or []
        return [u.strip() for u in users if u.strip()]

    @property
    def profile(self) -> str:
        return (self.get("profile.description", "") or "").strip()


def github_token() -> str | None:
    """Env first, then whatever `gh` is already logged in as."""
    for var in ("RADAR_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        out = subprocess.run(
            [gh, "auth", "token"], capture_output=True, text=True, timeout=15
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load(home: Path | None = None) -> Config:
    home = Path(home or os.environ.get("RADAR_HOME") or DEFAULT_HOME)
    path = home / CONFIG_NAME
    if not path.exists():
        raise SystemExit(f"No config at {path}\nRun:  python -m radar init")
    with open(path, "rb") as fh:
        return Config(home=home, raw=tomllib.load(fh))

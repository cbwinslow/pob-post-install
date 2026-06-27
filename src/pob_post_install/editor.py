from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class ConfigEditor:
    @staticmethod
    def read(path: Path) -> str:
        return path.read_text(errors="ignore")

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    @staticmethod
    def resolve(pkg_id: str) -> list[Path]:
        home = Path.home()
        candidates = [
            home / ".config" / pkg_id,
            home / f".{pkg_id}",
            home / ".local" / "share" / pkg_id,
        ]
        found = []
        for p in candidates:
            if p.exists():
                found.append(p)
        return found

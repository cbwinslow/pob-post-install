from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TimeTravel:
    STATE_DIR = Path.home() / ".local" / "share" / "pob-post-install" / "state"

    @classmethod
    def list_receipts(cls) -> list[Path]:
        if not cls.STATE_DIR.exists():
            return []
        return sorted(cls.STATE_DIR.glob("current-*.json"), reverse=True)

    @classmethod
    def load(cls, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text())

    @classmethod
    def diff_receipts(cls, a: Path, b: Path) -> dict[str, Any]:
        data_a = cls.load(a)
        data_b = cls.load(b)
        items_a = {i["id"]: i for i in data_a.get("items", [])}
        items_b = {i["id"]: i for i in data_b.get("items", [])}
        added = [i for i in items_b.values() if i["id"] not in items_a]
        removed = [i for i in items_a.values() if i["id"] not in items_b]
        changed = []
        for pkg_id, item_b in items_b.items():
            item_a = items_a.get(pkg_id)
            if not item_a:
                continue
            if item_a.get("ok") != item_b.get("ok"):
                changed.append({"id": pkg_id, "from": item_a, "to": item_b})
        return {
            "run_a": data_a.get("run_id"),
            "run_b": data_b.get("run_id"),
            "added": added,
            "removed": removed,
            "changed": changed,
        }

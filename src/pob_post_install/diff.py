from __future__ import annotations

from typing import Any


class DiffEngine:
    @staticmethod
    def compare(desired_ids: set[str], installed: dict[str, Any]) -> dict[str, Any]:
        installed_ids = {p.get("name", p.get("id", "")) for p in installed.get("apt", [])}
        installed_ids |= {p.get("name", "") for p in installed.get("python", [])}
        installed_ids |= {p.get("name", "") for p in installed.get("node", [])}
        installed_ids |= {p.get("name", "") for p in installed.get("snap", [])}
        installed_ids |= {p.get("name", "") for p in installed.get("flatpak", [])}
        missing = sorted(desired_ids - installed_ids)
        extra = sorted(installed_ids - desired_ids)
        return {
            "desired": sorted(desired_ids),
            "installed": sorted(installed_ids),
            "missing": missing,
            "extra": extra,
            "summary": {
                "desired_count": len(desired_ids),
                "installed_count": len(installed_ids),
                "missing_count": len(missing),
                "extra_count": len(extra),
            },
        }

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class UpdateChecker:
    @staticmethod
    async def check(pkg_id: str, provider: str, current_version: str | None = None) -> dict[str, Any]:
        if provider == "apt":
            return UpdateChecker._check_apt(pkg_id)
        if provider == "npm":
            return UpdateChecker._check_npm(pkg_id)
        if provider == "pip":
            return UpdateChecker._check_pip(pkg_id)
        return {
            "package": pkg_id,
            "provider": provider,
            "update_available": False,
            "latest": None,
            "current": current_version,
        }

    @staticmethod
    def _check_apt(pkg_id: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["apt-cache", "policy", pkg_id],
                capture_output=True,
                text=True,
                check=False,
            )
            out = result.stdout
            candidate = next((line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("Candidate: ")), None)
            return {
                "package": pkg_id,
                "provider": "apt",
                "update_available": bool(candidate),
                "latest": candidate,
                "current": None,
            }
        except Exception as e:
            return {"package": pkg_id, "provider": "apt", "update_available": False, "latest": None, "current": None, "error": str(e)}

    @staticmethod
    def _check_npm(pkg_id: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["npm", "view", pkg_id, "version"],
                capture_output=True,
                text=True,
                check=False,
            )
            latest = result.stdout.strip()
            return {
                "package": pkg_id,
                "provider": "npm",
                "update_available": bool(latest),
                "latest": latest,
                "current": None,
            }
        except Exception as e:
            return {"package": pkg_id, "provider": "npm", "update_available": False, "latest": None, "current": None, "error": str(e)}

    @staticmethod
    def _check_pip(pkg_id: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["pip", "index", "versions", pkg_id],
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "package": pkg_id,
                "provider": "pip",
                "update_available": result.returncode == 0,
                "latest": result.stdout.strip().splitlines()[0] if result.stdout.strip() else None,
                "current": None,
            }
        except Exception as e:
            return {"package": pkg_id, "provider": "pip", "update_available": False, "latest": None, "current": None, "error": str(e)}

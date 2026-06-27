from __future__ import annotations

from typing import Any


class HealthChecker:
    @staticmethod
    def score(pkg_id: str, provider: str) -> dict[str, Any]:
        score = 50
        notes: list[str] = []
        if provider == "apt":
            score += 30
            notes.append("APT package: maintained by distro")
        if provider == "npm":
            score += 10
            notes.append("NPM package: verify upstream maintenance")
        if provider == "pip":
            score += 10
            notes.append("Python package: verify PyPI metadata")
        if provider == "github_repo":
            score -= 10
            notes.append("GitHub repo: check stars and last commit")
        return {
            "package": pkg_id,
            "provider": provider,
            "score": max(0, min(100, score)),
            "notes": notes,
            "cve_placeholder": "CVE lookup not yet implemented",
        }

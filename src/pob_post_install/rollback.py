from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pob_post_install.models.package import Package
from pob_post_install.receipts import ReceiptLogger


class RollbackManager:
    STATE_DIR = Path("/var/lib/pob-post-install")
    FALLBACK_STATE_DIR = Path.home() / ".local" / "share" / "pob-post-install" / "state"

    def __init__(self, logger: ReceiptLogger) -> None:
        self.logger = logger
        self._rollback_plan: list[dict[str, Any]] = []
        self._state_dir = self._writable_dir()

    def _writable_dir(self) -> Path:
        primary = self.STATE_DIR
        fallback = self.FALLBACK_STATE_DIR
        try:
            test = primary / ".write_test"
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text("test")
            test.unlink()
            return primary
        except (PermissionError, OSError):
            return fallback

    def plan_apt_remove(self, pkg: Package) -> None:
        if pkg.provider.value != "apt":
            return
        self._rollback_plan.append(
            {
                "type": "apt",
                "id": pkg.id,
                "name": pkg.name,
                "cmd": ["apt-get", "remove", "-y", pkg.id],
                "purge_cmd": ["apt-get", "purge", "-y", pkg.id],
            }
        )

    def plan_docker_remove(self, pkg: Package) -> None:
        if pkg.provider.value != "script":
            return
        cmd_str = " ".join(str(a) for a in pkg.install_args)
        if "docker pull" in cmd_str:
            images = [a for a in pkg.install_args if "docker pull" in " ".join(str(x) for x in pkg.install_args)]
            for image_arg in pkg.install_args:
                s = str(image_arg)
                if s.startswith("docker pull "):
                    image = s[len("docker pull "):]
                    self._rollback_plan.append(
                        {
                            "type": "docker",
                            "id": pkg.id,
                            "name": pkg.name,
                            "image": image,
                            "cmd": ["docker", "rmi", image],
                        }
                    )
                    break

    def plan_github_remove(self, pkg: Package) -> None:
        if pkg.provider.value != "github_repo":
            return
        dest = pkg.config.get("clone_dest", f"/opt/{pkg.id}")
        self._rollback_plan.append(
            {
                "type": "github_repo",
                "id": pkg.id,
                "name": pkg.name,
                "dest": dest,
                "cmd": ["rm", "-rf", dest],
            }
        )

    def execute_rollback(self, dry_run: bool = False) -> tuple[bool, str]:
        if not self._rollback_plan:
            return True, "Nothing to roll back."
        # Reverse order: last installed, first removed
        results = []
        success = True
        for step in reversed(self._rollback_plan):
            if dry_run:
                results.append(f"[dry-run] {' '.join(step['cmd'])}")
                continue
            try:
                result = subprocess.run(
                    step["cmd"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                ok = result.returncode == 0
                out = (result.stdout or result.stderr).strip()
                results.append(f"[{ 'OK' if ok else 'FAIL' }] {step['name']}: {out[:200]}")
                if not ok:
                    success = False
            except Exception as e:
                results.append(f"[ERR] {step['name']}: {e}")
                success = False
        return success, "\n".join(results)

    def save(self, receipt_path: Path | None = None) -> None:
        if receipt_path is None:
            receipt_path = self._state_dir / f"rollback-{self.logger.run_id}.json"
        payload = {
            "run_id": self.logger.run_id,
            "plan": self._rollback_plan,
        }
        receipt_path.write_text(json.dumps(payload, indent=2))

    @staticmethod
    def load(receipt_path: Path) -> dict[str, Any]:
        return json.loads(receipt_path.read_text())

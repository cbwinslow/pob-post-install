from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from pob_post_install.models.package import Package


class ReceiptLogger:
    LOG_DIR = Path("/var/log/pob-post-install")
    INSTALL_HEADER = "/var/log/pob-post-install/install.log"
    STATE_DIR = Path("/var/lib/pob-post-install")
    FALLBACK_LOG_DIR = Path.home() / ".local" / "share" / "pob-post-install" / "logs"
    FALLBACK_STATE_DIR = Path.home() / ".local" / "share" / "pob-post-install" / "state"

    def __init__(self) -> None:
        self._log_dir = self._writable_dir(self.LOG_DIR, self.FALLBACK_LOG_DIR)
        self._state_dir = self._writable_dir(self.STATE_DIR, self.FALLBACK_STATE_DIR)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._run_id = time.strftime("%Y%m%d-%H%M%S")
        self._receipt: dict[str, Any] = {
            "run_id": self._run_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "finished_at": None,
            "host": os.uname().nodename,
            "user": os.environ.get("SUDO_USER", os.environ.get("USER", "unknown")),
            "items": [],
            "apt_transaction": None,
            "docker_images_before": [],
            "summary": {
                "total": 0,
                "ok": 0,
                "fail": 0,
                "skipped": 0,
            },
        }

    @staticmethod
    def _writable_dir(primary: Path, fallback: Path) -> Path:
        try:
            test = primary / ".write_test"
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text("test")
            test.unlink()
            return primary
        except (PermissionError, OSError):
            return fallback

    @property
    def run_id(self) -> str:
        return self._run_id

    def record_snapshot(self) -> None:
        self._receipt["docker_images_before"] = self._docker_images()

    def set_apt_transaction(self, transaction_id: str | None) -> None:
        self._receipt["apt_transaction"] = transaction_id

    def record_item(self, pkg: Package, ok: bool, message: str, dry_run: bool = False) -> None:
        entry = {
            "id": pkg.id,
            "provider": pkg.provider.value,
            "ok": ok,
            "message": message[:500],
            "dry_run": dry_run,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._receipt["items"].append(entry)
        self._receipt["summary"]["total"] += 1
        if dry_run:
            self._receipt["summary"]["skipped"] += 1
        elif ok:
            self._receipt["summary"]["ok"] += 1
        else:
            self._receipt["summary"]["fail"] += 1
        self._flush()

    def finalize(self) -> dict[str, Any]:
        self._receipt["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._flush()
        receipt_path = self._log_dir / f"{self._run_id}.json"
        receipt_path.write_text(json.dumps(self._receipt, indent=2))
        header_path = self._log_dir / "install.log"
        with header_path.open("a") as f:
            f.write(f"{self._run_id}\t{self._receipt['started_at']}\t{self._receipt['finished_at']}\t{self._receipt['summary']['total']}\t{self._receipt['summary']['ok']}\t{self._receipt['summary']['fail']}\n")
        return self._receipt

    def _flush(self) -> None:
        state_path = self._state_dir / f"current-{self._run_id}.json"
        state_path.write_text(json.dumps(self._receipt, indent=2))

    def _docker_images(self) -> list[str]:
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            pass
        return []

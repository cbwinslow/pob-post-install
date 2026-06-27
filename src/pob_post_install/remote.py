from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class RemoteManager:
    @staticmethod
    def generate_inventory(targets: list[str]) -> str:
        lines = ["[pob_targets]"]
        for t in targets:
            lines.append(t)
        return "\n".join(lines) + "\n"

    @staticmethod
    def run_adhoc(host: str, module: str, args: str) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                ["ansible", host, "-m", module, "-a", args, "-u", "root", "-b"],
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "host": host,
                "module": module,
                "args": args,
                "ok": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as e:
            return {"host": host, "module": module, "args": args, "ok": False, "error": str(e)}

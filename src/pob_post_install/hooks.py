from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional


class HookManager:
    HOOK_DIR = Path.home() / ".config" / "pob-post-install" / "hooks"

    def __init__(self) -> None:
        self.HOOK_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, pkg_id: Optional[str], phase: str) -> None:
        """
        phase: pre or post
        Runs global hooks first, then package-specific hooks.
        """
        candidates = [
            self.HOOK_DIR / f"global-{phase}.sh",
            self.HOOK_DIR / f"{pkg_id}-{phase}.sh" if pkg_id else None,
        ]
        for hook_path in candidates:
            if not hook_path or not hook_path.exists():
                continue
            if not os.access(hook_path, os.X_OK):
                hook_path.chmod(0o755)
            try:
                subprocess.run(
                    [str(hook_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception:
                pass

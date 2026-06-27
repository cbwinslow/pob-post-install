from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


class PluginRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}

    def register_provider(self, name: str, provider: Any) -> None:
        self._providers[name] = provider

    def load_plugin(self, path: Path) -> None:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            return
        mod = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "register"):
            mod.register(self)

    def load_plugins_from(self, directory: Path) -> None:
        if not directory.exists():
            return
        for path in directory.glob("*.py"):
            if path.name.startswith("_"):
                continue
            self.load_plugin(path)

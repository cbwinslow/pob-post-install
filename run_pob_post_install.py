#!/usr/bin/env python3
"""POB Post-Install TUI runner."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pob_post_install.registry import load_packages
from pob_post_install.main import build_app


def main() -> None:
    packages_dir = Path(__file__).parent / "packages"
    if not packages_dir.exists():
        raise SystemExit(f"Packages directory not found: {packages_dir}")
    all_packages: list = []
    for path in sorted(packages_dir.glob("*.toml")):
        all_packages.extend(load_packages(path))
    if not all_packages:
        raise SystemExit("No packages configured.")
    app = build_app(all_packages)
    app.run()


if __name__ == "__main__":
    main()

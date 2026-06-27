from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Optional

from pob_post_install.models.package import Category, Package, ProviderType


def _provider(value: str) -> ProviderType:
    return ProviderType(value.strip().lower())


def _category(value: str) -> Category:
    return Category(value.strip())


def load_packages(path: Path) -> list[Package]:
    with path.open("rb") as f:
        data = tomllib.load(f)

    packages: list[Package] = []
    for item in data.get("package", []):
        packages.append(
            Package(
                id=item["id"],
                name=item.get("name", item["id"]),
                description=item.get("description", ""),
                category=_category(item["category"]),
                provider=_provider(item["provider"]),
                install_args=item.get("install_args", [item["id"]]),
                verify_cmd=item.get("verify_cmd"),
                dependencies=item.get("dependencies", []),
                conflicts=item.get("conflicts", []),
                post_install_msg=item.get("post_install_msg"),
                config=item.get("config", {}),
                enabled=item.get("enabled", True),
            )
        )
    return packages

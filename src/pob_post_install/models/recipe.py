from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExportFormat(str, Enum):
    SHELL = "shell"
    ANSIBLE = "ansible"
    DOCKER_COMPOSE = "docker_compose"
    PULUMI = "pulumi"
    OPENTOFU = "opentofu"


@dataclass
class Recipe:
    name: str
    description: str = ""
    packages: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "packages": self.packages,
            "meta": self.meta,
        }

    @staticmethod
    def from_dict(data: dict) -> Recipe:
        return Recipe(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            packages=data.get("packages", []),
            meta=data.get("meta", {}),
        )

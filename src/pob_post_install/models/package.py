from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderType(str, Enum):
    APT = "apt"
    UV = "uv"
    NPM = "npm"
    ANSIBLE = "ansible"
    PULUMI = "pulumi"
    OPENTOFU = "opentofu"
    SCRIPT = "script"
    GITHUB_REPO = "github_repo"


class Category(str, Enum):
    SYSTEM = "System"
    SECURITY = "Security"
    TERMINAL = "Terminal"
    NETWORKING = "Networking"
    DEV = "Dev"
    LANGUAGES = "Languages"
    DATABASES = "Databases"
    CONTAINERS = "Containers"
    DOCKER = "Docker"
    WEB = "Web"
    AI = "AI"
    IAC = "IaC"
    MONITORING = "Monitoring"
    GITHUB = "GitHub"
    CUSTOM = "Custom"
    DISCOVERED = "Discovered"


@dataclass
class Package:
    id: str
    name: str
    description: str
    category: Category
    provider: ProviderType
    install_args: list[str] = field(default_factory=list)
    verify_cmd: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    post_install_msg: Optional[str] = None
    config: dict = field(default_factory=dict)
    enabled: bool = True
    status: str = "pending"

    def render_label(self) -> str:
        return f"{self.name} — {self.description}"

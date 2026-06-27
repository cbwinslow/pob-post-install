from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pob_post_install.models.recipe import Recipe, ExportFormat


class RecipeExporter:
    @staticmethod
    def export(recipe: Recipe, fmt: ExportFormat) -> str:
        if fmt == ExportFormat.SHELL:
            return RecipeExporter._to_shell(recipe)
        if fmt == ExportFormat.ANSIBLE:
            return RecipeExporter._to_ansible(recipe)
        if fmt == ExportFormat.DOCKER_COMPOSE:
            return RecipeExporter._to_compose(recipe)
        if fmt == ExportFormat.PULUMI:
            return RecipeExporter._to_pulumi(recipe)
        if fmt == ExportFormat.OPENTOFU:
            return RecipeExporter._to_opentofu(recipe)
        raise ValueError(f"Unsupported format: {fmt}")

    @staticmethod
    def save(recipe: Recipe, fmt: ExportFormat, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(RecipeExporter.export(recipe, fmt))

    @staticmethod
    def _to_shell(recipe: Recipe) -> str:
        lines = [
            "#!/usr/bin/env bash",
            f"# Recipe: {recipe.name}",
            f"# {recipe.description}",
            "set -euo pipefail",
            "",
        ]
        for pkg in recipe.packages:
            provider = pkg.get("provider", "script")
            pkg_id = pkg.get("id", pkg.get("name", "unknown"))
            install_args = pkg.get("install_args", [pkg_id])
            if provider == "apt":
                lines.append(f"apt-get install -y {' '.join(install_args)}")
            elif provider == "npm":
                lines.append(f"npm install -g {' '.join(install_args)}")
            elif provider == "uv":
                lines.append(f"uv tool install {' '.join(install_args)}")
            elif provider == "script":
                lines.append(" ".join(install_args))
            else:
                lines.append(f"# Unsupported provider: {provider} for {pkg_id}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _to_ansible(recipe: Recipe) -> str:
        tasks = []
        for pkg in recipe.packages:
            provider = pkg.get("provider", "script")
            pkg_id = pkg.get("id", pkg.get("name", "unknown"))
            install_args = pkg.get("install_args", [pkg_id])
            if provider == "apt":
                tasks.append({
                    "name": f"Install {pkg_id}",
                    "apt": {"name": install_args[0], "state": "present"},
                })
            elif provider == "npm":
                tasks.append({
                    "name": f"Install npm global {pkg_id}",
                    "npm": {"name": install_args[0], "global": True},
                })
            elif provider == "script":
                tasks.append({
                    "name": f"Run script for {pkg_id}",
                    "shell": " ".join(install_args),
                })
            else:
                tasks.append({
                    "name": f"Skip {pkg_id}",
                    "debug": {"msg": f"Unsupported provider {provider}"},
                })
        playbook = {
            "name": recipe.name,
            "hosts": "all",
            "become": True,
            "tasks": tasks,
        }
        return json.dumps({"playbook": [playbook]}, indent=2) + "\n"

    @staticmethod
    def _to_compose(recipe: Recipe) -> str:
        services = {}
        for pkg in recipe.packages:
            provider = pkg.get("provider", "script")
            pkg_id = pkg.get("id", pkg.get("name", "unknown"))
            install_args = pkg.get("install_args", [])
            cmd = " ".join(install_args) if install_args else None
            if provider == "script" and cmd and "docker" in cmd:
                services[pkg_id] = {
                    "image": cmd.split()[-1] if cmd else pkg_id,
                    "command": cmd,
                }
            else:
                services[pkg_id] = {
                    "image": pkg_id,
                    "command": cmd or ["sleep", "infinity"],
                }
        compose = {"version": "3.8", "services": services}
        import yaml
        return yaml.dump(compose, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _to_pulumi(recipe: Recipe) -> str:
        lines = [
            "import subprocess",
            "",
            "def install_pkg(pkg_id, install_args):",
            "    cmd = install_args or [pkg_id]",
            "    subprocess.run(cmd, check=True)",
            "",
            "",
        ]
        for pkg in recipe.packages:
            pkg_id = pkg.get("id", pkg.get("name", "unknown"))
            install_args = pkg.get("install_args", [pkg_id])
            lines.append(f"install_pkg({pkg_id!r}, {install_args!r})")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _to_opentofu(recipe: Recipe) -> str:
        lines = [
            'terraform {',
            '  required_providers {',
            '    local = { source = "hashicorp/local", version = "~> 2.4" }',
            "  }",
            "}",
            "",
            'provider "local" {}',
            "",
        ]
        for idx, pkg in enumerate(recipe.packages, start=1):
            pkg_id = pkg.get("id", pkg.get("name", f"pkg_{idx}"))
            install_args = pkg.get("install_args", [pkg_id])
            lines.extend([
                f'resource "local_file" "{pkg_id}_script" {{',
                f'  content  = <<-EOT',
                f"    {' '.join(install_args)}",
                f'  EOT',
                f'  filename = "/tmp/pob-recipe-{pkg_id}.sh"',
                "}",
                "",
            ])
        return "\n".join(lines) + "\n"

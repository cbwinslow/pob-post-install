from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from textual.widgets import Static


class InventoryCollector:
    async def collect(self) -> dict[str, Any]:
        return {
            "os": await self._get_os_info(),
            "apt": await self._get_apt_packages(),
            "python": await self._get_python_packages(),
            "node": await self._get_node_packages(),
            "docker": await self._get_docker_inventory(),
            "podman": await self._get_podman_inventory(),
            "snap": await self._get_snap_packages(),
            "flatpak": await self._get_flatpak_packages(),
            "services": await self._get_systemd_services(),
            "binaries": await self._get_local_binaries(),
        }

    async def _run(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout or b"").decode("utf-8", errors="ignore").strip()
            err = (stderr or b"").decode("utf-8", errors="ignore").strip()
            return proc.returncode == 0, out or err
        except Exception as e:
            return False, str(e)

    async def _get_os_info(self) -> dict[str, str]:
        info: dict[str, str] = {}
        ok, out = await self._run(["uname", "-a"])
        if ok:
            info["kernel"] = out
        ok, out = await self._run(["lsb_release", "-d"])
        if ok:
            parts = out.split(":", 1)
            if len(parts) == 2:
                info["distro"] = parts[1].strip()
        ok, out = await self._run(["lsb_release", "-r"])
        if ok:
            parts = out.split(":", 1)
            if len(parts) == 2:
                info["version"] = parts[1].strip()
        info["hostname"] = os.uname().nodename
        return info

    async def _get_apt_packages(self) -> list[dict[str, str]]:
        ok, out = await self._run(["dpkg-query", "-W", "-f", "${Package}\t${Version}\t${Status}\n"])
        if not ok:
            return []
        packages: list[dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and "install ok installed" in parts[2]:
                packages.append({
                    "name": parts[0],
                    "version": parts[1],
                    "status": parts[2].strip(),
                })
        return packages

    async def _get_python_packages(self) -> list[dict[str, str]]:
        packages: list[dict[str, str]] = []
        ok, out = await self._run(["python3", "-m", "pip", "list", "--format=freeze"])
        if ok:
            for line in out.splitlines():
                if "==" in line:
                    name, version = line.split("==", 1)
                    packages.append({"name": name.strip(), "version": version.strip(), "source": "pip"})
        ok, out = await self._run(["uv", "tool", "list"])
        if ok:
            for line in out.splitlines()[1:]:
                parts = line.split()
                if parts:
                    packages.append({"name": parts[0], "version": parts[1] if len(parts) > 1 else "?", "source": "uv"})
        return packages

    async def _get_node_packages(self) -> list[dict[str, str]]:
        ok, out = await self._run(["npm", "list", "-g", "--depth=0", "--json"])
        if not ok:
            return []
        packages: list[dict[str, str]] = []
        try:
            import json
            data = json.loads(out)
            deps = data.get("dependencies", {})
            for name, meta in deps.items():
                packages.append({
                    "name": name,
                    "version": meta.get("version", "?"),
                    "source": "npm",
                })
        except Exception:
            pass
        return packages

    async def _get_docker_inventory(self) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = {"images": [], "containers": []}
        ok, out = await self._run(["docker", "images", "--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}"])
        if ok:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    result["images"].append({
                        "repository": parts[0],
                        "tag": parts[1],
                        "size": parts[2],
                    })
        ok, out = await self._run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"])
        if ok:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    result["containers"].append({
                        "name": parts[0],
                        "image": parts[1],
                        "status": parts[2],
                    })
        return result

    async def _get_podman_inventory(self) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = {"images": [], "containers": []}
        ok, out = await self._run(["podman", "images", "--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}"])
        if ok:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    result["images"].append({
                        "repository": parts[0],
                        "tag": parts[1],
                        "size": parts[2],
                    })
        ok, out = await self._run(["podman", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"])
        if ok:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    result["containers"].append({
                        "name": parts[0],
                        "image": parts[1],
                        "status": parts[2],
                    })
        return result

    async def _get_snap_packages(self) -> list[dict[str, str]]:
        ok, out = await self._run(["snap", "list"])
        if not ok:
            return []
        packages: list[dict[str, str]] = []
        lines = out.splitlines()
        if not lines:
            return []
        headers = lines[0].split()
        for line in lines[1:]:
            parts = line.split()
            pkg: dict[str, str] = {}
            for i, h in enumerate(headers[:4]):
                pkg[h.lower()] = parts[i] if i < len(parts) else ""
            packages.append(pkg)
        return packages

    async def _get_flatpak_packages(self) -> list[dict[str, str]]:
        ok, out = await self._run(["flatpak", "list", "--app", "--columns=application,version,branch"])
        if not ok:
            return []
        packages: list[dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                packages.append({
                    "name": parts[0],
                    "version": parts[1],
                    "branch": parts[2],
                })
        return packages

    async def _get_systemd_services(self) -> list[dict[str, str]]:
        ok, out = await self._run(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain", "--no-legend"])
        if not ok:
            return []
        services: list[dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                services.append({
                    "unit": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                })
        return services

    async def _get_local_binaries(self) -> list[dict[str, str]]:
        binaries: list[dict[str, str]] = []
        search_paths = ["/usr/local/bin", "/usr/bin", "/bin", Path.home() / ".local" / "bin"]
        for base in search_paths:
            if not Path(base).exists():
                continue
            for entry in Path(base).iterdir():
                if entry.is_file() and os.access(entry, os.X_OK):
                    binaries.append({
                        "name": entry.name,
                        "path": str(entry),
                    })
        return sorted(binaries, key=lambda x: x["name"])
